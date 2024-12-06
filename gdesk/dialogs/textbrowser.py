"""
The About window of this GUI
"""
import pathlib

from qtpy import QtGui, QtWidgets, API_NAME
from qtpy.QtWidgets import QStyle
from qtpy.QtCore import Qt

from .. import config
from ..core.gui_proxy import gui


respath = pathlib.Path(config['respath'])

if API_NAME in ['PySide6']:
    DEFAULT_ICON = {
        'error': QStyle.StandardPixmap.SP_MessageBoxCritical,
        'info': QStyle.StandardPixmap.SP_MessageBoxInformation,
        'help': QStyle.StandardPixmap.SP_MessageBoxQuestion,
        'warn': QStyle.StandardPixmap.SP_MessageBoxWarning
        }

else:
    DEFAULT_ICON = {
        'error': QStyle.SP_MessageBoxCritical,
        'info': QStyle.SP_MessageBoxInformation,
        'help': QStyle.SP_MessageBoxQuestion,
        'warn': QStyle.SP_MessageBoxWarning
        }



class TextEditLinks(QtWidgets.QTextBrowser):
    """
    QTextBrowser used to show clickable links
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setOpenExternalLinks(True)

    def addLink(self, address, text):
        """addLink"""
        self.append(f'<a href="{address}">{text}</a>')

    def addMail(self, mail_address, text):
        """addMail"""
        self.append(f'<a href="mailto:{mail_address}">{text}</a>')
        
    def scrollToTop(self):
        cursor = self.textCursor()
        cursor.setPosition(0)
        self.setTextCursor(cursor)


class TextBrowserContent():        

    def initUI(self, content, title, icon):
        """
        Init the GUI items on this widget
        """
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setWindowTitle(title)

        cont = TextEditLinks(self)
        cont.setReadOnly(True)
        cont.append(content)
        cont.scrollToTop()
        
        hboxcontent= QtWidgets.QHBoxLayout()
        
        if icon in ['warn', 'error', 'info', 'help']:
            iconWidget = self.style().standardIcon(DEFAULT_ICON[icon])
        
        elif not icon is None: 
            # Load if from a file
            iconWidget = QtGui.QIcon(str(icon))
            
        else:
            iconWidget = None   

        if not iconWidget is None:
            self.setWindowIcon(iconWidget)            
            
        hboxcontent.addWidget(cont)
        
        hboxbut = QtWidgets.QHBoxLayout()
        hboxbut.addStretch(1)
        
        okButton = QtWidgets.QPushButton("OK")
        okButton.clicked.connect(self.close)        
            
        hboxbut.addWidget(okButton)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(hboxcontent)
        vbox.addLayout(hboxbut)

        self.setLayout(vbox)

            
   
class TextBrowser(QtWidgets.QDialog, TextBrowserContent):

    def __init__(self, content: str='No content', title: str='HTML', icon: str=None):
        super().__init__()
        self.initUI(content, title, icon)
