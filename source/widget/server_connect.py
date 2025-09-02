# -*- coding: utf-8 -*-

import json
import time
import threading
import urllib2

from .config import g_config
from .utils import print_error, print_debug, g_statsWrapper

class ServerClient(object):
    def __init__(self, config):
        self.config = config
        self.base_url = "https://node-websocket-758468a49fee.herokuapp.com"
        self.access_key = None
        self.secret_key = "06032002-Hedebu"
        self.lock = threading.Lock()
        self.last_request_time = 0
        self.request_cooldown = 1
        
    def _rate_limit(self):
        with self.lock:
            now = time.time()
            time_since_last = now - self.last_request_time
            if time_since_last < self.request_cooldown:
                sleep_time = self.request_cooldown - time_since_last
                time.sleep(sleep_time)
            self.last_request_time = time.time()

    def setApiKey(self):
        self.access_key = self.config.api_key.value if self.config and self.config.api_key else 'dev-test'

    def send_stats(self, api_key=None, player_id=None):
        print_debug("[ServerClient] Queuing stats send for player ID: {}".format(player_id))
        def async_send():
            try:
                self.setApiKey()
                self._rate_limit()
                raw_data = g_statsWrapper.get_raw_data()
                
                if not raw_data.get("BattleStats") and not raw_data.get("PlayerInfo"):
                    print_debug("[ServerClient] No data to send")
                    return
                
                data_to_send = {
                    "BattleStats": self._prepare_battle_stats(raw_data.get("BattleStats", {})),
                    "PlayerInfo": self._prepare_player_info(raw_data.get("PlayerInfo", {}))
                }
                
                json_data = json.dumps(data_to_send, ensure_ascii=False).encode('utf-8')
                
                headers = {
                    'Content-Type': 'application/json; charset=utf-8',
                    'User-Agent': 'WoT-Widget/1.0',
                    'X-Secret-Key': self.secret_key,
                    'X-API-Key': self.access_key
                }
                
                if player_id:
                    headers['X-Player-ID'] = str(player_id)
                
                url = "{}/api/server/update-stats".format(self.base_url)
                
                req = urllib2.Request(url, data=json_data)
                for header_name, header_value in headers.items():
                    req.add_header(header_name, header_value)
                
                resp = urllib2.urlopen(req, timeout=15)
                
                if 200 <= resp.getcode() < 300:
                    print_debug("[ServerClient] HTTP success: {}".format(resp.getcode()))
                else:
                    response_text = resp.read()
                    print_error("[ServerClient] HTTP error {}: {}".format(resp.getcode(), response_text))
                    
            except urllib2.HTTPError as e:
                error_body = ""
                try:
                    error_body = e.read()
                except:
                    pass
                print_error("[ServerClient] HTTP Error {}: {} - {}".format(e.code, e.reason, error_body))
                
            except Exception as e:
                print_error("[ServerClient] Request error: {}".format(e))
        
        thread = threading.Thread(target=async_send)
        thread.daemon = True
        thread.start()
        
        return {'success': True, 'status_code': 202, 'message': 'Request queued'}
    
    def _prepare_battle_stats(self, battle_stats):
        prepared = {}
        for arena_id, battle in battle_stats.items():
            prepared_players = {}
            for player_id, player_stats in battle.get("players", {}).items():
                prepared_players[str(player_id)] = {
                    "name": str(player_stats.get("name", "Unknown Player")),
                    "damage": int(player_stats.get("damage", 0)),
                    "kills": int(player_stats.get("kills", 0)),
                    "points": int(player_stats.get("points", 0)),
                    "vehicle": str(player_stats.get("vehicle", "Unknown Vehicle"))
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
        for player_id, player_name in player_info.items():
            prepared[str(player_id)] = str(player_name)
        return prepared

    def disconnect(self):
        print_debug("[ServerClient] Disconnect called")
        pass

    def fini(self):
        print_debug("[ServerClient] Finalizing")
        self.disconnect()

g_serverClient = ServerClient(g_config)