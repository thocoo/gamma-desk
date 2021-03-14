from .. import config

if config.get('qapp', False):
    from .base import BasePanel, CheckMenu, thisPanel
    MainPanel = BasePanel

