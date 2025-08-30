# -*- coding: utf-8 -*-
from .utils import print_error

class StatsWrapper(object):
    
    def __init__(self, data=None):
        if data is None:
            self.data = {
                u"BattleStats": {},
                u"PlayerInfo": {}
            }
        else:
            self.data = data
    
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
        arena_id = unicode(arena_id)
        return self.data[u"BattleStats"].get(arena_id)
    
    def get_all_battles(self):
        return list(self.data[u"BattleStats"].keys())
    
    def remove_battle(self, arena_id):
        arena_id = unicode(arena_id)
        if arena_id in self.data[u"BattleStats"]:
            del self.data[u"BattleStats"][arena_id]
            return True
        return False
    
    def set_battle_info(self, arena_id, start_time=None, duration=None, win=None, map_name=None):
        arena_id = unicode(arena_id)
        if arena_id not in self.data[u"BattleStats"]:
            self.create_battle(arena_id)
        
        battle = self.data[u"BattleStats"][arena_id]
        if start_time is not None:
            battle[u"startTime"] = start_time
        if duration is not None:
            battle[u"duration"] = duration
        if win is not None:
            battle[u"win"] = win
        if map_name is not None:
            battle[u"mapName"] = unicode(map_name)
    
    def get_battle_info(self, arena_id):
        arena_id = unicode(arena_id)
        battle = self.get_battle(arena_id)
        if battle:
            return {
                u"startTime": battle[u"startTime"],
                u"duration": battle[u"duration"],
                u"win": battle[u"win"],
                u"mapName": battle[u"mapName"]
            }
        return None

    def add_player_to_battle(self, arena_id, player_id, name=u"Unknown Player", damage=0, kills=0, points=0, vehicle=u"Unknown Vehicle"):
        arena_id = unicode(arena_id)
        player_id = unicode(player_id)
        
        if arena_id not in self.data[u"BattleStats"]:
            self.create_battle(arena_id)
        
        self.data[u"BattleStats"][arena_id][u"players"][player_id] = {
            u"name": unicode(name),
            u"damage": damage,
            u"kills": kills,
            u"points": points,
            u"vehicle": unicode(vehicle)
        }
    
    def get_player_battle_stats(self, arena_id, player_id):
        arena_id = (arena_id)
        player_id = unicode(player_id)
        
        battle = self.get_battle(arena_id)
        if battle and player_id in battle[u"players"]:
            return dict(battle[u"players"][player_id])
        return None
    
    def update_player_battle_stats(self, arena_id, player_id, damage=None, kills=None, points=None, vehicle=None):
        arena_id = unicode(arena_id)
        player_id = unicode(player_id)
        
        if arena_id not in self.data[u"BattleStats"] or player_id not in self.data[u"BattleStats"][arena_id][u"players"]:
            self.add_player_to_battle(arena_id, player_id)
        
        player_data = self.data[u"BattleStats"][arena_id][u"players"][player_id]
        
        if damage is not None:
            player_data[u"damage"] = damage
        if kills is not None:
            player_data[u"kills"] = kills
        if points is not None:
            player_data[u"points"] = points
        if vehicle is not None:
            player_data[u"vehicle"] = unicode(vehicle)
    
    
    def remove_player_from_battle(self, arena_id, player_id):
        arena_id = unicode(arena_id)
        player_id = unicode(player_id)
        
        battle = self.get_battle(arena_id)
        if battle and player_id in battle[u"players"]:
            del battle[u"players"][player_id]
            return True
        return False
    
    def add_damage(self, arena_id, player_id, damage):
        current_stats = self.get_player_battle_stats(arena_id, player_id)
        if current_stats:
            new_damage = current_stats[u"damage"] + damage
            self.update_player_battle_stats(arena_id, player_id, damage=new_damage)
    
    def add_kills(self, arena_id, player_id, kills):
        current_stats = self.get_player_battle_stats(arena_id, player_id)
        if current_stats:
            new_kills = current_stats[u"kills"] + kills
            self.update_player_battle_stats(arena_id, player_id, kills=new_kills)
    
    def add_points(self, arena_id, player_id, points):
        current_stats = self.get_player_battle_stats(arena_id, player_id)
        if current_stats:
            new_points = current_stats[u"points"] + points
            self.update_player_battle_stats(arena_id, player_id, points=new_points)

    def get_raw_data(self):
        return self.data
    
    def clear_all_data(self):
        self.data = {
            u"BattleStats": {},
            u"PlayerInfo": {}
        }

g_statsWrapper = StatsWrapper()