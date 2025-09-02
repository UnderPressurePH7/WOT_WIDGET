import BigWorld
from PlayerEvents import g_playerEvents
import BattleReplay
from items import vehicles
from ..server_connect import g_serverClient
from ..utils import print_error, print_debug, g_statsWrapper


class BattleResultsProvider(object):
    def __init__(self):
        self.results_cache = []

        g_playerEvents.onBattleResultsReceived += self.onBattleResultsReceived
        BigWorld.callback(1.0, self.checkResultsCache)
        print_debug("[BattleResultsProvider] Initialized")

    def setArenaUniqueID(self, arenaUniqueID):
        if arenaUniqueID not in self.results_cache:
            self.results_cache.append(arenaUniqueID)

    def checkResultsCache(self):
        BigWorld.callback(1.0, self.checkResultsCache)

        if not hasattr(BigWorld.player(), 'battleResultsCache'):
            return

        for arenaUniqueID in list(self.results_cache):
            try:
                BigWorld.player().battleResultsCache.get(
                    arenaUniqueID,
                    lambda code, results, arenaUniqueID=arenaUniqueID: self.onCachedResults(code, results, arenaUniqueID)
                )
            except Exception as e:
                print_error("[BattleResultsProvider] battleResultsCache error: {}".format(e))

    def onBattleResultsReceived(self, isPlayerVehicle, results):
        print_debug("[BattleResultsProvider] onBattleResultsReceived called.")
        if not isPlayerVehicle or BattleReplay.isPlaying():
            return
        self.processBattleResults(results)

    def onCachedResults(self, code, results, arenaUniqueID):
        if code > 0 and results:
            self.processBattleResults(results)
            if arenaUniqueID in self.results_cache:
                self.results_cache.remove(arenaUniqueID)

    def processBattleResults(self, results):
        try:
            arenaUniqueID = results.get('arenaUniqueID')
            common = results.get('common', {})
            
            personal = results.get('personal', {})
            if 'avatar' in personal:
                personal = personal['avatar']
            personal_accountDBID = personal.get('accountDBID', 0)

            vehicles_data = results.get('vehicles', {})
            players = results.get('players', {})
            duration = common.get('duration', 0)
            winner_team = common.get('winnerTeam', 0)
            player_team = personal.get('team', 0)
           

            if winner_team == 0:
                battle_result = 2
            elif winner_team == player_team:
                battle_result = 1  
            else:
                battle_result = 0
            
            print_debug("[BattleResultsProvider] Processing results for ArenaUniqueID: {}, Duration: {}, PlayerTeam: {}, WinnerTeam: {}, Result: {}".format(
                    arenaUniqueID, duration, player_team, winner_team, battle_result
                ))

            for vehicleID, vehicle_info in vehicles_data.items():
                if not vehicle_info:
                    continue

                if isinstance(vehicle_info, list):
                    vehicle = vehicle_info[0] if vehicle_info else None
                else:
                    vehicle = vehicle_info

                if not vehicle:
                    continue

                accountDBID = vehicle.get('accountDBID', 0)
                if accountDBID != personal_accountDBID:
                    continue    

                vehicle_type = vehicles.getVehicleType(vehicle.get('typeCompDescr', 0))
                damage = vehicle.get('damageDealt', 0)
                kills = vehicle.get('kills', 0)
                vehicle_name = vehicle_type.shortUserString

                player_name = players.get(accountDBID, {}).get('realName', 'Unknown')

                g_statsWrapper.update_battle_stats(arena_id=arenaUniqueID, player_id=accountDBID, damage=damage, kills=kills, vehicle=vehicle_name, win=battle_result, duration=duration)
            g_serverClient.send_stats(player_id=accountDBID)

            self.results_cache.remove(arenaUniqueID) if arenaUniqueID in self.results_cache else None
        except Exception as e:
            print_error('[BattleResultsProvider] Error processing battle results: {0}'.format(str(e)))

    def fini(self):
        g_playerEvents.onBattleResultsReceived -= self.onBattleResultsReceived
        self.results_cache = []
        print_debug("[BattleResultsProvider] Finalized.")
