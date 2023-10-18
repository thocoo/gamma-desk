from ... import config

if config.get('qapp', False):
    from .panel import NdimPanel

from .proxy import NdimGuiProxy
