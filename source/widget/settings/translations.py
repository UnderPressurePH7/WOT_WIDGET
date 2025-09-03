# -*- coding: utf-8 -*-
import json
import threading

import ResMgr
from helpers import getClientLanguage

from ..utils import print_error, print_debug


class TranslationError(Exception):
    pass


class TranslationManager(object):
    
    def __init__(self):
        self._default_translations_map = {}
        self._translations_map = {}
        self._current_language = None
        self._translation_cache = {}
        self._cache_lock = threading.Lock()
        self._translations_loaded = False
        self.fallback_language = "en"
        self.translation_path_template = "gui/l10n/widget/{}.json"

    def _safe_json_load(self, content, language):
        try:
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            return json.loads(content, encoding="utf-8")
        except (ValueError, TypeError, UnicodeDecodeError) as e:
            print_error("[TranslationManager] Failed to parse JSON for language {}: {}".format(language, e))
            return None

    def _load_language_file(self, language):
        try:
            translation_path = self.translation_path_template.format(language)
            translations_res = ResMgr.openSection(translation_path)
            
            if translations_res is None:
                print_debug("[TranslationManager] Translation file not found for language: {}".format(language))
                return None

            content = translations_res.asBinary
            if not content:
                print_debug("[TranslationManager] Empty translation file for language: {}".format(language))
                return None

            return self._safe_json_load(content, language)
            
        except Exception as e:
            print_error("[TranslationManager] Error loading translation file for {}: {}".format(language, e))
            return None

    def _validate_translations(self, translations, language):
        if not isinstance(translations, dict):
            print_error("[TranslationManager] Invalid translation format for {}: expected dict, got {}".format(
                language, type(translations).__name__))
            return False
        
        empty_keys = [key for key, value in translations.items() if not value or not str(value).strip()]
        if empty_keys:
            print_debug("[TranslationManager] Empty translation values in {} for keys: {}".format(language, empty_keys))

        return True

    def load_translations(self, force_reload=False):
        if self._translations_loaded and not force_reload:
            print_debug("[TranslationManager] Translations already loaded, skipping...")
            return True
        
        try:
            print_debug("[TranslationManager] Loading default translations ({})...".format(self.fallback_language))
            default_translations = self._load_language_file(self.fallback_language)
            
            if default_translations is None:
                print_error("[TranslationManager] Failed to load default translations. Mod may not work correctly.")
                return False
            
            if not self._validate_translations(default_translations, self.fallback_language):
                print_error("[TranslationManager] Invalid default translation format")
                return False
            
            self._default_translations_map = default_translations
            
            client_language = getClientLanguage()
            self._current_language = client_language
            print_debug("[TranslationManager] Detected client language: {}".format(client_language))

            if client_language != self.fallback_language:
                client_translations = self._load_language_file(client_language)
                
                if client_translations is not None and self._validate_translations(client_translations, client_language):
                    print_debug("[TranslationManager] Loaded translations for language: {}".format(client_language))
                    self._translations_map = client_translations
                else:
                    print_debug("[TranslationManager] Failed to load {} translations, using {} as fallback".format(
                        client_language, self.fallback_language))
                    self._translations_map = default_translations.copy()
            else:
                self._translations_map = default_translations.copy()
            
            self._clear_cache()
            self._translations_loaded = True

            print_debug("[TranslationManager] Translation system initialized successfully")
            return True
            
        except Exception as e:
            print_error("[TranslationManager] Critical error during translation loading: {}".format(e))
            return False

    def _clear_cache(self):
        with self._cache_lock:
            self._translation_cache.clear()

    def get_current_language(self):
        return self._current_language or self.fallback_language

    def _get_cached_translation(self, token_name):
        with self._cache_lock:
            return self._translation_cache.get(token_name)

    def _cache_translation(self, token_name, translation):
        with self._cache_lock:
            self._translation_cache[token_name] = translation

    def initialize(self):
        try:
            success = self.load_translations()
            if not success:
                print_error("[TranslationManager] Failed to initialize translation system")
        except Exception as e:
            print_error("[TranslationManager] Critical error initializing translations: {}".format(e))


g_translation_manager = TranslationManager()
g_translation_manager.initialize()


class TranslationBase(object):
    
    def __init__(self, token_name, manager=None):
        self._token_name = token_name
        self._cached_value = None
        self._manager = manager or g_translation_manager

    def __get__(self, instance, owner=None):
        if self._cached_value is None:
            self._cached_value = self._generate_translation()
        return self._cached_value

    def _generate_translation(self):
        raise NotImplementedError("Subclasses must implement _generate_translation")
    
    def invalidate_cache(self):
        self._cached_value = None


class TranslationElement(TranslationBase):
    
    def _generate_translation(self):
        if not self._manager._translations_loaded:
            print_debug("[TranslationElement] Translations not loaded, attempting to load...")
            self._manager.load_translations()
        
        cached = self._manager._get_cached_translation(self._token_name)
        if cached is not None:
            return cached
        
        translation = None
        if self._token_name in self._manager._translations_map:
            translation = self._manager._translations_map[self._token_name]
        elif self._token_name in self._manager._default_translations_map:
            translation = self._manager._default_translations_map[self._token_name]
        else:
            print_debug("[TranslationElement] Translation not found for token: {}".format(self._token_name))
            translation = self._token_name.replace('.', ' ').replace('_', ' ').title()
        
        self._manager._cache_translation(self._token_name, translation)
        return translation


class TranslationList(TranslationBase):
    
    def _generate_translation(self):
        if not self._manager._translations_loaded:
            self._manager.load_translations()
        
        cached = self._manager._get_cached_translation(self._token_name)
        if cached is not None:
            return cached
        
        translation_list = None
        if self._token_name in self._manager._translations_map:
            translation_list = self._manager._translations_map[self._token_name]
        elif self._token_name in self._manager._default_translations_map:
            translation_list = self._manager._default_translations_map[self._token_name]
        
        if translation_list is None:
            print_debug("[TranslationList] Translation list not found for token: {}".format(self._token_name))
            result = self._token_name.replace('.', ' ').replace('_', ' ').title()
        else:
            if isinstance(translation_list, list):
                result = "".join(translation_list)
            else:
                result = str(translation_list)
        
        self._manager._cache_translation(self._token_name, result)
        return result


class Translator(object):
    MOD_NAME = TranslationElement("modname")
    CHECKED = TranslationElement("checked")
    UNCHECKED = TranslationElement("unchecked")
    DEFAULT_VALUE = TranslationElement("defaultValue")
    MAIN_LABEL = TranslationElement("mainLabel")
    
    API_KEY = TranslationElement("apiKey")
    API_KEY_HEADER = TranslationElement("apiKey.header")
    API_KEY_BODY = TranslationElement("apiKey.body")