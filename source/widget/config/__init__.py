import BigWorld
from .config_template import Template
from .config_param import ConfigParams
from .config import Config

__all__ = [
    'g_configParams',
    'g_configTemplate',
    'g_config'
]

g_configParams = ConfigParams()
g_configTemplate = Template(g_configParams)
g_config = Config(g_configParams, g_configTemplate)

