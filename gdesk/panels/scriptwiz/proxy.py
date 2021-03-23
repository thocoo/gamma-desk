from ...core.gui_proxy import GuiProxyBase, StaticGuiCall, gui
      
class ScriptWizardProxy(GuiProxyBase):    
    category = 'scriptwiz'
    
    def __init__(self):
        pass
        
    def attach(self, gui):
        gui.script = self
       
    @StaticGuiCall
    def open(templateFile):
        """
        
        """        
        panel = gui.qapp.panels.select_or_new('scriptwiz')                
        panel.openTemplate(templateFile)