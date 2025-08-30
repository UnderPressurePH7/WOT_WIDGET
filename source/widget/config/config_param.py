# -*- coding: utf-8 -*-
from widget.config.config_param_types import BooleanParam, OptionsParam, ColorParam, ListParam, Option


class ConfigParams(object):
    def __init__(self):
        self.enabled = BooleanParam(['enabled'], defaultValue=True)
       

g_configParams = ConfigParams()
