# -*- coding: utf-8 -*-
from .config_param_types import CheckboxParameter, TextInputParameter, DropdownParameter, RadioButtonGroupParameter, OptionItem
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
                OptionItem('BB', 'BB', Translator.TOURNAMENT_TYPE_OPTION_BB)
            ]
)

        self.apiKey = TextInputParameter(
            ['apiKey'],
            defaultValue=u'dev-test',
            maxLength=10
        )

        self.chooseBlogger = DropdownParameter(
            ['chooseBlogger'],
            defaultValue='Palu4',
            options=[
                OptionItem('Palu4', 'Palu4', Translator.BLOGGER_PALU4),
                OptionItem('Vgosti', 'Vgosti', Translator.BLOGGER_VGOSTI),
                OptionItem('YKP_BOIH', 'YKP_BOIH', Translator.BLOGGER_YKP_BOIH),
                OptionItem('Bizzord', 'Bizzord', Translator.BLOGGER_BIZZORD)
            ]
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