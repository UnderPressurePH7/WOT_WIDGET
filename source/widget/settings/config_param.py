# -*- coding: utf-8 -*-
from .config_param_types import PARAM_REGISTRY, BaseParameter, CheckboxParameter, TextInputParameter


class ConfigParams(object):    
    def __init__(self):
        self.enabled = CheckboxParameter(
            ['enabled'], 
            defaultValue=True
        )

        self.apiKey = TextInputParameter(
            ['apiKey'],
            defaultValue=u'dev-test',
            maxLength=100
        )

    def items(self):
        result = {}
        for attr_name in dir(self):
            if not attr_name.startswith('_') and not callable(getattr(self, attr_name)):
                attr = getattr(self, attr_name)
                if isinstance(attr, BaseParameter):
                    result[attr.tokenName] = attr
        return result

    @staticmethod
    def get_registry():
        return PARAM_REGISTRY