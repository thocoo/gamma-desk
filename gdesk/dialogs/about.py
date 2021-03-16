import platform
import pathlib

from qtpy import QtGui, QtWidgets, QtCore
from qtpy.QtCore import Qt

from .. import config, __version__, __release__, progname 

respath = pathlib.Path(config['respath'])
       
class TextEditLinks(QtWidgets.QTextBrowser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setOpenExternalLinks(True)

    def addLink(self, address, text):
        self.append(f'<a href="{address}">{text}</a>')  
        
    def addMail(self, mail_address, text):        
        self.append(f'<a href="mailto:{mail_address}">{text}</a>')

class AboutScreen(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()        
        self.initUI()
        
    def initUI(self):                               
        desktop = QtWidgets.QApplication.instance().desktop()        
        
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.setWindowTitle('About')
        self.setWindowFlags(Qt.WindowStaysOnTopHint)       
        
        logopixmap = QtGui.QPixmap(str(respath / 'logo' / 'bench_eye_128px.png'))
        
        logo = QtWidgets.QLabel()
        logo.setPixmap(logopixmap)                                
                            
        message = f"""<center><h2>{progname}</h2>
            <p>Version {__release__}</p>
            """

        cont = TextEditLinks(self)
        cont.setReadOnly(True)
        cont.append(message)        
        
        cont.addLink("http://www.apache.org/licenses/LICENSE-2.0", "www.apache.org/licenses/LICENSE-2.0")
        cont.addLink("http://www.fatcow.com/free-icons", "www.fatcow.com/free-icons")
        cont.addMail("thomas.cools@telenet.be", "thomas.cools@telenet.be")
        
        hboxlogo = QtWidgets.QHBoxLayout()
        hboxlogo.addWidget(logo)
        hboxlogo.addWidget(cont)
        
        okButton = QtWidgets.QPushButton("OK")
        hboxbut = QtWidgets.QHBoxLayout()
        hboxbut.addStretch(1)
        hboxbut.addWidget(okButton)
                
        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(hboxlogo)
        vbox.addLayout(hboxbut)
        
        self.setLayout(vbox)

        okButton.clicked.connect(self.close)

        self.show()