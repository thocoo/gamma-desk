from ...core.gui_proxy import GuiProxyBase, StaticGuiCall, gui
        
class HtmlGuiProxy(GuiProxyBase):    
    category = 'html'
    
    def __init__(self):
        pass
        
    def attach(self, gui):
        gui.html = self
    
    @StaticGuiCall
    def show(html_content):
        #Note that the size of content is limited
        panel = gui.qapp.panels.selected('html')
        if panel is None:
            panel = gui.qapp.panels.select_or_new('html')        
        panel.webview.setHtml(html_content)
        
    @StaticGuiCall
    def load_url(url):
        panel = gui.qapp.panels.selected('html')
        if panel is None:
            panel = gui.qapp.panels.select_or_new('html')        
        panel.webview.load(url)    
