# -*- coding: utf-8 -*-
import json
import os
from ..utils import print_error, print_debug

class ConfigFile(object):

    def __init__(self, config_params):
        self.config_path =  os.path.join('mods', 'configs', 'under_pressure', 'widget.json')
        self.config_params = config_params

    def _ensure_config_exists(self):
        try:
            config_dir = os.path.dirname(self.config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                print_debug("[ConfigFile] Created config directory")

            if not os.path.exists(self.config_path):
                self._create_default_config(self.config_params)
        except Exception as e:
            print_error("[ConfigFile] Error ensuring config exists: {}".format(str(e)))

    def _create_default_config(self):
        try:
            config_data = {}
            config_items = self.config_params.items()
            for tokenName, param in config_items.items():
                config_data[tokenName] = param.fromJsonValue(param.defaultJsonValue)

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print_debug("[ConfigFile] Created default config file")
        except Exception as e:
            print_error("[ConfigFile] Error creating default config: {}".format(str(e)))

    def load_config(self):
        try:
            self._ensure_config_exists()
            
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)

                config_items = self.config_params.items()
                for tokenName, param in config_items.items():
                    if tokenName in config_data:
                        try:
                            param.jsonValue = config_data[tokenName]
                        except Exception as e:
                            print_error("[ConfigFile] Error loading parameter {}: {}".format(tokenName, str(e)))
                            param.value = param.defaultValue
                    else:
                        param.value = param.defaultValue

                print_debug("[ConfigFile] Config loaded successfully")
                return True
            else:
                config_items = self.config_params.items()
                for tokenName, param in config_items.items():
                    param.value = param.defaultValue
                print_debug("[ConfigFile] Config file not found, using defaults - still successful")
                return True 
                
        except Exception as e:
            print_error("[ConfigFile] Error loading config: {}".format(str(e)))
            return False

    def save_config(self):
        try:
            config_data = {}
            config_items = self.config_params.items()
            for tokenName, param in config_items.items():
                config_data[tokenName] = param.fromJsonValue(param.jsonValue)

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print_debug("[ConfigFile] Config saved successfully")
            return True
            
        except Exception as e:
            print_error("[ConfigFile] Error saving config: {}".format(str(e)))
            return False

    def config_exists(self):
        return os.path.exists(self.config_path)

    def get_config_path(self):
        return self.config_path

    def backup_config(self, backup_suffix='.backup'):
        try:
            if self.config_exists():
                backup_path = self.config_path + backup_suffix
                import shutil
                shutil.copy2(self.config_path, backup_path)
                print_debug("[ConfigFile] Config backup created: {}".format(backup_path))
                return True
        except Exception as e:
            print_error("[ConfigFile] Error creating config backup: {}".format(str(e)))
        return False

    def restore_config(self, backup_suffix='.backup'):
        try:
            backup_path = self.config_path + backup_suffix
            if os.path.exists(backup_path):
                import shutil
                shutil.copy2(backup_path, self.config_path)
                print_debug("[ConfigFile] Config restored from backup")
                return True
        except Exception as e:
            print_error("[ConfigFile] Error restoring config from backup: {}".format(str(e)))
        return False