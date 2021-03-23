from .proxy import CmdHistGuiProxy

from ... import config

if config['qapp']:
    from .panel import CmdHistPanel