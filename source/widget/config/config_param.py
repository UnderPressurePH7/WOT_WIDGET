# -*- coding: utf-8 -*-
from .config_param_types import PARAM_REGISTRY, Param


class ConfigParams(object):
    
    def __init__(self):
        self.enabled = Param(['enabled'], defaultValue=True)
       

    @staticmethod
    def items():
        return PARAM_REGISTRY
