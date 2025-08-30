# -*- coding: utf-8 -*-

import json
import time
import socket
import ssl
import base64
import struct
import threading
import urllib2
import random
from .utils import print_error, print_debug
from .stats_wraper import g_statsWrapper

class SocketIOClient(object):
    def __init__(self, url, access_key):
        self.host = "nodeserver-ffb64501d8ef.herokuapp.com"
        self.port = 443
        self.access_key = access_key
        self.socket = None
        self.connected = False
        self.sid = None
        self.ping_interval = 25
        self.ping_timeout = 20
        self.callbacks = {}
        self.callback_id = 1
        self.last_ping = 0
        
    def connect(self):
        try:
            if not self._handshake():
                return False
            if not self._upgrade_to_websocket():
                return False
            self._start_heartbeat()
            return True
        except Exception as e:
            print_error(u"Connect error: {}".format(e))
            return False
    
    def _handshake(self):
        try:
            url = "https://{}:{}/socket.io/?EIO=4&transport=polling&t={}".format(
                self.host, self.port, int(time.time() * 1000)
            )
            
            req = urllib2.Request(url)
            req.add_header('User-Agent', 'python-socketio')
            req.add_header('Accept', '*/*')
            req.add_header('Origin', 'https://{}'.format(self.host))
            
            response = urllib2.urlopen(req, timeout=30)
            data = response.read()
            
            if not data.startswith('0{'):
                return False
                
            handshake_data = json.loads(data[1:])
            self.sid = handshake_data.get('sid')
            self.ping_interval = handshake_data.get('pingInterval', 25000) / 1000
            self.ping_timeout = handshake_data.get('pingTimeout', 20000) / 1000
            
            if not self.sid:
                return False
            
            self._send_connect_packet()
            return True
            
        except Exception as e:
            print_error(u"[SocketIOClient] Handshake error: {}".format(e))
            return False
    
    def _send_connect_packet(self):
        try:
            url = "https://{}:{}/socket.io/?EIO=4&transport=polling&t={}&sid={}".format(
                self.host, self.port, int(time.time() * 1000), self.sid
            )
            
            data = '40'
            
            req = urllib2.Request(url, data=data)
            req.add_header('Content-Type', 'text/plain;charset=UTF-8')
            req.add_header('User-Agent', 'python-socketio')
            req.add_header('Origin', 'https://{}'.format(self.host))
            
            response = urllib2.urlopen(req, timeout=30)
            return True
            
        except Exception as e:
            print_error(u"[SocketIOClient] Connect packet error: {}".format(e))
            return False
    
    def _upgrade_to_websocket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(30)
            self.socket.connect((self.host, self.port))
            
            context = ssl.create_default_context()
            self.socket = context.wrap_socket(self.socket, server_hostname=self.host)
            
            key = base64.b64encode('{:016d}'.format(random.randint(10**15, 10**16-1)).encode()).decode()[:24]
            
            ws_request = (
                'GET /socket.io/?EIO=4&transport=websocket&sid={} HTTP/1.1\r\n'
                'Host: {}\r\n'
                'Upgrade: websocket\r\n'
                'Connection: Upgrade\r\n'
                'Sec-WebSocket-Key: {}\r\n'
                'Sec-WebSocket-Version: 13\r\n'
                'Origin: https://{}\r\n'
                'User-Agent: python-socketio\r\n'
                '\r\n'
            ).format(self.sid, self.host, key, self.host)
            
            self.socket.send(ws_request.encode())
            
            response = b''
            while b'\r\n\r\n' not in response:
                chunk = self.socket.recv(1024)
                if not chunk:
                    return False
                response += chunk
            
            if b'101 Switching Protocols' not in response:
                return False
            
            self.socket.settimeout(None)
            self.connected = True
            return True
            
        except Exception as e:
            print_error(u"[SocketIOClient] WebSocket upgrade error: {}".format(e))
            return False
    
    def _start_heartbeat(self):
        def heartbeat():
            while self.connected:
                try:
                    time.sleep(self.ping_interval - 5)
                    if self.connected:
                        self._send_socketio_frame('2')
                        self.last_ping = time.time()
                except:
                    break
        
        self.last_ping = time.time()
        thread = threading.Thread(target=heartbeat)
        thread.daemon = True
        thread.start()
    
    def _send_ping(self):
        try:
            self._send_socketio_frame('2')
        except:
            pass
    
    def _send_socketio_frame(self, data):
        if not self.connected or not self.socket:
            return False
        
        try:
            if isinstance(data, unicode):
                data = data.encode('utf-8')
            elif isinstance(data, str):
                data = data.encode('utf-8')
            
            frame = bytearray()
            frame.append(0x81)
            
            length = len(data)
            if length < 126:
                frame.append(0x80 | length)
            elif length < 65516:
                frame.append(0x80 | 126)
                frame.extend(struct.pack('!H', length))
            else:
                frame.append(0x80 | 127)
                frame.extend(struct.pack('!Q', length))
            
            mask_bytes = struct.pack('!I', random.randint(0, 0xFFFFFFFF))
            frame.extend(mask_bytes)
            
            masked_data = bytearray()
            for i, byte in enumerate(data):
                if isinstance(byte, str):
                    byte = ord(byte)
                mask_byte = ord(mask_bytes[i % 4]) if isinstance(mask_bytes[i % 4], str) else mask_bytes[i % 4]
                masked_data.append(byte ^ mask_byte)
            frame.extend(masked_data)
            
            self.socket.send(frame)
            return True
            
        except socket.error as e:
            print_error(u"[SocketIOClient] Socket error: {}".format(e))
            self.connected = False
            return False
        except Exception as e:
            print_error(u"[SocketIOClient] Send frame error: {}".format(e))
            self.connected = False
            return False
    
    def _receive_frame(self, timeout=30):
        try:
            self.socket.settimeout(timeout)
            
            header = self.socket.recv(2)
            if len(header) != 2:
                return None
            
            opcode = header[0] & 0x0F
            length = header[1] & 0x7F
            
            if length == 126:
                length_bytes = self.socket.recv(2)
                length = struct.unpack('!H', length_bytes)[0]
            elif length == 127:
                length_bytes = self.socket.recv(8)
                length = struct.unpack('!Q', length_bytes)[0]
            
            payload = b''
            while len(payload) < length:
                chunk = self.socket.recv(length - len(payload))
                if not chunk:
                    break
                payload += chunk
            
            if opcode == 1:
                message = payload.decode('utf-8')
                if message == '2':
                    self._send_socketio_frame('3')
                    return None
                return message
            elif opcode == 8:
                self.connected = False
                return None
            
            return None
            
        except socket.timeout:
            return None
        except Exception:
            return None
    
    def emit(self, event, data, callback=None):
        if not self.connected:
            return False
        
        try:
            packet_data = [event, data]
            
            if callback:
                cb_id = self.callback_id
                self.callback_id += 1
                self.callbacks[cb_id] = callback
                packet = "42{}{}".format(cb_id, json.dumps(packet_data, ensure_ascii=False, separators=(',', ':')))
            else:
                packet = "42{}".format(json.dumps(packet_data, ensure_ascii=False, separators=(',', ':')))
            
            if not self._send_socketio_frame(packet):
                return False
            
            if callback:
                start_time = time.time()
                while time.time() - start_time < 30:
                    response = self._receive_frame(1)
                    if response and self._handle_response(response, cb_id):
                        break
                    
            return True
            
        except Exception as e:
            print_error(u"[SocketIOClient] Emit error: {}".format(e))
            return False
    
    def _handle_response(self, message, expected_cb_id):
        try:
            if message == '3':
                self._send_socketio_frame('3')
                return False
            
            if message.startswith('43'):
                response_part = message[2:]
                
                cb_id_end = 0
                for i, char in enumerate(response_part):
                    if char.isdigit():
                        cb_id_end = i + 1
                    else:
                        break
                
                if cb_id_end > 0:
                    cb_id = int(response_part[:cb_id_end])
                    if cb_id == expected_cb_id:
                        json_part = response_part[cb_id_end:]
                        if json_part.startswith('[') and json_part.endswith(']'):
                            response_data = json.loads(json_part)
                            if response_data and cb_id in self.callbacks:
                                callback = self.callbacks.pop(cb_id)
                                callback(response_data[0])
                                return True
            
            return False
            
        except Exception:
            return False
    
    def close(self):
        self.connected = False
        if self.socket:
            try:
                self._send_socketio_frame('41')
                self.socket.close()
            except:
                pass


