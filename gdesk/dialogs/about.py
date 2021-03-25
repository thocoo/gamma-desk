"""
The About window of this GUI
"""
import pathlib

from qtpy import QtGui, QtWidgets
from qtpy.QtCore import Qt

from .. import config, __version__, __release__, PROGNAME

respath = pathlib.Path(config['respath'])

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


class AboutScreen(QtWidgets.QDialog):
    """
    The About window
    """
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        """
        Init the GUI items on this widget
        """
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.setWindowTitle('About')
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        logopixmap = QtGui.QPixmap(str(respath / 'logo' / 'logo_128px.png'))

        logo = QtWidgets.QLabel()
        logo.setPixmap(logopixmap)

        message = f"""<center><h2>{PROGNAME}</h2>
            <p>Version {__release__}</p>
            """

        cont = TextEditLinks(self)
        cont.setReadOnly(True)
        cont.append(message)

        cont.addLink("http://www.apache.org/licenses/LICENSE-2.0",
            "www.apache.org/licenses/LICENSE-2.0")
        cont.addLink("http://www.fatcow.com/free-icons",
            "www.fatcow.com/free-icons")
        cont.addMail("thomas.cools@telenet.be",
            "thomas.cools@telenet.be")

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
