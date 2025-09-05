# -*- coding: utf-8 -*-
class Template(object):
    def __init__(self, config_params):
        self.config_params = config_params
        self.mod_display_name = None
        self.column1_items = []
        self.column2_items = []

    def _default_enabled(self):
        enabled_param = getattr(self.config_params, 'enabled', None)
        return enabled_param.defaultValue if enabled_param else True

    def set_mod_display_name(self, name):
        self.mod_display_name = unicode(name)
        return self
    
    def add_to_column1(self, item):
        if isinstance(item, dict):
            self.column1_items.append(item)
        return self
    
    def add_to_column2(self, item):
        if isinstance(item, dict):
            self.column2_items.append(item)
        return self

    def add_parameter_to_column1(self, param_name, value, header=None, body=None, note=None, attention=None):
        if hasattr(self.config_params, param_name):
            param = getattr(self.config_params, param_name)
            if hasattr(param, 'renderParam'):
                rendered_param = param.renderParam(
                    header=header or param.name.title(),
                    value=value,
                    body=body,
                    note=note,
                    attention=attention
                )
                self.add_to_column1(rendered_param)
        return self

    def add_parameter_to_column2(self, param_name, value, header=None, body=None, note=None, attention=None):
        if hasattr(self.config_params, param_name):
            param = getattr(self.config_params, param_name)
            if hasattr(param, 'renderParam'):
                rendered_param = param.renderParam(
                    header=header or param.name.title(),
                    value=value,
                    body=body,
                    note=note,
                    attention=attention
                )
                self.add_to_column2(rendered_param)
        return self
    
    def clear_columns(self):
        self.column1_items = []
        self.column2_items = []
        return self
    
    def generateTemplate(self):  
        template = {
            'modDisplayName': self.mod_display_name,
            'enabled': self._default_enabled(),
            'column1': list(self.column1_items),
            'column2': list(self.column2_items)
        }
        
        return template
    
