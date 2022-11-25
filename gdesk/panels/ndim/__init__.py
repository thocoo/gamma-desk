from ... import config

if config['qapp']:
    from .panel import NdimPanel

from .proxy import NdimGuiProxy
