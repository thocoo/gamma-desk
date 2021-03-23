from ...core.gui_proxy import GuiProxyBase, StaticGuiCall, gui
        
class CmdHistGuiProxy(GuiProxyBase):    
    category = 'cmdhist'
    
    def __init__(self):
        pass
        
    def attach(self, gui):
        gui.cmdhist = self
    
