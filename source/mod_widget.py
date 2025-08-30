from widget.provider.platoon_provider import PlatoonProvider
from widget.provider.hangar_provider import HangarProvider
from widget.provider.battle_provider import BattleProvider
from widget.provider.battle_result_provider import BattleResultsProvider

from widget.utils import print_error, print_debug, print_log

__version__ = "0.0.1" 
__author__ = "Under_Pressure"
__copyright__ = "Copyright 2025, Under_Pressure"
__mod_name__ = "Widget"

g_platoonProvider = None
g_hangarProvider = None
g_battleProvider = None
g_battleResultsProvider = None

def init():
    global g_platoonProvider, g_hangarProvider, g_battleProvider, g_battleResultsProvider
    try:
        print_log('MOD {} START LOADING: v{}'. format(__mod_name__, __version__))
        g_platoonProvider = PlatoonProvider()
        g_hangarProvider = HangarProvider()
        g_battleProvider = BattleProvider()
        g_battleResultsProvider = BattleResultsProvider()
        print_debug("Providers initialized successfully.")
    except Exception as e:
        print_error("Error initializing providers: {}".format(e))

def fini():
    global g_platoonProvider, g_hangarProvider, g_battleProvider, g_battleResultsProvider
    try:
        print_log('MOD {} START FINALIZING'.format(__mod_name__))
        if g_platoonProvider:
            g_platoonProvider.fini()
        if g_hangarProvider:
            g_hangarProvider.fini()
        if g_battleProvider:
            g_battleProvider.fini()
        if g_battleResultsProvider:
            g_battleResultsProvider.fini()
        print_debug("Providers finalized successfully.")
    except Exception as e:
        print_error("Error finalizing providers: {}".format(e))