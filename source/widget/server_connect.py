# -*- coding: utf-8 -*-
import json
import time
import threading
import Queue

from .utils import print_error, print_debug, g_statsWrapper
from .web_socket_client import WebSocketClient

MAX_PAYLOAD_SIZE = 2 * 1024 * 1024


class ServerClient(object):
    def __init__(self):
        self.player_id = None
        self.base_host = "node-websocket-758468a49fee.herokuapp.com"
        self.secure = True
        self.port = 443

        self.access_key = None           
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

            # події
            if raw.startswith("42"):
                arr = json.loads(raw[2:])
                event = arr[0]
                data = arr[1] if len(arr) > 1 else None

                if event == "connected":
                    self._connected = True
                    print_debug("[WS] connected: {}".format(data))

                elif event == "statsUpdated":
                    print_debug("[WS] statsUpdated: {}".format(data))

                elif event == "updateError":
                    print_error("[WS] updateError: {}".format(data))

                elif event == "pong":
                    print_debug("[WS] pong(event): {}".format(data))

                else:
                    print_debug("[WS] event={} data={}".format(event, data))
            else:
                print_debug("[WS] raw: {}".format(raw))
        except Exception as e:
            print_error("[WS] on_message parse error: {}".format(e))


    def _connect(self):
        with self._connect_lock:
            if self._ws and getattr(self._ws, "is_connected", False):
                return
            try:
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
            except Exception as e:
                self._connected = False
                if self._ws:
                    try:
                        self._ws.close()
                    except:
                        pass
                self._ws = None
                print_error("[WS] Не вдалося підключитись: {}".format(e))

    def _ensure_background_sender(self):
        if self._sender_thread and self._sender_thread.is_alive():
            return
        self._stop.clear()
        self._sender_thread = threading.Thread(target=self._sender_loop)
        self._sender_thread.daemon = True
        self._sender_thread.start()

    def _sender_loop(self):
        backoff = 1.0
        while not self._stop.is_set():
            try:
                if (not self._ws) or (not getattr(self._ws, "is_connected", False)) or (not self._connected):
                    self._connect()
                    time.sleep(0.5)
                    if (not self._ws) or (not getattr(self._ws, "is_connected", False)) or (not self._connected):
                        time.sleep(backoff)
                        backoff = min(backoff * 2.0, 30.0)
                        continue
                backoff = 1.0

                try:
                    item = self._queue.get(timeout=1.0)
                except Queue.Empty:
                    continue

                event_name, data = item
                self._rate_limit()
                if self._ws and getattr(self._ws, "is_connected", False) and self._connected:
                    self._ws.emit(event_name, data)
                else:
                    try:
                        self._queue.put(item, timeout=0.1)
                    except Queue.Full:
                        print_error("[WS] Локальна черга переповнена при повторному додаванні")
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


    def setApiKey(self, api_key):
        self.access_key = str(api_key) if api_key is not None else None

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
            return True
        except Queue.Full:
            print_error("[WS] Черга переповнена (joinRoom)")
            return False

    def ping(self):
        self._ensure_background_sender()
        try:
            self._queue.put(('ping', {"key": str(self.access_key)}), timeout=0.1)
            return True
        except Queue.Full:
            print_error("[WS] Черга переповнена (ping)")
            return False

    def send_stats(self, player_id=None):
        if player_id is not None:
            self.player_id = str(player_id)

        try:
            raw_data = g_statsWrapper.get_raw_data()
        except Exception as e:
            print_error("[WS] Неможливо отримати дані зі statsWrapper: {}".format(e))
            return {'success': False, 'status_code': 500, 'message': 'stats wrapper error'}

        payload = self._build_payload(self.player_id, raw_data)
        if not payload:
            return {'success': True, 'status_code': 204, 'message': 'no content'}

        self._ensure_background_sender()
        try:
            self._queue.put(('updateStats', payload), timeout=0.1)
            return {'success': True, 'status_code': 202, 'message': 'queued'}
        except Queue.Full:
            print_error("[WS] Черга переповнена, скасовано")
            return {'success': False, 'status_code': 503, 'message': 'local queue full'}

    def disconnect(self):
        self._stop.set()
        if self._ws:
            try:
                self._ws.close()
            except:
                pass
        try:
            if self._sender_thread and self._sender_thread.is_alive():
                self._sender_thread.join(timeout=1.0)
        except Exception:
            pass
        self._ws = None
        self._connected = False

    def fini(self):
        self.disconnect()


g_serverClient = ServerClient()
