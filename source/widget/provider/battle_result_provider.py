import BigWorld
import BattleReplay
from PlayerEvents import g_playerEvents
from items import vehicles

from ..server import g_serverManager
from ..settings import g_config
from ..utils import print_error, print_debug, g_statsWrapper


class BattleResultsProvider(object):
    def __init__(self):
        self.inBattle = False
        self.arenaUniqueIDs = []

        g_playerEvents.onBattleResultsReceived += self.onBattleResultsReceived
        self.battleResultsCacheLoop()

        print_debug("[BattleResultsProvider] Initialized")

    def setInBattle(self, inBattle):
        self.inBattle = inBattle

    def setArenaUniqueID(self, arenaUniqueID):
        if arenaUniqueID not in self.arenaUniqueIDs:
            self.arenaUniqueIDs.append(arenaUniqueID)

    def battleResultsCacheLoop(self):
        BigWorld.callback(1.0, self.battleResultsCacheLoop)

        def resultCallback(code, results):
            if code > 0 and results:
                self.processBattleResults(results)

        if len(self.arenaUniqueIDs) > 0:
            arenaID = self.arenaUniqueIDs.pop(0)
            self.arenaUniqueIDs.append(arenaID)
            try:
                BigWorld.player().battleResultsCache.get(arenaID, resultCallback)
            except Exception as e:
                print_error("[BattleResultsProvider] battleResultsCache error: {}".format(e))

    def onBattleResultsReceived(self, isPlayerVehicle, results):
        try:
            if not g_config.configParams.enabled.value:
                print_debug("[BattleResultsProvider] Mod disabled, skipping battle session start")
                return
        except ImportError:
            print_debug("[BattleResultsProvider] ImportError occurred")
            return

        if not isPlayerVehicle or BattleReplay.isPlaying():
            return

        print_debug("[BattleResultsProvider] onBattleResultsReceived called.")
        self.processBattleResults(results)

    def processBattleResults(self, results):
        try:
            arenaUniqueID = results.get('arenaUniqueID')
            common = results.get('common', {})

            if arenaUniqueID not in self.arenaUniqueIDs:
                print_debug("[BattleResultsProvider] Unknown arenaUniqueID: {}".format(arenaUniqueID))
                return

            while arenaUniqueID in self.arenaUniqueIDs:
                self.arenaUniqueIDs.remove(arenaUniqueID)

            guiType = common.get('guiType', None)
            print_debug("[BattleResultsProvider] guiType: {}".format(guiType))
            if guiType != 1:
                print_debug("[BattleResultsProvider] Unsupported game mode (guiType: {}), skipping".format(guiType))
                return

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

            print_debug("[BattleResultsProvider] Processing results for ArenaID: {}, Duration: {}, PlayerTeam: {}, WinnerTeam: {}, Result: {}".format(
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
                points = damage + (kills * g_statsWrapper.pointPerFrag)
                vehicle_name = vehicle_type.shortUserString
                player_name = players.get(accountDBID, {}).get('realName', 'Unknown')

                g_statsWrapper.update_battle_stats(
                    arena_id=arenaUniqueID, player_id=accountDBID, points=points,
                    damage=damage, kills=kills, vehicle=vehicle_name,
                    win=battle_result, duration=duration
                )

            if self.inBattle:
                print_debug("[BattleResultsProvider] Already in battle, skipping sending stats.")
                return

            result = g_serverManager.send_stats(player_id=accountDBID)
            if result:
                g_statsWrapper.clear_current_battle_data(arena_id=arenaUniqueID)
                print_debug("[BattleResultsProvider] Battle stats sent successfully for PlayerID: {}".format(accountDBID))
            else:
                print_debug("[BattleResultsProvider] Failed to send stats for PlayerID: {}".format(accountDBID))

        except Exception as e:
            print_error("[BattleResultsProvider] Error processing results: {}".format(e))

    def fini(self):
        g_playerEvents.onBattleResultsReceived -= self.onBattleResultsReceived
        self.arenaUniqueIDs = []
        print_debug("[BattleResultsProvider] Finalized")
