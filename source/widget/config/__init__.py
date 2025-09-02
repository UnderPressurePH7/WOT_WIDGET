import BigWorld
from .config_param import ConfigParams
from .config import Config

__all__ = [
    'initialize_config',
    'get_config_params',
    'is_config_initialized'
]

g_configParams = None
g_config = None

def initialize_config():
    global g_configParams, g_config
    g_configParams = ConfigParams()
    g_config = Config(g_configParams)

def get_config_params():
    return g_configParams

def is_config_initialized():
    return g_configParams is not None