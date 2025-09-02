# -*- coding: utf-8 -*-

import json
import time
import threading
import urllib2

from .utils import print_error, print_debug, g_statsWrapper

class SocketIOClient(object):
    PACKET_CONNECT = "40"
    PACKET_DISCONNECT = "41"
    PACKET_EVENT = "42"
    PACKET_PING = "2"
    PACKET_PONG = "3"

    def __init__(self, access_key="test"):
        self.host = "node-websocket-758468a49fee.herokuapp.com"
        self.port = 443
        self.access_key = access_key
        self.secret_key = "06032002-Hedebu"
        self.connected = False
        self.sid = None
        self.ping_interval = 25
        self.ping_timeout = 20
        self.lock = threading.Lock()
        self.polling = False
        self.callback_counter = 0
        self.callbacks = {}

    def _build_url_for_handshake(self):
        timestamp = int(time.time() * 1000)
        base_url = "https://{}:{}/socket.io/?EIO=4&transport=polling&t={}".format(self.host, self.port, timestamp)
        if self.secret_key:
            return "{}&secretKey={}".format(base_url, self.secret_key)
        return "{}&key={}".format(base_url, self.access_key)
    
    def _build_url(self):
        timestamp = int(time.time() * 1000)
        return "https://{}:{}/socket.io/?EIO=4&transport=polling&t={}&sid={}".format(
            self.host, self.port, timestamp, self.sid if self.sid else ""
        )

    def connect(self):
        print_debug("[SocketIOClient] Attempting to connect...")
        try:
            if not self._handshake():
                print_error("[SocketIOClient] Connection failed during handshake.")
                return False
            self.connected = True
            self._start_polling()
            print_debug("[SocketIOClient] Connection successful.")
            return True
        except Exception as e:
            print_error("[SocketIOClient] General connection error: {}".format(e))
            return False

    def _handshake(self):
        print_debug("[SocketIOClient] Starting handshake...")
        url = self._build_url_for_handshake()
        req = urllib2.Request(url)
        req.add_header("User-Agent", "python-socketio")
        req.add_header("Accept", "*/*")

        try:
            resp = urllib2.urlopen(req, timeout=30)
            data = resp.read()
            if not data.startswith("0{"):
                print_error("[SocketIOClient] Invalid handshake response: {}".format(data))
                return False
            
            handshake = json.loads(data[1:])
            self.sid = handshake.get("sid")
            self.ping_interval = handshake.get("pingInterval", 25000) / 1000.0
            self.ping_timeout = handshake.get("pingTimeout", 20000) / 1000.0
            print_debug("[SocketIOClient] Handshake successful, SID: {}, PingInterval: {}".format(self.sid, self.ping_interval))

            url = self._build_url()
            req = urllib2.Request(url, data=self.PACKET_CONNECT)
            req.add_header("Content-Type", "text/plain")
            urllib2.urlopen(req, timeout=30)
            print_debug("[SocketIOClient] Sent CONNECT packet.")
            return True

        except (urllib2.URLError, ValueError, KeyError) as e:
            print_error("[SocketIOClient] Handshake failed: {}".format(e))
            return False

    def _start_polling(self):
        def polling_loop():
            self.polling = True
            consecutive_errors = 0
            print_debug("[SocketIOClient] Starting polling loop.")
            
            while self.connected and self.polling:
                try:
                    time.sleep(0.1)
                    url = self._build_url()
                    req = urllib2.Request(url)
                    resp = urllib2.urlopen(req, timeout=self.ping_timeout)
                    data = resp.read()
                    
                    consecutive_errors = 0
                    
                    if data:
                        self._handle_message(data)
                
                except urllib2.HTTPError as e:
                    consecutive_errors += 1
                    print_error("[SocketIOClient] Polling HTTP error: {} {}".format(e.code, e.reason))
                    if e.code == 400:
                        print_error("[SocketIOClient] Session ID might be invalid. Disconnecting.")
                        self.connected = False
                        break
                    time.sleep(min(1 * (2 ** consecutive_errors), 30))

                except (urllib2.URLError, IOError) as e:
                    consecutive_errors += 1
                    print_debug("[SocketIOClient] Polling connection error: {}".format(e))
                    if consecutive_errors > 5:
                        print_error("[SocketIOClient] Too many connection errors, disconnecting.")
                        self.connected = False
                        break
                    time.sleep(min(1 * (2 ** consecutive_errors), 30))
            print_debug("[SocketIOClient] Polling loop stopped.")
        
        thread = threading.Thread(target=polling_loop)
        thread.daemon = True
        thread.start()
        
        def heartbeat_loop():
            print_debug("[SocketIOClient] Starting heartbeat loop.")
            while self.connected and self.polling:
                time.sleep(self.ping_interval)
                if self.connected:
                    self._send_ping()
            print_debug("[SocketIOClient] Heartbeat loop stopped.")
        
        heartbeat_thread = threading.Thread(target=heartbeat_loop)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()

    def _handle_message(self, data):
        try:
            messages = self._parse_socket_io_messages(data)
            for msg in messages:
                if msg == self.PACKET_PING:
                    print_debug("[SocketIOClient] Received PING, sending PONG.")
                    self._send_pong()
                elif msg.startswith(self.PACKET_DISCONNECT):
                    print_debug("[SocketIOClient] Server requested disconnect.")
                    self.close()
                elif msg.startswith(self.PACKET_EVENT):
                    try:
                        payload = json.loads(msg[2:])
                        if isinstance(payload, list) and len(payload) >= 3:
                            callback_id = payload[2]
                            with self.lock:
                                if callback_id in self.callbacks:
                                    callback_data = payload[1] if len(payload) > 1 else None
                                    cb = self.callbacks.pop(callback_id)
                                    print_debug("[SocketIOClient] Executing callback for ID: {}".format(callback_id))
                                    cb(callback_data)
                    except (ValueError, KeyError, IndexError) as e:
                        print_error("[SocketIOClient] Error handling callback message: {}".format(e))
        except Exception as e:
            print_error("[SocketIOClient] Error in _handle_message: {}".format(e))

    def _parse_socket_io_messages(self, data):
        messages = []
        if not data: return messages
        if ':' not in data or not data[0].isdigit():
            messages.append(data)
            return messages
        pos = 0
        while pos < len(data):
            colon_pos = data.find(':', pos)
            if colon_pos == -1:
                if pos < len(data): messages.append(data[pos:])
                break
            try:
                length_str = data[pos:colon_pos]
                if not length_str.isdigit():
                    messages.append(data[pos:])
                    break
                msg_length = int(length_str)
                msg_start = colon_pos + 1
                msg_end = msg_start + msg_length
                if msg_end > len(data):
                    messages.append(data[pos:])
                    break
                messages.append(data[msg_start:msg_end])
                pos = msg_end
            except (ValueError, IndexError):
                messages.append(data[pos:])
                break
        return messages

    def _send_packet(self, packet_type, packet_data):
        try:
            url = self._build_url()
            req = urllib2.Request(url, data=packet_data)
            req.add_header("Content-Type", "text/plain; charset=UTF-8")
            urllib2.urlopen(req, timeout=10)
            return True
        except (urllib2.URLError, IOError) as e:
            print_error("[SocketIOClient] Error sending packet {}: {}".format(packet_type, e))
            return False

    def _send_ping(self):
        print_debug("[SocketIOClient] Sending PING.")
        self._send_packet("PING", self.PACKET_PING)

    def _send_pong(self):
        self._send_packet("PONG", self.PACKET_PONG)

    def emit(self, event, data, callback=None):
        if not self.connected or not self.sid:
            print_error("[SocketIOClient] Cannot emit event '{}', not connected.".format(event))
            return False
        
        print_debug("[SocketIOClient] Emitting event: '{}'".format(event))
        packet_data = [event, data]
        callback_id = None
        
        if callback:
            with self.lock:
                self.callback_counter += 1
                callback_id = str(self.callback_counter)
                self.callbacks[callback_id] = callback
            packet_data.append(callback_id)
            print_debug("[SocketIOClient] Registered callback with ID: {}".format(callback_id))
            
            def timeout_callback():
                time.sleep(30)
                with self.lock:
                    if callback_id in self.callbacks:
                        print_error("[SocketIOClient] Callback {} timed out.".format(callback_id))
                        cb = self.callbacks.pop(callback_id)
                        cb({"error": "Timeout", "status": 408})
            
            timeout_thread = threading.Thread(target=timeout_callback)
            timeout_thread.daemon = True
            timeout_thread.start()
            
        packet = self.PACKET_EVENT + json.dumps(packet_data, ensure_ascii=False)
        
        if not self._send_packet("EMIT", packet.encode('utf-8')):
            print_error("[SocketIOClient] Failed to send EMIT packet for event '{}'.".format(event))
            if callback_id:
                with self.lock:
                    if callback_id in self.callbacks:
                        del self.callbacks[callback_id]
            return False
        
        return True

    def close(self):
        if self.connected:
            print_debug("[SocketIOClient] Closing connection.")
            self.connected = False
            self.polling = False
            self._send_packet("DISCONNECT", self.PACKET_DISCONNECT)

