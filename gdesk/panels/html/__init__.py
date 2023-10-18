from .proxy import HtmlGuiProxy

from ... import config

if config.get('qapp', False):
    from .panel import HtmlPanel