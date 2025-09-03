# -*- coding: utf-8 -*-
from .config_param_types import CheckboxParameter, TextInputParameter, RadioButtonGroupParameter, OptionItem
from .translations import Translator

class ConfigParams(object):    
    def __init__(self):
        self.enabled = CheckboxParameter(
            ['enabled'], 
            defaultValue=True
        )

        self.tournamentType = RadioButtonGroupParameter(
            ['tournamentType'],
            defaultValue='platoon',
            options=[
                OptionItem('platoon', 'platoon', Translator.TOURNAMENT_TYPE_OPTION_PLATOON),
                OptionItem('solo', 'solo', Translator.TOURNAMENT_TYPE_OPTION_SOLO)
            ]
)

        self.apiKey = TextInputParameter(
            ['apiKey'],
            defaultValue=u'dev-test',
            maxLength=10
        )

    def items(self):
        result = {}
        for attr_name in dir(self):
            if not attr_name.startswith('_') and attr_name != 'items':
                try:
                    attr = getattr(self, attr_name)
                    if hasattr(attr, 'tokenName') and hasattr(attr, 'defaultValue'):
                        result[attr.tokenName] = attr
                except Exception:
                    continue
        return result