class ServerSyncClient(object):
    def __init__(self, access_key="test"):
        self.base_url = "https://nodeserver-ffb64501d8ef.herokuapp.com"
        self.access_key = access_key
        self.client = None
        self.lock = threading.Lock()
    
    def _ensure_connection(self):
        with self.lock:
            if not self.client or not self.client.connected:
                def connect_async():
                    self.client = SocketIOClient(self.base_url, self.access_key)
                    self.client.connect()
                
                thread = threading.Thread(target=connect_async)
                thread.daemon = True
                thread.start()
                
                return False
            return True
    
    def send_stats(self, player_id=None):
        def async_send():
            try:
                if not self._ensure_connection():
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
                
                def handle_callback(response):
                    pass
                
                if not self.client.emit('updateStats', data_to_send, handle_callback):
                    self._http_fallback_async(player_id)
                    
            except Exception:
                print_error(u"[ServerSyncClient] WebSocket send error")
                self._http_fallback_async(player_id)
        
        thread = threading.Thread(target=async_send)
        thread.daemon = True
        thread.start()
        
        return {
            'success': True,
            'status_code': 202,
            'message': 'Request queued for async processing',
            'response': {}
        }
    
    def _http_fallback_async(self, player_id=None):
        try:
            raw_data = g_statsWrapper.get_raw_data()
            
            data_to_send = {
                u"BattleStats": self._prepare_battle_stats(raw_data.get(u"BattleStats", {})),
                u"PlayerInfo": self._prepare_player_info(raw_data.get(u"PlayerInfo", {}))
            }
            
            json_data = json.dumps(data_to_send, ensure_ascii=False).encode('utf-8')
            
            headers = {
                'Content-Type': 'application/json; charset=utf-8',
                'User-Agent': 'WoT-StatsWrapper/1.0'
            }
            
            if player_id:
                headers['X-Player-ID'] = unicode(player_id)
            
            url = "{}/api/battle-stats/{}".format(self.base_url, self.access_key)
            req = urllib2.Request(url, data=json_data, headers=headers)
            urllib2.urlopen(req, timeout=10)
            
        except Exception as e:
            print_error(u"[ServerSyncClient] HTTP fallback error: {}".format(e))

    def disconnect(self):
        with self.lock:
            if self.client:
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

g_serverSyncClient = ServerSyncClient()