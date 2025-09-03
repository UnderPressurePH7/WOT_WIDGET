# -*- coding: utf-8 -*-
from .config_param_types import LabelParameter
from .config_file import ConfigFile

from .config_param import ConfigParams
from .config_template import Template
from .translations import Translator

from ..utils import print_error, print_debug
try:
    from gui.modsSettingsApi import g_modsSettingsApi   
except ImportError:
    print_error("[Config] Failed to import g_modsSettingsApi")
    g_modsSettingsApi = None

modLinkage = 'me.under-pressure.widget'

class Config(object):
    def __init__(self):
        print_debug("[Config] Initializing configuration")
        self.configParams = ConfigParams()
        self.configTemplate = Template(self.configParams)
        self.configFile = ConfigFile(self.configParams)
        self._loadedSuccessfully = False
        
        self.configFile.load_config()
        
        if g_modsSettingsApi:
            self._register_mod()
            

    def _register_mod(self):
        if not g_modsSettingsApi:
            print_debug("[Config] ModsSettingsAPI not available")
            return
            
        try:
            self.configTemplate.set_mod_display_name(Translator.MOD_NAME)
            
            self.configTemplate.add_to_column1(
                LabelParameter().renderParam(Translator.MAIN_LABEL)
            )
            
            self.configTemplate.add_parameter_to_column1(
                "apiKey",
                header=Translator.API_KEY_HEADER,
                body=Translator.API_KEY_BODY
            )

            template = self.configTemplate.generateTemplate()  

            print_debug("[Config] Template = {}".format(template))
            
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
            
            self.configFile.save_config()
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

            self.configFile.save_config()
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
            self._loadedSuccessfully = self.configFile.load_config(self.configParams)
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

    def backup_config(self):
        return self.configFile.backup_config()

    def restore_config(self):
        if self.configFile.restore_config():
            self.configFile.load_config()

            return True
        return False

    def config_exists(self):
        return self.configFile.config_exists()