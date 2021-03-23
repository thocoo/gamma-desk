from qtpy.QtCore import Qt
from qtpy.QtGui import QWindow
from qtpy.QtWidgets import QWidget
from qtpy import QtWebEngineWidgets

from ..base import BasePanel, CheckMenu

HTML_BANNER = '''<html>
<head>
<title>A Sample Page</title>
</head>
<body>
<h1>Hello, World!</h1>
<hr />
I have nothing to say.
</body>
</html>'''

class HtmlPanel(BasePanel):
    panelCategory = 'html'
    panelShortName = 'basic'

    def __init__(self, parent, panid):
        super().__init__(parent, panid, type(self).panelCategory)
        
        self.fileMenu = CheckMenu("File", self.menuBar())
        self.addMenuItem(self.fileMenu, "Close", self.close_panel,
            statusTip = "Close this html panel",
            icon = 'cross.png')
        
        self.webview = QtWebEngineWidgets.QWebEngineView()
        self.webview.setHtml(HTML_BANNER)
        self.setCentralWidget(self.webview)        
        self.addBaseMenu()