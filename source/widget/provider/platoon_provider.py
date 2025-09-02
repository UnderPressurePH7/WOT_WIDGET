import BigWorld
from PlayerEvents import g_playerEvents
from helpers import dependency
from skeletons.gui.game_control import IPlatoonController
from items import vehicles as vehiclesUtils
from skeletons.gui.shared.utils import IHangarSpace

from ..utils import print_error, print_debug


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

    def updatePlatoonInfo(self):
        try:
            print_debug("[PlatoonProvider] updatePlatoonInfo called")
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