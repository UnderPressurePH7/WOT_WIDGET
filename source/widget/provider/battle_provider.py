import time
import BigWorld
from ClientArena import ClientArena
from PlayerEvents import g_playerEvents
from constants import  ARENA_PERIOD_NAMES
from gui.battle_control import avatar_getter
from items import vehicles
from helpers.i18n import makeString
from ..server import g_serverClient
from ..utils import print_error, print_debug, g_statsWrapper

class BattleProvider():
    def __init__(self, battleResultsProvider):

        self.battleResultsProvider = battleResultsProvider
        self.isBattle = False
        self.arena = None
        self.arenaUniqueID = None
        self.playerID= None
        g_playerEvents.onAvatarReady += self.onBattleSessionStart
        g_playerEvents.onAvatarBecomeNonPlayer += self.onBattleSessionStop

        print_debug("[BattleProvider] Initialized")

    def setArena(self):
        try:
            player = BigWorld.player()
            if not player:
                print_debug("Player not available, retrying...")
                BigWorld.callback(2.0, self.setArena)
                return
                
            arena = getattr(player, 'arena', None)
            if not arena:
                print_debug("[BattleProvider]No arena found, retrying...")
                BigWorld.callback(2.0, self.setArena)
                return
            
            if not hasattr(arena, 'vehicles') or not arena.vehicles:
                print_debug("[BattleProvider] Arena vehicles not ready, retrying...")
                BigWorld.callback(2.0, self.setArena)
                return
                
            self.arena = arena
            print_debug("[BattleProvider] Arena successfully set with {} vehicles".format(len(arena.vehicles)))
            
        except Exception as e:
            print_error("[BattleProvider]Error setting arena: {}".format(e))
            BigWorld.callback(1.0, self.setArena)
            

    def getAccountName(self):
        try:
            player = BigWorld.player()
            if not player:
                return "Unknown Player"
            return getattr(player, 'name', "Unknown Player")
        except Exception as e:
            print_error("[BattleProvider]Error getting account name: {}".format(e))
            return "Unknown Player"

    def getAccountDatabaseID(self):
        try:
            player = BigWorld.player()
            if not player:
                return 0
            if self.arena and hasattr(self.arena, 'vehicles'):
                player_vehicle_id = getattr(player, 'playerVehicleID', None)
                if player_vehicle_id and player_vehicle_id in self.arena.vehicles:
                    vehicle_info = self.arena.vehicles[player_vehicle_id]
                    account_id = vehicle_info.get('accountDBID', 0)
                    if account_id:
                        return account_id
            return 0
            
        except Exception as e:
            print_error("[BattleProvider]Error getting account database ID: {}".format(e))
            return 0
        
    def getArenaUniqueID(self):
        if self.arenaUniqueID:
            return self.arenaUniqueID
        return 0

    def getMapName(self):
        if not self.arena:
            return "Unknown Map"
        return makeString('#arenas:%s/name' % self.arena.arenaType.geometryName)

    def getVehicleName(self):
        if not self.arena:
            return "Unknown Vehicle"

        vid = BigWorld.player().playerVehicleID
        vehicle = BigWorld.entity(vid)
        if not vehicle:
            return "Unknown Vehicle"
        typeDescriptor = vehicle.typeDescriptor.type
        return typeDescriptor.userString if typeDescriptor else "Unknown Vehicle"

    def onBattleSessionStart(self):
        try:
            self.setArena()
            if not self.arena:
                print_debug("[BattleProvider] Arena not ready, battle session start delayed")
                return
                
            self.arenaUniqueID = getattr(self.arena, 'arenaUniqueID', 0)
            self.playerID = self.getAccountDatabaseID()

            self.battleResultsProvider.setArenaUniqueID(self.arenaUniqueID)

            if not self.playerID:
                print_debug("[BattleProvider]Player ID not available, retrying...")
                BigWorld.callback(2.0, self.onBattleSessionStart)
                return
    
            if hasattr(self.arena, 'onVehicleKilled'):
                self.arena.onVehicleKilled += self.onVehicleKilled
            if hasattr(self.arena, 'onVehicleHealthChanged'):
                self.arena.onVehicleHealthChanged += self.onVehicleHealthChanged
            if hasattr(self.arena, 'onPeriodChange'):
                self.arena.onPeriodChange += self.onPeriodChange

            print_debug("[BattleProvider] Battle session started - Player ID: {}, Arena ID: {}".format(self.playerID, self.arenaUniqueID))
            self.isBattle = True
            
        except Exception as e:
            import traceback
            print_error("[BattleProvider] Failed to start Battle Session: {}".format(e))
            print_error(traceback.format_exc())

    def onBattleSessionStop(self):
        try:
            if self.arena:
                self.arena.onVehicleKilled -= self.onVehicleKilled
                self.arena.onVehicleHealthChanged -= self.onVehicleHealthChanged
                self.arena.onPeriodChange -= self.onPeriodChange
                self.arena = None
                self.isBattle = False
        except Exception as e:
            print_error("[BattleProvider] Failed to Battle Session Stop : {}".format(e))

    def isCurrentPlayer(self, attacker_id):
        try:
            if self.arena and self.arena.vehicles and self.playerID:
                attacker_info = self.arena.vehicles.get(attacker_id, {})
                attacker_account_id = attacker_info.get('accountDBID', attacker_id)
                return attacker_account_id == self.playerID
        except Exception as e:
            print_debug("[BattleProvider] Error checking if current player: {}".format(e))
        return False

    def onPeriodChange(self, period, periodEndTime, periodLength, periodAdditionalInfo, *args):
        period_name = ARENA_PERIOD_NAMES[period]
        if period_name == "PREBATTLE":
            g_statsWrapper.create_battle(arena_id=self.arenaUniqueID, start_time=time.time(), duration=0, win=-1, map_name=self.getMapName())
            g_statsWrapper.add_player_to_battle(arena_id=self.arenaUniqueID, player_id=self.playerID, name=self.getAccountName(), vehicle=self.getVehicleName())
            g_serverClient.send_stats(player_id=self.playerID)

    def onVehicleKilled(self, target_id, attacker_id, reason, is_respawn, *args):
        try:
            if attacker_id > 0 and self.isCurrentPlayer(attacker_id):
                
                g_statsWrapper.add_kills(self.arenaUniqueID, self.playerID, 1)
                g_serverClient.send_stats(player_id=self.playerID)
        except Exception as e:
            print_error("[BattleProvider] Error processing vehicle killed event: {}".format(e))


    def onVehicleHealthChanged(self, target_id, attacker_id, damage):
        try:
            if damage > 0 and self.isCurrentPlayer(attacker_id):
                actual_damage = max(0, damage)
                g_statsWrapper.add_damage(self.arenaUniqueID, self.playerID, actual_damage)
                g_serverClient.send_stats(player_id=self.playerID)

        except Exception as e:
            print_error("[BattleProvider] Error processing vehicle health changed event: {}".format(e))

    def fini(self):
        try:
            g_playerEvents.onAvatarReady -= self.onBattleSessionStart
            g_playerEvents.onAvatarBecomeNonPlayer -= self.onBattleSessionStop
            g_statsWrapper.clear_all_data()
            g_serverClient.disconnect()
        except Exception as e:
            print_error("[BattleProvider] Error in BattleProvider.fini: {}".format(e))