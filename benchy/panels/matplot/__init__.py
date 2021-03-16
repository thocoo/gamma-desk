from ... import config

if config['qapp']:
    from .plotpanel import PlotPanel
    
from .plotproxy import PlotGuiProxy