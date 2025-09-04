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
        
        self._loadConfigFileToParams()
        
        if g_modsSettingsApi:
            self._register_mod()
            

    def _register_mod(self):
        if not g_modsSettingsApi:
            print_debug("[Config] ModsSettingsAPI not available")
            return
            
        try:
            self.configTemplate.set_mod_display_name(Translator.MOD_NAME)
            
            # self.configTemplate.add_to_column1(
            #     LabelParameter().renderParam(Translator.MAIN_LABEL)
            # )

            self.configTemplate.add_parameter_to_column1(
                "tournamentType",
                header=Translator.TOURNAMENT_TYPE_HEADER,
                body=Translator.TOURNAMENT_TYPE_BODY
            )
            
            self.configTemplate.add_parameter_to_column1(
                "apiKey",
                header=Translator.API_KEY_HEADER,
                body=Translator.API_KEY_BODY
            )

            self.configTemplate.add_to_column2(
                LabelParameter().renderParam(header=Translator.BATTLE_BLOGGERS_LABEL, body=Translator.BATTLE_BLOGGERS_BODY)
            )

            self.configTemplate.add_parameter_to_column2(
                "chooseBlogger",
                header=Translator.CHOOSE_BLOGGER_HEADER,
                body=Translator.CHOOSE_BLOGGER_BODY
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
            self._loadConfigFileToParams()
            if not self._loadedSuccessfully:
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
            from ..server import g_serverManager

            result =  g_serverManager.send_stats()
            if result:
                print_debug("[Config] Stats sent successfully after config change")
        except Exception as e:
            print_error("[Config] Error notifying config change: {}".format(str(e)))

    def _loadConfigFileToParams(self):
        print_debug("[Config] Starting config loading ...")
        self._loadedSuccessfully = False

        try:
            success = self.configFile.load_config()
            if success:
                self._loadedSuccessfully = True
                print_debug("[Config] Finished config loading.")
            else:
                print_error("[Config] Config loading failed, using defaults")
            
            if not self.configFile.exists():
                print_debug("[Config] Config file doesn't exist, creating it")
                self.configFile.save_config()
                
        except Exception as e:
            print_error("[Config] Failed to load config: {}".format(str(e)))
            config_items = self.configParams.items()
            for tokenName, param in config_items.items():
                param.value = param.defaultValue

    def reloadSafely(self):
        try:
            self._loadConfigFileToParams()

            from ..server import g_serverClient, ServerClient
            if hasattr(self, 'configParams') and hasattr(self.configParams, 'apiKey'):
                apiKey = self.get_api_key()
                if apiKey != g_serverClient.access_key:
                    g_serverClient = None
                    g_serverClient = ServerClient(api_key=apiKey)

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
            self._loadConfigFileToParams()
            return True
        return False
    
    def get_api_key(self):
        try:
            if not hasattr(self, 'configParams'):
                print_debug("[Config] configParams not available, using default API key")
                return 'dev-test'
            
            tournament_type_param = getattr(self.configParams, 'tournamentType', None)
            if not tournament_type_param:
                print_debug("[Config] tournamentType parameter not found, using default API key")
                return 'dev-test'
            
            tournament_type = tournament_type_param.value
            print_debug("[Config] Tournament type: {}".format(tournament_type))
            
            if tournament_type == 'platoon':
                api_key_param = getattr(self.configParams, 'apiKey', None)
                if not api_key_param:
                    print_debug("[Config] apiKey parameter not found for platoon type")
                    return 'dev-test'
                
                api_key = api_key_param.value
                if not api_key or len(str(api_key).strip()) < 3:
                    print_debug("[Config] Invalid API key for platoon type, using default")
                    return 'dev-test'
                
                return str(api_key).strip()
            
            else:
                blogger_param = getattr(self.configParams, 'chooseBlogger', None)
                if not blogger_param:
                    print_debug("[Config] chooseBlogger parameter not found")
                    return 'dev-test'
                
                blogger_value = blogger_param.value
                print_debug("[Config] Selected blogger: {}".format(blogger_value))
                
                blogger_api_keys = {
                    'Palu4': 'Palu4',
                    'Vgosti': 'Vgosti',
                    'YKP_BOIH': 'YKP_BOIH',
                    'Bizzord': 'Bizzord'
                }
                
                api_key = blogger_api_keys.get(blogger_value)
                if api_key:
                    return api_key
                else:
                    print_debug("[Config] Unknown blogger '{}', using default API key".format(blogger_value))
                    return 'dev-test'
        
        except Exception as e:
            print_error("[Config] Error getting API key: {}".format(e))
            return 'dev-test'