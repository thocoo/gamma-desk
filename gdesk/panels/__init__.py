from .. import config, gui

if config.get('qapp', False):
    from .base import BasePanel, CheckMenu, thisPanel, selectThisPanel