# -*- coding: utf-8 -*-
import json
import os
from ..utils import print_error, print_debug

class ConfigFile(object):

    def __init__(self, config_params):
        self.config_path = os.path.join('mods', 'configs', 'under_pressure', 'widget.json')
        self.config_params = config_params
        self._loaded_config_data = None

    def _ensure_config_exists(self):
        try:
            config_dir = os.path.dirname(self.config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                print_debug("[ConfigFile] Created config directory: {}".format(config_dir))

            if not os.path.exists(self.config_path):
                print_debug("[ConfigFile] Config file doesn't exist, creating default")
                return self._create_default_config()
            return True
        except Exception as e:
            print_error("[ConfigFile] Error ensuring config exists: {}".format(str(e)))
            return False

    def _create_default_config(self):
        try:
            config_data = {}
            config_items = self.config_params.items()
            
            print_debug("[ConfigFile] Creating config with {} parameters".format(len(config_items)))
            
            for tokenName, param in config_items.items():
                config_data[tokenName] = param.defaultValue
                print_debug("[ConfigFile] Added default: {} = {}".format(tokenName, param.defaultValue))

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
            print_debug("[ConfigFile] Created default config file at: {}".format(self.config_path))
            
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    content = f.read()
                print_debug("[ConfigFile] Verified file content: {}".format(content[:200]))
                return True
            else:
                print_error("[ConfigFile] File was not created despite no errors")
                return False
            
        except Exception as e:
            print_error("[ConfigFile] Error creating default config: {}".format(str(e)))
            return False

    def load_config(self):
        try:
            if not self._ensure_config_exists():
                print_error("[ConfigFile] Failed to ensure config exists")
                config_items = self.config_params.items()
                for tokenName, param in config_items.items():
                    param.value = param.defaultValue
                return False
            
            if not os.path.exists(self.config_path):
                print_error("[ConfigFile] Config file still doesn't exist after creation")
                return False
                
            with open(self.config_path, 'r') as f:
                content = f.read().strip()
                
            if not content:
                print_debug("[ConfigFile] Config file is empty, recreating")
                if self._create_default_config():
                    with open(self.config_path, 'r') as f:
                        content = f.read().strip()
                else:
                    return False

              
            config_data = json.loads(content)
            self._loaded_config_data = config_data 
            print_debug("[ConfigFile] Loaded config data: {}".format(config_data))
            
            config_items = self.config_params.items()
            for tokenName, param in config_items.items():
                if tokenName in config_data:
                    try:
                        param.value = config_data[tokenName]
                        print_debug("[ConfigFile] Set {} = {}".format(tokenName, param.value))
                    except Exception as e:
                        print_error("[ConfigFile] Error loading parameter {}: {}".format(tokenName, str(e)))
                        param.value = param.defaultValue
                else:
                    param.value = param.defaultValue
                    print_debug("[ConfigFile] Using default for {}: {}".format(tokenName, param.defaultValue))

            print_debug("[ConfigFile] Config loaded successfully")
            return True
                
        except ValueError as e:
            print_error("[ConfigFile] Invalid JSON in config file: {}".format(str(e)))
            self._loaded_config_data = None
            config_items = self.config_params.items()
            for tokenName, param in config_items.items():
                param.value = param.defaultValue
            return False
        except Exception as e:
            print_error("[ConfigFile] Error loading config: {}".format(str(e)))
            self._loaded_config_data = None
            config_items = self.config_params.items()
            for tokenName, param in config_items.items():
                param.value = param.defaultValue
            return False

    def save_config(self):
        try:
            config_dir = os.path.dirname(self.config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                print_debug("[ConfigFile] Created directory for save: {}".format(config_dir))
            
            config_data = {}
            config_items = self.config_params.items()
            for tokenName, param in config_items.items():
                config_data[tokenName] = param.value
                print_debug("[ConfigFile] Preparing to save: {} = {}".format(tokenName, param.value))

            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
            self._loaded_config_data = config_data
            print_debug("[ConfigFile] Config saved to: {}".format(self.config_path))
            
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    saved_content = f.read()
                print_debug("[ConfigFile] Verified saved content: {}".format(saved_content[:200]))
                return True
            else:
                print_error("[ConfigFile] File was not saved despite no errors")
                return False
            
        except Exception as e:
            print_error("[ConfigFile] Error saving config: {}".format(str(e)))
            return False

    def get_loaded_data(self):
        return self._loaded_config_data

    def exists(self):
        exists = os.path.exists(self.config_path)
        print_debug("[ConfigFile] File exists check: {} -> {}".format(self.config_path, exists))
        return exists

    def config_exists(self):
        return self.exists()

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