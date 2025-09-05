# -*- coding: utf-8 -*-
from .stats_wraper import StatsWrapper

__all__ = [
    'print_log',
    'print_error',
    'print_debug',
    'g_statsWrapper'
]

DEBUG_MODE = True

def print_log(log):
    print("[WIDGET]: {}".format(str(log)))

def print_error(log):
    print("[WIDGET] [ERROR]: {}".format(str(log)))

def print_debug(log):
    global DEBUG_MODE
    if DEBUG_MODE:
        print("[WIDGET] [DEBUG]: {}".format(str(log)))


g_statsWrapper = StatsWrapper()