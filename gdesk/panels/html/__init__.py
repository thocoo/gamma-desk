from .proxy import HtmlGuiProxy

from ... import config

if config['qapp']:
    from .panel import HtmlPanel