# -*- coding: utf-8 -*-
import json
import time
import threading
import Queue

from ..utils import print_error, print_debug, g_statsWrapper
from .web_socket_client import WebSocketClient

MAX_PAYLOAD_SIZE = 2 * 1024 * 1024


class ServerClient(object):
    def __init__(self, api_key=None):
        self.player_id = None
        self.base_host = "node-websocket-758468a49fee.herokuapp.com"
        self.secure = True
        self.port = 443

        self.access_key = api_key
        self.secret_key = "06032002-Hedebu"
        self.use_secret_auth = True

        self.lock = threading.Lock()
        self.last_request_time = 0.0
        self.request_cooldown = 1.0

        self._stop = threading.Event()
        self._sender_thread = None
        self._queue = Queue.Queue(maxsize=100)

        self._ws = None
        self._connected = False         
        self._connect_lock = threading.Lock()
        
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5.0

    def _rate_limit(self):
        with self.lock:
            now = time.time()
            delta = now - self.last_request_time
            if delta < self.request_cooldown:
                time.sleep(self.request_cooldown - delta)
            self.last_request_time = time.time()

    def _prepare_battle_stats(self, battle_stats):
        prepared = {}
        try:
            for arena_id, battle in (battle_stats or {}).iteritems():
                prepared_players = {}
                for pid, pstats in (battle.get("players", {}) or {}).iteritems():
                    prepared_players[str(pid)] = {
                        "name": str(pstats.get("name", "Unknown Player")),
                        "damage": int(pstats.get("damage", 0)),
                        "kills": int(pstats.get("kills", 0)),
                        "points": int(pstats.get("points", 0)),
                        "vehicle": str(pstats.get("vehicle", "Unknown Vehicle"))
                    }
                prepared[str(arena_id)] = {
                    "startTime": int(battle.get("startTime", int(time.time() * 1000))),
                    "duration": int(battle.get("duration", 0)),
                    "win": int(battle.get("win", -1)),
                    "mapName": str(battle.get("mapName", "Unknown Map")),
                    "players": prepared_players
                }
        except Exception as e:
            print_error("[WS] _prepare_battle_stats error: {}".format(e))
        return prepared

    def _prepare_player_info(self, player_info):
        prepared = {}
        try:
            for pid, name in (player_info or {}).iteritems():
                prepared[str(pid)] = str(name)
        except Exception as e:
            print_error("[WS] _prepare_player_info error: {}".format(e))
        return prepared

    def _build_payload(self, player_id, raw_data):
        if self.use_secret_auth and not self.access_key:
            print_error("[WS] secret_key режим: відсутній API key (payload.key) — запит не буде відправлено")
            return None

        body = {
            "BattleStats": self._prepare_battle_stats((raw_data or {}).get("BattleStats", {})),
            "PlayerInfo": self._prepare_player_info((raw_data or {}).get("PlayerInfo", {}))
        }

        payload = {
            "playerId": str(player_id) if player_id is not None else None,
            "key": str(self.access_key) if self.access_key is not None else None,
            "body": body
        }
        if self.use_secret_auth and self.secret_key:
            payload["secretKey"] = str(self.secret_key)

        if not body["BattleStats"] and not body["PlayerInfo"]:
            return None

        try:
            size = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
            if size > MAX_PAYLOAD_SIZE:
                print_error("[WS] Payload size {0} > {1} bytes, скасовано".format(size, MAX_PAYLOAD_SIZE))
                return None
        except Exception as e:
            print_error("[WS] Неможливо порахувати розмір payload: {}".format(e))

        return payload

    def _on_message(self, raw):
        try:
            if not raw:
                return

            if raw == "3":
                return
            if raw == "2":
                return
            if raw == "40":
                print_debug("[WS] Namespace connected (40)")
                return

            if raw.startswith("42"):
                try:
                    arr = json.loads(raw[2:])
                    event = arr[0]
                    data = arr[1] if len(arr) > 1 else None

                    if event == "connected":
                        self._connected = True
                        print_debug("[WS] Server connected event: {}".format(data))

                    elif event == "statsUpdated":
                        print_debug("[WS] statsUpdated: {}".format(data))

                    elif event == "updateError":
                        print_error("[WS] updateError: {}".format(data))

                    elif event == "pong":
                        print_debug("[WS] pong(event): {}".format(data))

                    else:
                        print_debug("[WS] event={} data={}".format(event, data))
                        
                except (ValueError, IndexError) as e:
                    print_error("[WS] Failed to parse Socket.IO message: {}".format(e))
            elif raw.startswith("44"):
                try:
                    data = json.loads(raw[2:])
                    message = data.get("message", "Unknown error")
                    print_error("[WS] Server error: {}".format(message))
                except:
                    print_error("[WS] Server error (raw): {}".format(raw))
            elif raw.startswith("0"):
                print_debug("[WS] Socket.IO handshake: {}".format(raw[:100]))
                self._connected = True
            else:
                print_debug("[WS] raw: {}".format(raw[:100]))
                
        except Exception as e:
            print_error("[WS] on_message parse error: {}".format(e))

    def _connect(self):
        with self._connect_lock:
            if self._ws and getattr(self._ws, "is_connected", False):
                print_debug("[WS] Already connected, skipping")
                return True
                
            attempts = 0
            while attempts < self._max_reconnect_attempts:
                try:
                    print_debug("[WS] Connection attempt {} of {}".format(attempts + 1, self._max_reconnect_attempts))
                    
                    if self._ws:
                        try:
                            self._ws.close()
                        except:
                            pass
                        self._ws = None
                    
                    self._connected = False
                    
                    ws_url_params = {}
                    if self.access_key:
                        ws_url_params['key'] = str(self.access_key)
                    if self.use_secret_auth and self.secret_key:
                        ws_url_params['secretKey'] = str(self.secret_key)
                    if self.player_id:
                        ws_url_params['playerId'] = str(self.player_id)
                    
                    self._ws = WebSocketClient(
                        host=self.base_host,
                        port=int(self.port),
                        secure=bool(self.secure),
                        api_key=str(self.access_key) if self.access_key is not None else None,
                        secret_key=str(self.secret_key) if self.use_secret_auth and self.secret_key else None,
                        player_id=str(self.player_id) if self.player_id is not None else None,
                        message_callback=self._on_message
                    )
                    
                    self._ws.connect()
                    
                    if getattr(self._ws, "is_connected", False):
                        print_debug("[WS] Successfully connected on attempt {}".format(attempts + 1))
                        return True
                    else:
                        raise Exception("Connection established but is_connected is False")
                        
                except Exception as e:
                    attempts += 1
                    print_error("[WS] Connection attempt {} failed: {}".format(attempts, e))
                    
                    if self._ws:
                        try:
                            self._ws.close()
                        except:
                            pass
                        self._ws = None
                    
                    self._connected = False
                    
                    if attempts < self._max_reconnect_attempts:
                        print_debug("[WS] Retrying in {} seconds...".format(self._reconnect_delay))
                        time.sleep(self._reconnect_delay)
                    
            print_error("[WS] Failed to connect after {} attempts".format(self._max_reconnect_attempts))
            return False

    def _ensure_background_sender(self):
        if self._sender_thread and self._sender_thread.is_alive():
            return
        self._stop.clear()
        self._sender_thread = threading.Thread(target=self._sender_loop)
        self._sender_thread.daemon = True
        self._sender_thread.start()
        print_debug("[WS] Background sender thread started")

    def _sender_loop(self):
        backoff = 1.0
        consecutive_failures = 0
        
        while not self._stop.is_set():
            try:
                if (not self._ws) or (not getattr(self._ws, "is_connected", False)):
                    print_debug("[WS] Not connected, attempting to connect...")
                    
                    if self._connect():
                        consecutive_failures = 0
                        backoff = 1.0
                        time.sleep(0.5)
                    else:
                        consecutive_failures += 1
                        backoff = min(backoff * 2.0, 30.0)
                        print_debug("[WS] Connection failed, waiting {} seconds (failure #{})".format(backoff, consecutive_failures))
                        time.sleep(backoff)
                    continue

                try:
                    item = self._queue.get(timeout=1.0)
                except Queue.Empty:
                    continue

                event_name, data = item
                
                self._rate_limit()
                
                if self._ws and getattr(self._ws, "is_connected", False):
                    success = self._ws.emit(event_name, data)
                    if success:
                        consecutive_failures = 0
                        backoff = 1.0
                        print_debug("[WS] Successfully sent: {}".format(event_name))
                    else:
                        print_error("[WS] Failed to send message, requeueing")
                        try:
                            self._queue.put(item, timeout=0.1)
                        except Queue.Full:
                            print_error("[WS] Queue full, message lost")
                else:
                    try:
                        self._queue.put(item, timeout=0.1)
                    except Queue.Full:
                        print_error("[WS] Queue full, message lost")
                
                self._queue.task_done()

            except Exception as e:
                print_error("[WS] Sender loop error: {}".format(e))
                self._connected = False
                if self._ws:
                    try:
                        self._ws.close()
                    except:
                        pass
                self._ws = None
                time.sleep(1.0)

        print_debug("[WS] Sender loop stopped")

    def setApiKey(self, api_key):
        self.access_key = str(api_key) if api_key is not None else None
        print_debug("[WS] API key updated: {}".format(self.access_key))

    def join_room(self, key=None, player_id=None):
        if key is not None:
            self.access_key = str(key)
        if player_id is not None:
            self.player_id = str(player_id)

        self._ensure_background_sender()
        
        data = {"key": str(self.access_key)}
        if self.player_id is not None:
            data["playerId"] = str(self.player_id)
        if self.use_secret_auth and self.secret_key:
            data["secretKey"] = str(self.secret_key)

        try:
            self._queue.put(('joinRoom', data), timeout=0.1)
            print_debug("[WS] Join room queued")
            return True
        except Queue.Full:
            print_error("[WS] Queue full (joinRoom)")
            return False

    def ping(self):
        self._ensure_background_sender()
        try:
            self._queue.put(('ping', {"key": str(self.access_key)}), timeout=0.1)
            return True
        except Queue.Full:
            print_error("[WS] Queue full (ping)")
            return False

    def send_stats(self, player_id=None):
        if player_id is not None:
            self.player_id = str(player_id)

        try:
            raw_data = g_statsWrapper.get_raw_data()
        except Exception as e:
            print_error("[WS] Cannot get stats data: {}".format(e))
            return {'success': False, 'status_code': 500, 'message': 'stats wrapper error'}

        payload = self._build_payload(self.player_id, raw_data)
        if not payload:
            return {'success': True, 'status_code': 204, 'message': 'no content'}

        self._ensure_background_sender()
        try:
            self._queue.put(('updateStats', payload), timeout=0.1)
            print_debug("[WS] Stats update queued for player: {}".format(self.player_id))
            return {'success': True, 'status_code': 202, 'message': 'queued'}
        except Queue.Full:
            print_error("[WS] Queue full, stats update cancelled")
            return {'success': False, 'status_code': 503, 'message': 'local queue full'}

    def disconnect(self):
        print_debug("[WS] Disconnecting...")
        self._stop.set()
        
        if self._ws:
            try:
                self._ws.close()
            except:
                pass
        
        try:
            if self._sender_thread and self._sender_thread.is_alive():
                print_debug("[WS] Waiting for sender thread to finish...")
                self._sender_thread.join(timeout=3.0)
                if self._sender_thread.is_alive():
                    print_error("[WS] Sender thread did not terminate within timeout")
        except Exception as e:
            print_error("[WS] Error waiting for sender thread: {}".format(e))
            
        self._ws = None
        self._connected = False
        print_debug("[WS] Disconnected")

    def fini(self):
        print_debug("[WS] Finalizing...")
        self.disconnect()
        

        try:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except:
                    break
        except Exception as e:
            print_error("[WS] Error clearing queue: {}".format(e))