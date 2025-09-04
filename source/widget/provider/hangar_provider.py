from unittest import result
import BigWorld
from PlayerEvents import g_playerEvents
from helpers import dependency
from skeletons.gui.shared.utils import IHangarSpace
from CurrentVehicle import g_currentVehicle

from ..utils import print_error, print_debug, g_statsWrapper

class HangarProvider(object):

    hangarSpace = dependency.descriptor(IHangarSpace)

    def __init__(self):
        self.isInHangar = False
        self.account_id = None
        self.account_name = None

        self.currentVehicleName = None
        g_playerEvents.onAccountShowGUI += self.onAccountShowGUI
        self.hangarSpace.onSpaceCreate += self.onHangarSpaceCreate
        self.hangarSpace.onSpaceDestroy += self.onHangarSpaceDestroy

        print_debug("[HangarProvider] Initialized")

    def onAccountShowGUI(self, *args):
        try:
            from ..settings import g_config
            if not g_config.configParams.enabled.value:
                print_debug("[HangarProvider] Mod disabled, skipping battle session start")
                return
        except ImportError:
            print_debug("[HangarProvider] ImportError occurred")
            return
        print_debug("[HangarProvider] Account GUI shown")
        player = BigWorld.player()
        if player:
            self.account_id = getattr(player, 'databaseID', None)
            self.account_name = getattr(player, 'name', None)
            BigWorld.callback(5.0, self.onSendPlayerInfo)
        else:
            print_debug("[HangarProvider] Player not found")
            BigWorld.callback(1, self.onAccountShowGUI)

    def onSendPlayerInfo(self):
        try:
            from ..server import g_serverManager
            print_debug("[HangarProvider] Sending player info to server for account ID: {}".format(self.account_id))
            g_statsWrapper.add_player_info(player_id=self.account_id, player_name=self.account_name)

            result = g_serverManager.send_stats(player_id=self.account_id)
            if result:
                print_debug("[HangarProvider] Player info sent successfully for account ID: {}".format(self.account_id))


        except ImportError:
            print_debug("[HangarProvider] Config not available, using default API key")

    def onHangarSpaceCreate(self, *args):
        self.isInHangar = True
        print_debug("[HangarProvider] Entered hangar")
        g_currentVehicle.onChanged += self.onCurrentVehicleChanged

    def onHangarSpaceDestroy(self, *args):
        self.isInHangar = False
        print_debug("[HangarProvider] Left hangar")
        g_currentVehicle.onChanged -= self.onCurrentVehicleChanged

    def onCurrentVehicleChanged(self, *args):
        item = g_currentVehicle.item
    
        if not item:
            return
        self.currentVehicleName = item.typeDescr.userString
        self.onSendPlayerInfo()
        print_debug("[HangarProvider] Current vehicle changed to: {}".format(self.currentVehicleName))

        
    def fini(self):
        g_playerEvents.onAccountShowGUI -= self.onAccountShowGUI
        self.hangarSpace.onSpaceCreate -= self.onHangarSpaceCreate
        self.hangarSpace.onSpaceDestroy -= self.onHangarSpaceDestroy