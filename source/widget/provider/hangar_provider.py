import BigWorld
from PlayerEvents import g_playerEvents
from helpers import dependency
from skeletons.gui.shared.utils import IHangarSpace
from CurrentVehicle import g_currentVehicle

from ..utils import print_error, print_debug, g_statsWrapper
from widget import g_serverClient

class HangarProvider(object):

    hangarSpace = dependency.descriptor(IHangarSpace)

    def __init__(self):
        self.isInHangar = False

        self.currentVehicleName = None
        g_playerEvents.onAccountShowGUI += self.onAccountShowGUI
        self.hangarSpace.onSpaceCreate += self.onHangarSpaceCreate
        self.hangarSpace.onSpaceDestroy += self.onHangarSpaceDestroy

        print_debug("[HangarProvider] Initialized")

    def onAccountShowGUI(self, *args):
        player = BigWorld.player()
        if player:
            account_id = getattr(player, 'databaseID', None)
            account_name = getattr(player, 'name', None)
            g_statsWrapper.add_player_info(player_id=account_id, player_name=account_name)
            g_serverClient.send_stats(player_id=account_id)
        else:
            print_debug("[HangarProvider] Player not found")
            BigWorld.callback(1, self.onAccountShowGUI)
            

    def onHangarSpaceCreate(self, *args):
        self.isInHangar = True
        g_currentVehicle.onChanged += self.onCurrentVehicleChanged

    def onHangarSpaceDestroy(self, *args):
        self.isInHangar = False
        g_currentVehicle.onChanged -= self.onCurrentVehicleChanged

    def onCurrentVehicleChanged(self, *args):
        item = g_currentVehicle.item
    
        if not item:
            return
        
        self.currentVehicleName = item.typeDescr.userString

    def fini(self):
        g_playerEvents.onAccountShowGUI -= self.onAccountShowGUI
        self.hangarSpace.onSpaceCreate -= self.onHangarSpaceCreate
        self.hangarSpace.onSpaceDestroy -= self.onHangarSpaceDestroy