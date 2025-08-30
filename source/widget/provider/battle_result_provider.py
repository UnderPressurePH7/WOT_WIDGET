import BigWorld
from PlayerEvents import g_playerEvents
import BattleReplay
from items import vehicles
from ..stats_wraper import g_statsWrapper
from ..server_sync_client import g_serverSyncClient
from ..utils import print_error, print_debug

class BattleResultsProvider():

    def __init__(self):
        self.playerID = None
        self.results_cache = []
        self.battleStats = {}
        g_playerEvents.onBattleResultsReceived += self.onBattleResultsReceived
        BigWorld.callback(1.0, self.checkResultsCache)
        print_debug("[BattleResultsProvider] initialized.")

    def checkResultsCache(self):
        BigWorld.callback(1.0, self.checkResultsCache)
        if not hasattr(BigWorld.player(), 'battleResultsCache'):
            return
        for arenaUniqueID in self.results_cache:
            try:
                BigWorld.player().battleResultsCache.get(arenaUniqueID, lambda code, results: self.onCachedResults(code, results, arenaUniqueID))
            except Exception as e:
                print_error("Failed to get cached results for arena {}: {}".format(arenaUniqueID, e))

    def onBattleResultsReceived(self, isPlayerVehicle, results):
        if not isPlayerVehicle or BattleReplay.isPlaying():
            return
        print_debug("[BattleResultsProvider] onBattleResultsReceived called.")
        self.processBattleResults(results)

    def onCachedResults(self, code, results, arenaUniqueID):
        print_debug("[BattleResultsProvider] onCachedResults called with code: {}, arenaUniqueID: {}".format(code, arenaUniqueID))
        if code > 0 and results:
            self.processBattleResults(results)
            if arenaUniqueID in self.results_cache:
                self.results_cache.remove(arenaUniqueID)

    def processBattleResults(self, results):
        try:
            print_debug("[BattleResultsProvider] Processing battle results.{}".format(results))
            self.playerID = results.get('personal', {}).get('accountDBID', None)
            arenaUniqueID = results.get('arenaUniqueID', None)
            common = results.get('common', {})
            duration = common.get('duration', 0)   
            personal = results.get('personal', {})
            if 'avatar' in personal:
                personal = personal['avatar']
            vehicles_data = results.get('vehicles', {})
            players = results.get('players', {})
            winner_team = common.get('winnerTeam', 0)
            player_team = personal.get('team', 0)
            battle_result = 1 if winner_team == player_team else (0 if winner_team else 2)

            player_names = {}
            for player_id, player_data in players.items():
                player_names[player_id] = {'name': player_data.get('realName', 'Unknown'),
                 'prebattleID': player_data.get('prebattleID', 0),
                 'accountDBID': player_data.get('accountDBID', 0)}

            for vehicleID, vehicle_info in vehicles_data.items():
                if not vehicle_info:
                    continue
                vehicle = vehicle_info[0]
                accountDBID = vehicle.get('accountDBID', 0)
                if accountDBID != self.playerID:
                    continue
                vehicle_type = vehicles.getVehicleType(vehicle.get('typeCompDescr', 0))

                damage = vehicle.get('damageDealt', 0)
                kills = vehicle.get('kills', 0)
                points = damage + kills * 400
                vehicle = vehicle_type.shortUserString
                g_statsWrapper.set_battle_info(arena_id=arenaUniqueID, duration=duration, win=battle_result)
                g_statsWrapper.update_player_battle_stats(arena_id=arenaUniqueID, player_id=self.playerID, damage=damage, kills=kills, points=points, vehicle=vehicle)
                g_serverSyncClient.send_stats(player_id=self.playerID)
            print_debug("[BattleResultsProvider] Processed battle results for player ID: {}, Arena ID: {}".format(self.playerID, arenaUniqueID))
        except Exception as e:
            print_error("[BattleResultsProvider] Error processing battle results: {0}".format(str(e)))


    def fini(self):
        g_playerEvents.onBattleResultsReceived -= self.onBattleResultsReceived