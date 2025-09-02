# -*- coding: utf-8 -*-
import json
import os
from ..utils import print_error, print_debug

try:
    from gui.modsSettingsApi import g_modsSettingsApi   
except ImportError:
    print_error("Failed to import g_modsSettingsApi")


modLinkage = 'me.under-pressure.widget'

class Config(object):
    def __init__(self, configParams):
        self.configParams = configParams
        self.config_path = os.path.join('mods', 'configs', 'under_pressure', 'widget.json')
        self._ensure_config_exists()
        self.load_config()
        self._register_mod()

    def _ensure_config_exists(self):
        try:
            config_dir = os.path.dirname(self.config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                print_debug("Created config directory")

            if not os.path.exists(self.config_path):
                self._create_default_config()
        except Exception as e:
            print_error("Error ensuring config exists: {}".format(str(e)))

    def _create_default_config(self):
        try:
            config_data = {}
            for tokenName, param in self.configParams.items():
                config_data[tokenName] = param.defaultValue

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
            print_debug("Created default config file")
        except Exception as e:
            print_error("Error creating default config: {}".format(str(e)))

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)

                for tokenName, param in self.configParams.items():
                    if tokenName in config_data:
                        try:
                            param.jsonValue = config_data[tokenName]
                        except Exception as e:
                            print_error("Error loading parameter {}: {}".format(tokenName, str(e)))
                            param.value = param.defaultValue
                    else:
                        param.value = param.defaultValue

                print_debug("[Config] loaded successfully")
            else:
                print_debug("[Config] file not found, using defaults")
        except Exception as e:
            print_error("[Config] Error loading config: {}".format(str(e)))

    def save_config(self):
        try:
            config_data = {}
            for tokenName, param in self.configParams.items():
                config_data[tokenName] = param.jsonValue

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
            print_debug("[Config] saved successfully")
        except Exception as e:
            print_error("[Config] Error saving config:{}".format(str(e)))

            
    def _get_safe_msa_value(self, param):
        try:
            if hasattr(param, 'msaValue'):
                return param.msaValue
            else:
                return param.value
        except Exception as e:
            print_error("[Config] Error getting msaValue for : {}".format(str(e)))
            return param.defaultValue

    def _register_mod(self):
        try:
            template = {
                'modDisplayName': u'Віджет від Палича',
                'enabled': self.configParams.enabled.defaultMsaValue,
                'column1': [
                    {
                        'type': 'Label',
                        'text': u'Основні налаштування'
                    }
                ],
                'column2': [
                            {
                                'type': 'Label',
                                'text': u'Додаткові налаштування'
                            },
                           
                        ]
                    }

            g_modsSettingsApi.setModTemplate(modLinkage, template, self.on_settings_changed)
            print_debug("[Config] Mod template registered successfully using setModTemplate")
            
        except Exception as e:
            print_error("[Config] Error registering mod template: {}".format(str(e)))

    def on_settings_changed(self, linkage, newSettings):
        if linkage != modLinkage:
            return
        try:
            print_debug("[Config]MSA settings changed: %s" % str(newSettings))

            for tokenName, value in newSettings.items():
                if tokenName in self.configParams.items():
                    param = self.configParams.items()[tokenName]
                    if hasattr(param, 'fromMsaValue'):
                        param.value = param.fromMsaValue(value)
                    elif hasattr(param, 'msaValue'):
                        param.msaValue = value
                    else:
                        param.value = value
            self.save_config()
            
            self._notify_config_changed()

            print_debug("[Config] Settings updated successfully")
        except Exception as e:
            print_error("[Config] Error updating settings from MSA: {}".format(str(e)))

    def _notify_config_changed(self):
        try:

            print_debug("[Config] Config change notification sent")
        except Exception as e:
            print_error("[Config] Error notifying config change: {}".format(str(e)))

    def sync_with_msa(self):
        try:
            print_debug("[Config] MSA sync called - using config file values")
        except Exception as e:
            print_error("[Config] Error in MSA sync: {}".format(str(e)))