class ServerClient(object):
    def __init__(self, access_key="test",):
        self.base_url = "https://node-websocket-758468a49fee.herokuapp.com"
        self.access_key = access_key
        self.secret_key = "06032002-Hedebu"
        self.client = None
        self.lock = threading.Lock()
        self.last_connect_attempt = 0
        self.connect_cooldown = 5
    
    def _ensure_connection(self):
        with self.lock:
            now = time.time()
            if now - self.last_connect_attempt < self.connect_cooldown: return False
            if not self.client or not self.client.connected:
                print_debug("[ServerClient] Connection check failed. Attempting to reconnect.")
                self.last_connect_attempt = now
                try:
                    self.client = SocketIOClient(access_key=self.access_key)
                    if self.client.connect():
                        print_debug("[ServerClient] Reconnection successful.")
                        return True
                    else:
                        print_error("[ServerClient] Reconnection failed.")
                        self.client = None
                        return False
                except Exception as e:
                    print_error("[ServerClient] Exception during reconnection: {}".format(e))
                    self.client = None
                    return False
            return True
    
    def send_stats(self, player_id=None):
        print_debug("[ServerClient] Queuing stats send for player ID: {}".format(player_id))
        def async_send():
            try:
                if not self._ensure_connection():
                    print_debug("[ServerClient] WebSocket connection failed, switching to HTTP fallback.")
                    self._http_fallback_async(player_id)
                    return
                raw_data = g_statsWrapper.get_raw_data()
                data_to_send = {
                    u"key": self.access_key,
                    u"playerId": unicode(player_id) if player_id else None,
                    u"body": {
                        u"BattleStats": self._prepare_battle_stats(raw_data.get(u"BattleStats", {})),
                        u"PlayerInfo": self._prepare_player_info(raw_data.get(u"PlayerInfo", {}))
                    }
                }
                if self.secret_key:
                    data_to_send[u"secretKey"] = self.secret_key

                def handle_response(response):
                    if response and isinstance(response, dict) and response.get('success'):
                        print_debug("[ServerClient] WebSocket response OK: {}".format(response))
                    else:
                        print_error("[ServerClient] WebSocket error response: {}".format(response))

                if not self.client.emit('updateStats', data_to_send, handle_response):
                    print_error("[ServerClient] WebSocket emit failed, switching to HTTP fallback.")
                    self._http_fallback_async(player_id)
                    
            except Exception as e:
                print_error(u"[ServerClient] Unhandled exception in async_send: {}".format(e))
                self._http_fallback_async(player_id)
        
        thread = threading.Thread(target=async_send)
        thread.daemon = True
        thread.start()
        
        return {'success': True, 'status_code': 202, 'message': 'Request queued'}
    
    def _http_fallback_async(self, player_id=None):
        print_debug("[ServerClient] Executing HTTP fallback for player ID: {}".format(player_id))
        try:
            raw_data = g_statsWrapper.get_raw_data()
            data_to_send = {
                u"BattleStats": self._prepare_battle_stats(raw_data.get(u"BattleStats", {})),
                u"PlayerInfo": self._prepare_player_info(raw_data.get(u"PlayerInfo", {}))
            }
            json_data = json.dumps(data_to_send, ensure_ascii=False).encode('utf-8')
            
            headers = {
                'Content-Type': 'application/json; charset=utf-8',
                'User-Agent': 'WoT-StatsWrapper/1.0',
                'X-API-Key': self.access_key
            }
            if self.secret_key:
                headers['X-Secret-Key'] = self.secret_key
            if player_id:
                headers['X-Player-ID'] = unicode(player_id)
            
            url = "{}/api/server/update-stats".format(self.base_url)
            print_debug("[ServerClient] HTTP Fallback URL: {}".format(url))
            
            req = urllib2.Request(url, data=json_data, headers=headers)
            resp = urllib2.urlopen(req, timeout=15)
            
            if 200 <= resp.getcode() < 300:
                print_debug("[ServerClient] HTTP fallback successful, status: {}".format(resp.getcode()))
            else:
                print_error(u"[ServerClient] HTTP fallback failed with status {}: {}".format(resp.getcode(), resp.read()))

        except urllib2.HTTPError as e:
            print_error(u"[ServerClient] HTTP fallback HTTPError: {} {}, Body: {}".format(e.code, e.reason, e.read()))
        except Exception as e:
            print_error(u"[ServerClient] HTTP fallback unexpected error: {}".format(e))

    def disconnect(self):
        with self.lock:
            if self.client:
                print_debug("[ServerClient] Disconnecting client.")
                self.client.close()
                self.client = None
    
    def _prepare_battle_stats(self, battle_stats):
        prepared = {}
        for arena_id, battle in battle_stats.items():
            prepared_players = {}
            for player_id, player_stats in battle.get(u"players", {}).items():
                prepared_players[unicode(player_id)] = {
                    u"name": unicode(player_stats.get(u"name", u"Unknown Player")),
                    u"damage": int(player_stats.get(u"damage", 0)),
                    u"kills": int(player_stats.get(u"kills", 0)),
                    u"points": int(player_stats.get(u"points", 0)),
                    u"vehicle": unicode(player_stats.get(u"vehicle", u"Unknown Vehicle"))
                }
            prepared[unicode(arena_id)] = {
                u"startTime": int(battle.get(u"startTime", int(time.time() * 1000))),
                u"duration": int(battle.get(u"duration", 0)),
                u"win": int(battle.get(u"win", -1)),
                u"mapName": unicode(battle.get(u"mapName", u"Unknown Map")),
                u"players": prepared_players
            }
        return prepared
    
    def _prepare_player_info(self, player_info):
        prepared = {}
        for player_id, player_name in player_info.items():
            prepared[unicode(player_id)] = unicode(player_name)
        return prepared

    def fini(self):
        print_debug("[ServerClient] Finalizing.")
        self.disconnect()

g_serverClient = ServerClient()