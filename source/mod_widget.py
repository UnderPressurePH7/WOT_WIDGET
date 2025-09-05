from widget.provider import initialize_providers, finalize_providers
from widget.utils import print_error, print_log

__version__ = "0.0.2" 
__author__ = "Under_Pressure"
__copyright__ = "Copyright 2025, Under_Pressure"
__mod_name__ = "Widget"


def init():
    try:
        print_log('MOD {} START LOADING: v{}'. format(__mod_name__, __version__))
        initialize_providers()
    except Exception as e:
        print_error("Error initializing providers: {}".format(e))

def fini():
    try:
        print_log('MOD {} START FINALIZING'.format(__mod_name__))
        finalize_providers()
    except Exception as e:
        print_error("Error finalizing providers: {}".format(e))