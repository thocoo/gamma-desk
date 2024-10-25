"""
The About window of this GUI
"""
import pathlib

from qtpy import QtGui, QtWidgets
from qtpy.QtWidgets import QStyle
from qtpy.QtCore import Qt

from .. import config
from ..core.gui_proxy import gui


respath = pathlib.Path(config['respath'])

# in QStyle.StandardPixmap for PySide6 

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


class TextBrowser(QtWidgets.QDialog):
#class TextBrowser(QtWidgets.QWidget):
    """
    The About window
    """
    def __init__(self, content: str='No content', title: str='HTML', icon: str=None):
        super().__init__()
        self.initUI(content, title, icon)
        #gui.qapp.unnamed_windows.append(self)
        #self.show()
        

    def initUI(self, content, title, icon):
        """
        Init the GUI items on this widget
        """
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.setWindowTitle(title)
        #self.setWindowFlags(Qt.WindowStaysOnTopHint)

        # message = f"""<center><h2>{PROGNAME}</h2>
            # <p>Version {__release__}</p>
            # """

        cont = TextEditLinks(self)
        cont.setReadOnly(True)
        cont.append(content)

        # cont.addLink("http://www.apache.org/licenses/LICENSE-2.0",
            # "www.apache.org/licenses/LICENSE-2.0")
        # cont.addLink("http://www.fatcow.com/free-icons",
            # "www.fatcow.com/free-icons")
        # cont.addMail("thomas.cools@telenet.be",
            # "thomas.cools@telenet.be")

        hboxcontent= QtWidgets.QHBoxLayout()
        
        if icon in ['warn', 'error', 'info', 'help']:
            iconWidget = self.style().standardIcon(DEFAULT_ICON[icon])
        
        elif not icon is None: 
            # Load if from a file
            iconWidget = QtGui.QIcon(str(icon))
            
        else:
            iconWidget = None            
            
        hboxcontent.addWidget(cont)
        
        hboxbut = QtWidgets.QHBoxLayout()
        hboxbut.addStretch(1)
        
        # pinButton = QtWidgets.QPushButton("Toggle Stay on Top")
        # pinButton.clicked.connect(self.toggleOnTop)
        # hboxbut.addWidget(pinButton)
        
        okButton = QtWidgets.QPushButton("OK")
        okButton.clicked.connect(self.close)
        
        if not iconWidget is None:
            okButton.setIcon(iconWidget)
            
        hboxbut.addWidget(okButton)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(hboxcontent)
        vbox.addLayout(hboxbut)

        self.setLayout(vbox)

        
    # def toggleOnTop(self):
        # flags = self.windowFlags()
        
        # if (flags & Qt.WindowStaysOnTopHint) == Qt.WindowStaysOnTopHint:
            # flags = flags & (~Qt.WindowStaysOnTopHint)
        # else:
            # flags = flags | Qt.WindowStaysOnTopHint
        
        # self.setWindowFlags(flags)
        # self.show()            
        
        
    # def closeEvent(self, event):
        # gui.qapp.unnamed_windows.remove(self)
        # event.accept()
            
   

