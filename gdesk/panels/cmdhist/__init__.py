from .proxy import CmdHistGuiProxy

from ... import config

if config.get('qapp', False):
    from .panel import CmdHistPanel