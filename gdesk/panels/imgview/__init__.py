from ... import config

if config.get('qapp', False):
    from .imgview import ImageViewer, ImageProfilePanel
    
from .proxy import ImageGuiProxy    