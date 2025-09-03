# -*- coding: utf-8 -*-
import json
import os
from .config_param_types import LabelParam
from ..utils import print_error, print_debug

try:
    from gui.modsSettingsApi import g_modsSettingsApi   
except ImportError:
    print_error("[Config] Failed to import g_modsSettingsApi")
    g_modsSettingsApi = None

modLinkage = 'me.under-pressure.widget'

class Config(object):
    def __init__(self, configParams, configTemplate):
        self.configParams = configParams
        self.configTemplate = configTemplate
        self.config_path = os.path.join('mods', 'configs', 'under_pressure', 'widget.json')
        self._loadedSuccessfully = False
        
        self._ensure_config_exists()
        self.load_config()
        
        if g_modsSettingsApi:
            self._register_mod()

    def _ensure_config_exists(self):
        try:
            config_dir = os.path.dirname(self.config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                print_debug("[Config] Created config directory")

            if not os.path.exists(self.config_path):
                self._create_default_config()
        except Exception as e:
            print_error("[Config] Error ensuring config exists: {}".format(str(e)))

    def _create_default_config(self):
        try:
            config_data = {}
            config_items = self.configParams.items()
            for tokenName, param in config_items.items():
                config_data[tokenName] = param.fromJsonValue(param.defaultJsonValue)

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print_debug("[Config] Created default config file")
        except Exception as e:
            print_error("[Config] Error creating default config: {}".format(str(e)))

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)

                config_items = self.configParams.items()
                for tokenName, param in config_items.items():
                    if tokenName in config_data:
                        try:
                            param.jsonValue = config_data[tokenName]
                        except Exception as e:
                            print_error("[Config] Error loading parameter {}: {}".format(tokenName, str(e)))
                            param.value = param.defaultValue
                    else:
                        param.value = param.defaultValue

                self._loadedSuccessfully = True
                print_debug("[Config] loaded successfully")
            else:
                print_debug("[Config] file not found, using defaults")
                self._loadedSuccessfully = False
        except Exception as e:
            print_error("[Config] Error loading config: {}".format(str(e)))
            self._loadedSuccessfully = False

    def save_config(self):
        try:
            config_data = {}
            config_items = self.configParams.items()
            for tokenName, param in config_items.items():
                config_data[tokenName] = param.fromJsonValue(param.jsonValue)

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print_debug("[Config] saved successfully")
        except Exception as e:
            print_error("[Config] Error saving config: {}".format(str(e)))

    def _register_mod(self):
        if not g_modsSettingsApi:
            print_debug("[Config] ModsSettingsAPI not available")
            return
            
        try:
            self.configTemplate.set_mod_display_name(u"Віджет від Палича")
            
            self.configTemplate.add_to_column1(
                LabelParam().renderParam(u'Основні налаштування')
            )
            
            self.configTemplate.add_parameter_to_column1(
                "enabled", 
                header=u"Увімкнути мод",
                body=u"Увімкнути або вимкнути мод"
            )
            
            self.configTemplate.add_parameter_to_column1(
                "apiKey", 
                header=u"API Ключ",
                body=u"Ваш API ключ для передачі даних на сервер"
            )

            template = self.configTemplate.generateTemplate()  

            settings = g_modsSettingsApi.setModTemplate(
                modLinkage, 
                template, 
                self.on_settings_changed
            )
            
            if settings:
                self._apply_settings_from_msa(settings)
            
            print_debug("[Config] Mod template registered successfully")
            
        except Exception as e:
            print_error("[Config] Error registering mod template: {}".format(str(e)))

    def _apply_settings_from_msa(self, settings):
        try:
            config_items = self.configParams.items()
            for param_name, value in settings.items():
                if param_name in config_items:
                    param = config_items[param_name]
                    try:
                        param.msaValue = value
                    except Exception as e:
                        print_error("[Config] Error applying MSA setting {} = {}: {}".format(
                            param_name, value, str(e)))
            
            self.save_config()
            print_debug("[Config] Applied settings from MSA")
            
        except Exception as e:
            print_error("[Config] Error applying MSA settings: {}".format(str(e)))

    def on_settings_changed(self, linkage, newSettings):
        if linkage != modLinkage:
            return
            
        if not self._loadedSuccessfully:
            print_error("[Config] Settings change cancelled - config not loaded properly")
            return
            
        try:
            print_debug("[Config] MSA settings changed: {}".format(str(newSettings)))

            config_items = self.configParams.items()
            for tokenName, value in newSettings.items():
                if tokenName in config_items:
                    param = config_items[tokenName]
                    try:
                        param.msaValue = value
                    except Exception as e:
                        print_error("[Config] Error setting parameter {} to {}: {}".format(
                            tokenName, value, str(e)))
            
            self.save_config()
            self._notify_config_changed()
            print_debug("[Config] Settings updated successfully")
            
        except Exception as e:
            print_error("[Config] Error updating settings from MSA: {}".format(str(e)))

    def _notify_config_changed(self):
        try:
            from ..server_connect import g_serverClient
            
            api_key_param = self.configParams.items().get('apiKey')
            if api_key_param:
                g_serverClient.setApiKey(api_key_param.value)
                print_debug("[Config] Config change notification sent")
        except Exception as e:
            print_error("[Config] Error notifying config change: {}".format(str(e)))

    def reload_safely(self):
        try:
            self.load_config()
        except Exception as e:
            print_error("[Config] Error reloading config: {}".format(str(e)))

    def sync_with_msa(self):
        try:
            if g_modsSettingsApi:
                current_settings = {}
                config_items = self.configParams.items()
                for param_name, param in config_items.items():
                    current_settings[param_name] = param.msaValue
                
                g_modsSettingsApi.updateModSettings(modLinkage, current_settings)
                print_debug("[Config] Synchronized with MSA")
        except Exception as e:
            print_error("[Config] Error in MSA sync: {}".format(str(e)))