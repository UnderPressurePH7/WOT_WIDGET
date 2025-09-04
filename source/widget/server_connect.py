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
        return prepared

    def _prepare_player_info(self, player_info):
        prepared = {}
        for pid, name in (player_info or {}).iteritems():
            prepared[str(pid)] = str(name)
        return prepared

    def _build_payload(self, player_id, raw_data):
        body = {
            "BattleStats": self._prepare_battle_stats(raw_data.get("BattleStats", {})),
            "PlayerInfo": self._prepare_player_info(raw_data.get("PlayerInfo", {}))
        }

        payload = {
            "playerId": str(player_id) if player_id is not None else None,
            "key": self.access_key,
            "body": body
        }
        if self.use_secret_auth and self.secret_key:
            payload["secretKey"] = self.secret_key

        if not body["BattleStats"] and not body["PlayerInfo"]:
            return None

        try:
            size = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
            if size > MAX_PAYLOAD_SIZE:
                print_error("[WS] Payload size {} > {} bytes, скасовано".format(size, MAX_PAYLOAD_SIZE))
                return None
        except Exception as e:
            print_error("[WS] Неможливо порахувати розмір payload: {}".format(e))

        return payload

    def _on_message(self, raw):
        try:
            if raw.startswith("42"):
                arr = json.loads(raw[2:])
                event = arr[0]
                data = arr[1]
                if event == "connected":
                    print_debug("[WS] connected: {}".format(data))
                elif event == "statsUpdated":
                    print_debug("[WS] statsUpdated: {}".format(data))
                elif event == "updateError":
                    print_error("[WS] updateError: {}".format(data))
                elif event == "pong":
                    print_debug("[WS] pong: {}".format(data))
                else:
                    print_debug("[WS] event={} data={}".format(event, data))
        except Exception as e:
            print_error("[WS] on_message parse error: {}".format(e))

    def _connect(self):
        with self._connect_lock:
            if self._connected and self._ws:
                return

            try:
                scheme = "wss" if self.secure else "ws"
                url = "{}://{}:{}/socket.io/".format(scheme, self.base_host, self.port)
                print_debug("[WS] Connecting to {} ...".format(url))

                self._ws = WebSocketClient(
                    url,
                    key=self.access_key,
                    secret_key=self.secret_key if self.use_secret_auth else None,
                    player_id=self.player_id,
                    on_message=self._on_message
                )
                self._ws.connect()
                self._connected = True
                print_debug("[WS] Connected")
            except Exception as e:
                self._connected = False
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
                if not self._connected or not self._ws:
                    self._connect()
                    if not self._connected:
                        time.sleep(backoff)
                        backoff = min(backoff * 2.0, 30.0)
                        continue
                    backoff = 1.0

                try:
                    item = self._queue.get(timeout=0.25)
                except Queue.Empty:
                    try:
                        if self._ws:
                            self._ws.emit("ping", {"ts": int(time.time() * 1000)})
                    except Exception:
                        pass
                    continue

                event_name, data = item
                self._rate_limit()
                if self._ws:
                    self._ws.emit(event_name, data)

            except Exception as e:
                print_error("[WS] Sender loop error: {}".format(e))
                self._connected = False
                self._ws = None
                time.sleep(1.0)

    def setApiKey(self, api_key):
        self.access_key = api_key

    def send_stats(self, player_id=None):
        if player_id is not None:
            self.player_id = player_id

        try:
            raw_data = g_statsWrapper.get_raw_data()
        except Exception as e:
            print_error("[WS] Неможливо отримати дані зі statsWrapper: {}".format(e))
            return {'success': False, 'status_code': 500, 'message': 'stats wrapper error'}

        payload = self._build_payload(self.player_id, raw_data)
        if not payload:
            print_debug("[WS] Немає даних для відправки або payload занадто великий")
            return {'success': True, 'status_code': 204, 'message': 'no content'}

        self._ensure_background_sender()
        try:
            self._queue.put(('updateStats', payload), timeout=0.1)
            print_debug("[WS] Запит поставлено в чергу для playerId={}".format(self.player_id))
            return {'success': True, 'status_code': 202, 'message': 'queued'}
        except Queue.Full:
            print_error("[WS] Черга переповнена, скасовано")
            return {'success': False, 'status_code': 503, 'message': 'local queue full'}

    def disconnect(self):
        print_debug("[WS] Disconnect called")
        self._stop.set()
        try:
            if self._sender_thread and self._sender_thread.is_alive():
                self._sender_thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        finally:
            self._ws = None
            self._connected = False

    def fini(self):
        print_debug("[WS] Finalizing")
        self.disconnect()


g_serverClient = ServerClient()
