# -*- coding: utf-8 -*-
class StatsWrapper(object):
    
    def __init__(self, data=None):
        self.pointPerFrag = 400
        if data is None:
            self.data = {
                "BattleStats": {},
                "PlayerInfo": {}
            }
        else:
            self.data = data
            
    def _get_player_data(self, arena_id, player_id):
        battle = self.get_battle(arena_id)
        if battle and player_id in battle.get("players", {}):
            return battle["players"][player_id]
        return None

    def add_player_info(self, player_id, player_name):
        if not player_id or not player_name:
            return
        self.data["PlayerInfo"][(player_id)] = (player_name)
    
    def get_all_players_info(self):
        return dict(self.data["PlayerInfo"])
    
    def remove_player_info(self, player_id):
        player_id = (player_id)
        if player_id in self.data["PlayerInfo"]:
            del self.data["PlayerInfo"][player_id]
            return True
        return False
    
    def create_battle(self, arena_id, start_time=0, duration=0, win=-1, map_name=u"Unknown Map"):
        if not arena_id:
            return
        self.data["BattleStats"][arena_id] = {
            "startTime": start_time,
            "duration": duration,
            "win": win,
            "mapName": unicode(map_name),
            "players": {}
        }
    
    def get_battle(self, arena_id):
        return self.data["BattleStats"].get(arena_id)
    
    def get_all_battles(self):
        return list(self.data["BattleStats"].keys())
    
    def remove_battle(self, arena_id):
        if arena_id in self.data["BattleStats"]:
            del self.data["BattleStats"][arena_id]
            return True
        return False
    
    def add_player_to_battle(self, arena_id, player_id, name=u"Unknown Player", damage=0, kills=0, points=0, vehicle=u"Unknown Vehicle"):

        if arena_id not in self.data[u"BattleStats"]:
            self.create_battle(arena_id)
        
        self.data["BattleStats"][arena_id]["players"][player_id] = {
            "name": unicode(name), "damage": damage, "kills": kills,
            "points": points, "vehicle": unicode(vehicle)
        }
    
    def get_player_battle_stats(self, arena_id, player_id):
        player_data = self._get_player_data(arena_id, player_id)
        if player_data:
            return dict(player_data) 
        return None

    def update_battle_stats(self, arena_id, win=None, duration=None, player_id=None, name=None, points=None, damage=None, kills=None, vehicle=None):
        player_data = self._get_player_data(arena_id, player_id)
        if not player_data:
            return False

        if duration is not None:
            battle = self.get_battle(arena_id)
            if battle:
                battle["duration"] = duration

        if win is not None:
            battle = self.get_battle(arena_id)
            if battle:
                battle["win"] = win

        if name is not None:
            player_data["name"] = unicode(name)

        if points is not None:
            player_data["points"] = points

        if damage is not None:
            player_data["damage"] = damage

        if kills is not None:
            player_data["kills"] = kills

        if vehicle is not None:
            player_data["vehicle"] = unicode(vehicle)

        return True

    def add_damage(self, arena_id, player_id, damage):
        if not isinstance(damage, (int, float)) or damage <= 0:
            return False

        player_data = self._get_player_data(arena_id, player_id)
        if player_data:
        
            player_data["damage"] += damage
            return True
        return False
    
    def add_kills(self, arena_id, player_id, kills):
        if not isinstance(kills, (int, float)) or kills <= 0:
            return False

        player_data = self._get_player_data(arena_id, player_id)
        if player_data:
            player_data["kills"] += kills
            return True
        return False

    def add_points(self, arena_id, player_id, points):
        if not isinstance(points, (int, float)) or points <= 0:
            return False

        player_data = self._get_player_data(arena_id, player_id)
        if player_data:
            player_data["points"] += points
            return True
        return False

    def get_raw_data(self):
        return self.data
    
    def clear_all_data(self):
        self.data = {"BattleStats": {}, "PlayerInfo": {}}

    def clear_battle_data(self):
        self.data["BattleStats"] = {}