import threading
import time
from ..utils import print_debug, print_error


class ServerManager(object):
    def __init__(self):
        self._client = None
        self._current_api_key = None
        self._lock = threading.Lock()
        self._cleanup_timeout = 5.0
    
    def get_client(self, required_api_key=None):
        with self._lock:
            try:
                if required_api_key is None:
                    try:
                        from ..settings import g_config
                        required_api_key = g_config.get_api_key()
                    except:
                        required_api_key = 'dev-test'
                
                if (self._client is None or 
                    self._current_api_key != required_api_key or
                    not getattr(self._client, 'is_connected', False)):
                    
                    self._recreate_client(required_api_key)
                
                return self._client
                
            except Exception as e:
                print_error("[ServerManager] Error getting client: {}".format(e))
                return None
    
    def _recreate_client(self, api_key):
        try:
            from ..settings import g_config
            if not g_config.configParams.enabled.value:
                print_debug("[ServerManager] Mod disabled, skipping client creation")
                return
        except ImportError:
            print_debug("[ServerManager] ImportError occurred")
            return
        
        try:
            old_client = self._client
            
            from .server_connect import ServerClient
            new_client = ServerClient(api_key=api_key)
            
            self._client = new_client
            self._current_api_key = api_key
            
            print_debug("[ServerManager] Created new client with API key: {}".format(api_key))
            
            if old_client:
                self._cleanup_old_client(old_client)
            
        except Exception as e:
            print_error("[ServerManager] Failed to recreate client: {}".format(e))
            self._client = None
            self._current_api_key = None
    
    def _cleanup_old_client(self, old_client):
        def cleanup_thread():
            try:
                print_debug("[ServerManager] Starting cleanup of old client")
                
                if hasattr(old_client, '_stop'):
                    old_client._stop.set()
                
                if hasattr(old_client, 'disconnect'):
                    old_client.disconnect()
                
                if hasattr(old_client, '_sender_thread') and old_client._sender_thread:
                    if old_client._sender_thread.is_alive():
                        old_client._sender_thread.join(timeout=self._cleanup_timeout)
                        if old_client._sender_thread.is_alive():
                            print_error("[ServerManager] Sender thread did not terminate within timeout")
                
                if hasattr(old_client, '_ws') and old_client._ws:
                    try:
                        old_client._ws.close()
                    except:
                        pass
                
                print_debug("[ServerManager] Old client cleanup completed")
                
            except Exception as e:
                print_error("[ServerManager] Error during old client cleanup: {}".format(e))
        
        cleanup_worker = threading.Thread(target=cleanup_thread)
        cleanup_worker.daemon = True
        cleanup_worker.start()
    
    def send_stats(self, player_id=None):
        try:
            from ..settings import g_config
            if not g_config.configParams.enabled.value:
                print_debug("[ServerManager] Mod disabled, skipping stats send")
                return {'success': False, 'message': 'Mod disabled'}
        except ImportError:
            print_debug("[ServerManager] ImportError occurred")
            return {'success': False, 'message': 'Config unavailable'}

        client = self.get_client()
        if client:
            return client.send_stats(player_id=player_id)
        else:
            return {'success': False, 'message': 'Client not available'}
    
    def disconnect(self):
        with self._lock:
            if self._client:
                try:
                    print_debug("[ServerManager] Disconnecting current client")
                    self._client.disconnect()
                    
                    if hasattr(self._client, '_sender_thread') and self._client._sender_thread:
                        if self._client._sender_thread.is_alive():
                            self._client._sender_thread.join(timeout=self._cleanup_timeout)
                    
                except Exception as e:
                    print_error("[ServerManager] Error during disconnect: {}".format(e))
                finally:
                    self._client = None
                    self._current_api_key = None
    
    def force_cleanup(self):
        with self._lock:
            if self._client:
                print_debug("[ServerManager] Force cleanup initiated")
                try:
                    if hasattr(self._client, '_stop'):
                        self._client._stop.set()
                    
                    if hasattr(self._client, '_ws') and self._client._ws:
                        try:
                            self._client._ws.close()
                        except:
                            pass
                    
                    if hasattr(self._client, '_sender_thread') and self._client._sender_thread:
                        if self._client._sender_thread.is_alive():
                            print_debug("[ServerManager] Waiting for sender thread to terminate")
                            self._client._sender_thread.join(timeout=1.0)
                            if self._client._sender_thread.is_alive():
                                print_error("[ServerManager] Force cleanup: sender thread still alive")
                
                except Exception as e:
                    print_error("[ServerManager] Error during force cleanup: {}".format(e))
                finally:
                    self._client = None
                    self._current_api_key = None


g_server_manager = ServerManager()