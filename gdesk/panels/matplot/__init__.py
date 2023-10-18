from ... import config

if config.get('qapp', False):
    from .plotpanel import PlotPanel
    
from .plotproxy import PlotGuiProxy