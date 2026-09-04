from .proxy import StatisticsProxy

from ... import config

if config.get('qapp', False):
    from .panel import StatisticsPanel