import BigWorld
from .platoon_provider import PlatoonProvider
from .hangar_provider import HangarProvider
from .battle_provider import BattleProvider
from .battle_result_provider import BattleResultsProvider
from ..utils import print_error

__all__ = [
    'initialize_providers',
    'finalize_providers',
]
g_battleProvider = None
g_platoonProvider = None
g_hangarProvider = None
g_battleResultsProvider = None

def initialize_providers():
    global g_platoonProvider, g_hangarProvider, g_battleProvider, g_battleResultsProvider
    try:
        g_platoonProvider = PlatoonProvider()
        g_hangarProvider = HangarProvider()
        g_battleResultsProvider = BattleResultsProvider()
        g_battleProvider = BattleProvider(g_battleResultsProvider)

    except Exception as e:
        print_error("Error initializing providers: {}".format(e))


def finalize_providers():
    global g_platoonProvider, g_hangarProvider, g_battleProvider, g_battleResultsProvider
    try:
        if g_platoonProvider:
            g_platoonProvider.fini()
        if g_hangarProvider:
            g_hangarProvider.fini()
        if g_battleProvider:
            g_battleProvider.fini()
        if g_battleResultsProvider:
            g_battleResultsProvider.fini()
    except Exception as e:
        print_error("Error finalizing providers: {}".format(e))