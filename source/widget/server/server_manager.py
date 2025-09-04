import threading
from source.widget.utils import print_debug, print_error


class ServerManager(object):
    def __init__(self):
        self._client = None
        self._current_api_key = None
        self._lock = threading.Lock()
    
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
                print_debug("[ServerManager] Mod disabled, skipping battle session start")
                return
        except ImportError:
            print_debug("[ServerManager] ImportError occurred")
            return
        
        try:
            if self._client:
                try:
                    self._client.disconnect()
                except:
                    pass

            from .server_connect import ServerClient
            self._client = ServerClient(api_key=api_key)
            self._current_api_key = api_key
            
            print_debug("[ServerManager] Created new client with API key: {}".format(api_key))
            
        except Exception as e:
            print_error("[ServerManager] Failed to recreate client: {}".format(e))
            self._client = None
            self._current_api_key = None
    
    def send_stats(self, player_id=None):
        try:
            from ..settings import g_config
            if not g_config.configParams.enabled.value:
                print_debug("[ServerManager] Mod disabled, skipping battle session start")
                return
        except ImportError:
            print_debug("[ServerManager] ImportError occurred")
            return

        client = self.get_client()
        if client:
            return client.send_stats(player_id=player_id)
        else:
            return {'success': False, 'message': 'Client not available'}
    
    def disconnect(self):
        with self._lock:
            if self._client:
                try:
                    self._client.disconnect()
                except:
                    pass
                self._client = None
                self._current_api_key = None

g_server_manager = ServerManager()
