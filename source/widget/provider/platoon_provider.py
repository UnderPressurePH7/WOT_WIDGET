import BigWorld
from PlayerEvents import g_playerEvents
from helpers import dependency
from skeletons.gui.game_control import IPlatoonController
from items import vehicles as vehiclesUtils
from skeletons.gui.shared.utils import IHangarSpace

from ..utils import print_error, print_debug, g_statsWrapper

class PlatoonProvider():

    platoon = dependency.descriptor(IPlatoonController)
    hangarSpace = dependency.descriptor(IHangarSpace)

    def __init__(self):

        self.isInPlatoon = False
        self.maxSlotCount = 0
        self.platoonMembers = []
        self.commanderID = None


        self.hangarSpace.onSpaceCreate += self.onHangarSpaceCreate
        
        self.platoon.onMembersUpdate += self.onPlatoonUpdated
        self.platoon.onPlatoonTankVisualizationChanged += self.onPlatoonUpdated
        self.platoon.onPlatoonTankUpdated += self.onPlatoonUpdated
        self.platoon.onPlatoonTankRemove += self.onPlatoonUpdated

        print_debug("[PlatoonProvider] Initialized")


    def onHangarSpaceCreate(self, *args):
        print_debug("[PlatoonProvider] Hangar space created")
        BigWorld.callback(1.0, self.updatePlatoonInfo)

    def onPlatoonUpdated(self, *args):
        print_debug("[PlatoonProvider] Platoon updated")
        BigWorld.callback(1.0, self.updatePlatoonInfo)


    def onSendPlayerInfo(self):
        try:
            from ..settings import g_config
            from ..server import g_serverClient, ServerClient

            player = BigWorld.player()
            if player:
                account_id = getattr(player, 'databaseID', None)
                account_name = getattr(player, 'name', None)

            print_debug("[PlatoonProvider] Sending player info to server for account ID: {}".format(account_id))
            
            g_statsWrapper.add_player_info(player_id=account_id, player_name=account_name)

            api_key = g_config.get_api_key()
            if api_key != g_serverClient.access_key:
                print_debug("[PlatoonProvider] API key mismatch, reinitializing server client")
                g_serverClient.disconnect()
                g_serverClient = None
                g_serverClient = ServerClient(api_key)

            print_debug("[PlatoonProvider] API key set to: {}".format(api_key))
            g_serverClient.send_stats(player_id=account_id)
        except ImportError:
            print_debug("[PlatoonProvider] Config not available, using default API key")


    def updatePlatoonInfo(self):
        try:
            print_debug("[PlatoonProvider] updatePlatoonInfo called")
            self.onSendPlayerInfo()
            self.isInPlatoon = self.platoon.isInPlatoon()
            self.maxSlotCount = self.platoon.getMaxSlotCount()

            self.platoonMembers = []
            self.commanderID = None
            
            slots = self.platoon.getPlatoonSlotsData()

            for slot in slots:
                player = slot.get('player')
                if player is None:
                    self.platoonMembers.append(None)
                    continue
                if player.get('isCommander'):
                    self.commanderID = player.get('accountDBID')

                vehicleDescr = slot.get('selectedVehicle')
                vehicle = vehiclesUtils.getItemByCompactDescr(vehicleDescr.get('intCD')) if vehicleDescr else None
                self.platoonMembers.append((player.get('accountDBID'), player.get('name'), vehicle))
        except Exception as e:
            print_error("[PlatoonProvider] Error updating platoon info: {}".format(e))


    def fini(self):
        self.hangarSpace.onSpaceCreate -= self.onHangarSpaceCreate

        self.platoon.onMembersUpdate -= self.onPlatoonUpdated
        self.platoon.onPlatoonTankVisualizationChanged -= self.onPlatoonUpdated
        self.platoon.onPlatoonTankUpdated -= self.onPlatoonUpdated
        self.platoon.onPlatoonTankRemove -= self.onPlatoonUpdated