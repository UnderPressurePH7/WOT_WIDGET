# -*- coding: utf-8 -*-

class StatsWrapper(object):
    
    def __init__(self, data=None):
        self.pointPerFrag = 400
        if data is None:
            self.data = {
                u"BattleStats": {},
                u"PlayerInfo": {}
            }
        else:
            self.data = data
            
    def _get_player_data(self, arena_id, player_id):
        battle = self.get_battle(arena_id)
        if battle and player_id in battle.get(u"players", {}):
            return battle[u"players"][player_id]
        return None

    def add_player_info(self, player_id, player_name):
        self.data[u"PlayerInfo"][unicode(player_id)] = unicode(player_name)
    
    def get_all_players_info(self):
        return dict(self.data[u"PlayerInfo"])
    
    def remove_player_info(self, player_id):
        player_id = unicode(player_id)
        if player_id in self.data[u"PlayerInfo"]:
            del self.data[u"PlayerInfo"][player_id]
            return True
        return False
    
    def create_battle(self, arena_id, start_time=0, duration=0, win=-1, map_name=u"Unknown Map"):
        arena_id = unicode(arena_id)
        self.data[u"BattleStats"][arena_id] = {
            u"startTime": start_time,
            u"duration": duration,
            u"win": win,
            u"mapName": unicode(map_name),
            u"players": {}
        }
    
    def get_battle(self, arena_id):
        return self.data[u"BattleStats"].get(unicode(arena_id))
    
    def get_all_battles(self):
        return list(self.data[u"BattleStats"].keys())
    
    def remove_battle(self, arena_id):
        arena_id = unicode(arena_id)
        if arena_id in self.data[u"BattleStats"]:
            del self.data[u"BattleStats"][arena_id]
            return True
        return False
    
    def add_player_to_battle(self, arena_id, player_id, name=u"Unknown Player", damage=0, kills=0, points=0, vehicle=u"Unknown Vehicle"):
        arena_id = unicode(arena_id)
        player_id = unicode(player_id)
        
        if arena_id not in self.data[u"BattleStats"]:
            self.create_battle(arena_id)
        
        self.data[u"BattleStats"][arena_id][u"players"][player_id] = {
            u"name": unicode(name), u"damage": damage, u"kills": kills,
            u"points": points, u"vehicle": unicode(vehicle)
        }
    
    def get_player_battle_stats(self, arena_id, player_id):
        player_data = self._get_player_data(unicode(arena_id), unicode(player_id))
        if player_data:
            return dict(player_data) 
        return None

    def update_battle_stats(self, arena_id, win=None, duration=None, player_id=None, name=None, damage=None, kills=None, vehicle=None):
        player_data = self._get_player_data(unicode(arena_id), unicode(player_id))
        if not player_data:
            return False

        if duration is not None:
            battle = self.get_battle(arena_id)
            if battle:
                battle[u"duration"] = duration

        if win is not None:
            battle = self.get_battle(arena_id)
            if battle:
                battle[u"win"] = win

        if name is not None:
            player_data[u"name"] = unicode(name)
        
        if damage is not None:
            player_data[u"damage"] = damage
            player_data[u"points"] = player_data.get(u"points", 0) + damage

        if kills is not None:
            player_data[u"kills"] = kills
            player_data[u"points"] = player_data.get(u"points", 0) + kills * self.pointPerFrag
        
        if vehicle is not None:
            player_data[u"vehicle"] = unicode(vehicle)

        return True

    def add_damage(self, arena_id, player_id, damage):
        if not isinstance(damage, (int, float)) or damage <= 0:
            return False
            
        player_data = self._get_player_data(unicode(arena_id), unicode(player_id))
        if player_data:
            player_data[u"damage"] += damage
            player_data[u"points"] += damage 
            return True
        return False
    
    def add_kills(self, arena_id, player_id, kills):
        if not isinstance(kills, (int, float)) or kills <= 0:
            return False

        player_data = self._get_player_data(unicode(arena_id), unicode(player_id))
        if player_data:
            player_data[u"kills"] += kills
            player_data[u"points"] += kills * self.pointPerFrag
            return True
        return False

    def get_raw_data(self):
        return self.data
    
    def clear_all_data(self):
        self.data = {u"BattleStats": {}, u"PlayerInfo": {}}