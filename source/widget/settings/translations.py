import json

import ResMgr
from helpers import getClientLanguage

from ..utils import print_error, print_debug

DEFAULT_TRANSLATIONS_MAP = {}
TRANSLATIONS_MAP = {}


def loadTranslations():
    defaultTranslationsMap = _loadLanguageFile("en")

    global DEFAULT_TRANSLATIONS_MAP
    DEFAULT_TRANSLATIONS_MAP = defaultTranslationsMap if defaultTranslationsMap is not None else {}

    language = getClientLanguage()
    print_debug("Client language: {}".format(language))

    translationsMap = _loadLanguageFile(language)

    if translationsMap is not None:
        print_debug("Translations for language {} detected".format(language))
        global TRANSLATIONS_MAP
        TRANSLATIONS_MAP = translationsMap
    else:
        print_debug("Translations for language {} not present, fallback to en".format(language))


def _loadLanguageFile(language):
    translationsRes = ResMgr.openSection("gui\l10n\widget\{}.json".format(language))
    if translationsRes is None:
        print_debug("Failed to load translations for language {}".format(language))
        return None

    translationsStr = str(translationsRes.asBinary)
    return json.loads(translationsStr, encoding="UTF-8")


class TranslationBase(object):

    def __init__(self, tokenName):
        self._tokenName = tokenName
        self._value = None

    def __get__(self, instance, owner=None):
        if self._value is None:
            self._value = self._generateTranslation()
        return self._value

    def _generateTranslation(self):
        raise NotImplementedError()


class TranslationElement(TranslationBase):

    def _generateTranslation(self):
        global TRANSLATIONS_MAP
        if self._tokenName in TRANSLATIONS_MAP:
            return TRANSLATIONS_MAP[self._tokenName]

        global DEFAULT_TRANSLATIONS_MAP
        return DEFAULT_TRANSLATIONS_MAP[self._tokenName]


class TranslationList(TranslationBase):

    def _generateTranslation(self):
        global TRANSLATIONS_MAP
        if self._tokenName in TRANSLATIONS_MAP:
            return "".join(TRANSLATIONS_MAP[self._tokenName])

        global DEFAULT_TRANSLATIONS_MAP
        return "".join(DEFAULT_TRANSLATIONS_MAP[self._tokenName])


class Translator(object):

    MODNAME = TranslationElement("modname")
    CHECKED = TranslationElement("checked")
    UNCHECKED = TranslationElement("unchecked")
    DEFAULT_VALUE = TranslationElement("defaultValue")
    MAIN_LABEL = TranslationElement("mainLabel")
    API_KEY = TranslationElement("apiKey")
    API_KEY_HEADER = TranslationElement("apiKey.header")
    API_KEY_BODY = TranslationElement("apiKey.body")

    