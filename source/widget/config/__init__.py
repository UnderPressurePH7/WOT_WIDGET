import BigWorld
from .config_param import ConfigParams
from .config import Config

__all__ = [
    'g_configParams',
    'g_config'
]

g_configParams = ConfigParams()
g_config = Config(g_configParams)

