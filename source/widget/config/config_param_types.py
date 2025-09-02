# -*- coding: utf-8 -*-
import Keys
from ..utils import print_error, print_debug

PARAM_REGISTRY = {}

class Param(object):
    def __init__(self, path, defaultValue, disabledValue=None):
        self.name = path[-1]
        self.path = path
        self.tokenName = "-".join(self.path)
        self.value = defaultValue
        self.defaultValue = defaultValue
        self.disabledValue = disabledValue if disabledValue is not None else defaultValue
        PARAM_REGISTRY[self.tokenName] = self

    def readValueFromConfigDict(self, configDict):
        readValue = None
        prevConfigSection = configDict

        for pathSegment in self.path:
            if pathSegment not in prevConfigSection:
                return None
            dictSection = prevConfigSection[pathSegment]
            readValue = dictSection
            prevConfigSection = dictSection

        return readValue

    @property
    def jsonValue(self):
        return self.toJsonValue(self.value)

    @jsonValue.setter
    def jsonValue(self, jsonValue):
        try:
            self.value = self.fromJsonValue(jsonValue)
        except Exception as e:
            print_error("[Param] Error occurred while saving parameter %s with jsonValue %s, fallback to previous valid value: %s" % (self.tokenName, jsonValue, str(e)))

    @property
    def defaultMsaValue(self):
        return self.toMsaValue(self.defaultValue)

    @property
    def msaValue(self):
        return self.toMsaValue(self.value)

    @msaValue.setter
    def msaValue(self, msaValue):
        try:
            self.value = self.fromMsaValue(msaValue)
        except Exception as e:
            print_error("[Param] Error occurred while saving parameter %s with msaValue %s, fallback to previous valid value: %s" % (self.tokenName, msaValue, str(e)))

    def toMsaValue(self, value):
        return value

    def fromMsaValue(self, msaValue):
        return msaValue

    def toJsonValue(self, value):
        return value

    def fromJsonValue(self, jsonValue):
        return jsonValue

    def validate(self, value):
        return True
