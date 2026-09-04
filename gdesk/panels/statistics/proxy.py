from ...core.gui_proxy import GuiProxyBase, StaticGuiCall, gui
        
class StatisticsProxy(GuiProxyBase):    
    category = 'statistics'
    
    def __init__(self):
        pass
        
    def attach(self, gui):
        gui.stats = self
     
