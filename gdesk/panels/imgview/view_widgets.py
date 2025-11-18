from pathlib import Path
import types
from collections.abc import Iterable
import logging

logger = logging.getLogger(__name__)
   

from ... import config, gui

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal, QUrl
from qtpy.QtGui import QFont, QTextCursor, QPainter, QPixmap, QCursor, QPalette, QColor, QKeySequence
from qtpy.QtWidgets import (QApplication, QAction, QMainWindow, QPlainTextEdit, QSplitter, QVBoxLayout, QHBoxLayout, QSplitterHandle,
    QMessageBox, QTextEdit, QLabel, QWidget, QStyle, QStyleFactory, QLineEdit, QShortcut, QMenu, QStatusBar, QColorDialog)

from ...panels import CheckMenu
from ...panels.base import MyStatusBar


here = Path(__file__).parent.absolute()
respath = Path(config['respath'])
    

class ZoomWidget(MyStatusBar):
    zoomEdited = Signal(float)
    
    def __init__(self, parent):
        super().__init__(parent=parent)
        self.panel = parent.panel

        self.zoomOutBtn = QtWidgets.QPushButton(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'bullet_toggle_minus.png')), None, self)
        self.zoomOutBtn.setFixedWidth(20)
        self.zoom = QLineEdit('100')
        self.zoom.keyPressEvent = self.zoomKeyPressEvent
        self.zoomInBtn = QtWidgets.QPushButton(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'bullet_toggle_plus.png')), None, self)       
        self.zoomInBtn.setFixedWidth(20)
        
        self.addWidget(self.zoomOutBtn)
        self.addWidget(self.zoom, 1)
        self.addWidget(self.zoomInBtn)
        
        self.zoomOutBtn.clicked.connect(self.panel.zoomOut)
        self.zoomInBtn.clicked.connect(self.panel.zoomIn)     
        self.zoomEdited.connect(self.panel.setZoomValue)  

    def set_zoom(self, value):
        self.zoom.setText(f'{value*100:.2f}')          

    def zoomKeyPressEvent(self, event):
        key_enter = (event.key() == Qt.Key_Return) or \
            (event.key() == Qt.Key_Enter)

        statpan = self
        if event.key() == Qt.Key_Up:
            statpan.panel.zoomIn()

        elif event.key() == Qt.Key_Down:
            statpan.panel.zoomOut()

        if key_enter:
            statpan.zoomEdited.emit(float(self.zoom.text()) / 100)

        QLineEdit.keyPressEvent(self.zoom, event)                  


class ValuePanel(MyStatusBar):
    zoomEdited = Signal(float)
    
    def __init__(self, parent):
        super().__init__(parent=parent)    
        self.panel = parent.panel        
        
        console_font = QFont(config['console']['font'], pointSize=config['console']['fontsize'])                      
        
        self.xy = QLabel('0,0')
        self.vallab = QLabel('val')
        self.val = QLineEdit('0')
        self.val.setFont(console_font)
        if gui.qapp.color_scheme == "Dark":
            self.val.setStyleSheet(f"QLineEdit {{ background: rgb(33, 33, 33);}}")
        else:
            self.val.setStyleSheet(f"QLineEdit {{ background: rgb(224, 224, 224); color: rgb(0, 0, 0);}}")
        self.val.setReadOnly(True)
        self.val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.chooseValFormat = QMenu('Value Format', self)
        self.chooseValFormat.addAction(QAction("Decimal", self, triggered=lambda: self.set_val_format('dec')))
        self.chooseValFormat.addAction(QAction("Hex", self, triggered=lambda: self.set_val_format('hex')))
        self.chooseValFormat.addAction(QAction("Binary", self, triggered=lambda: self.set_val_format('bin')))        
        self.val.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.val.customContextMenuRequested.connect(lambda: self.chooseValFormat.exec_(QtGui.QCursor().pos()))       
        
        self.addWidget(self.xy, 2)
        self.addWidget(self.vallab, 1, Qt.AlignRight)
        self.addWidget(self.val, 4)

    def set_val_format(self, fmt='dec'):        
        self.panel.imviewer.set_val_item_format(fmt)

    def set_xy_val(self, x, y, val=None):
        self.xy.setText(f'xy:{x:d},{y:d} ')        

        fmt = self.panel.imviewer.val_item_format        

        if not val is None:
            try:
                if isinstance(val, Iterable):
                    r, g, b, *ignore = val
                    text = ' '.join(fmt.format(v) for v in val)                                        
                    self.val.setText(text)
                else:
                    self.val.setText(fmt.format(val))
            except:
                self.val.setText(str(val))               

class ContrastPanel(MyStatusBar):

    """
    A panel showing offset, gain and gamma factor.

    For use in the status bar.
    """

    offsetGainEdited = Signal(str, str, str)
    blackWhiteEdited = Signal(str, str)

    def __init__(self, parent):
        super().__init__(parent=parent)

        self.panel = parent.panel
        
        console_font = QFont(config['console']['font'], pointSize=config['console']['fontsize'])

        self.offsetlab = QLabel('B')
        self.offset = QLineEdit('0')
        self.offset.keyPressEvent = types.MethodType(offsetGainKeyPressEvent, self.offset)
        self.offset.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.chooseBlackMenu = QMenu('Black Defaults', self)
        self.chooseBlackMenu.addAction(QAction("0", self, triggered=lambda: self.chooseBlack('0')))
        self.offset.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)    
        self.offset.customContextMenuRequested.connect(lambda: self.chooseBlackMenu.exec_(QtGui.QCursor().pos()))         
        
        self.whitelab = QLabel('W')
        self.white = QLineEdit('1')
        self.white.keyPressEvent = types.MethodType(blackWhitePressEvent, self.white)
        self.white.setAlignment(Qt.AlignRight | Qt.AlignVCenter)        
        
        self.chooseWhiteMenu = QMenu('White Defaults', self)
        self.chooseWhiteMenu.addAction(QAction("256", self, triggered=lambda: self.chooseWhite('256')))
        self.chooseWhiteMenu.addAction(QAction("1024", self, triggered=lambda: self.chooseWhite('1024')))
        self.chooseWhiteMenu.addAction(QAction("4096", self, triggered=lambda: self.chooseWhite('4096')))        
        self.chooseWhiteMenu.addAction(QAction("16384", self, triggered=lambda: self.chooseWhite('16384')))        
        self.chooseWhiteMenu.addAction(QAction("65536", self, triggered=lambda: self.chooseWhite('65536')))        
        self.white.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)    
        self.white.customContextMenuRequested.connect(lambda: self.chooseWhiteMenu.exec_(QtGui.QCursor().pos())) 
        
        self.gainlab = QLabel('gain')
        self.gain = QLineEdit('1')
        self.gain.keyPressEvent = types.MethodType(offsetGainKeyPressEvent, self.gain)
        self.gain.setAlignment(Qt.AlignRight | Qt.AlignVCenter)        
                
        self.gammalab = QLabel('gamma')
        self.gamma = QLineEdit('1')
        self.gamma.keyPressEvent = types.MethodType(offsetGainKeyPressEvent, self.gamma)
        self.gamma.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.addWidget(self.offsetlab, 1, Qt.AlignRight)
        self.addWidget(self.offset, 1)
        self.addWidget(self.whitelab, 1, Qt.AlignRight)
        self.addWidget(self.white, 1) 
        self.addWidget(self.gainlab, 1, Qt.AlignRight)
        self.addWidget(self.gain, 1)        
        self.addWidget(self.gammalab, 1, Qt.AlignRight)
        self.addWidget(self.gamma, 1)             

        self.offsetGainEdited.connect(self.panel.changeOffsetGain)
        self.blackWhiteEdited.connect(self.panel.changeBlackWhite)             
        
    def chooseBlack(self, sval):
        self.offset.setText(sval)
        blackWhitePressEvent(self.white)        
        
    def chooseWhite(self, sval):
        self.white.setText(sval)
        blackWhitePressEvent(self.white)

    def setOffsetGainInfo(self, offset, gain, white, gamma):
        if not self.offset.hasFocus():
            self.offset.setText(f'{offset:8.6g}')
            self.offset.setCursorPosition(0)
        if not self.gain.hasFocus():
            self.gain.setText(f'{gain:8.6g}')
            self.gain.setCursorPosition(0)
        if not self.white.hasFocus():
            self.white.setText(f'{white:8.6g}')
            self.white.setCursorPosition(0)
        if not self.gamma.hasFocus():
            self.gamma.setText(f'{gamma:8.6g}')
            self.gamma.setCursorPosition(0)

def offsetGainKeyPressEvent(self, event=None):
    key_enter = event is None or (event.key() == Qt.Key_Return) or \
        (event.key() == Qt.Key_Enter)

    if key_enter:
        statpan = self.parent()
        statpan.offsetGainEdited.emit(statpan.offset.text(), statpan.gain.text(), statpan.gamma.text())

    if not event is None:
        QLineEdit.keyPressEvent(self, event)
    
def blackWhitePressEvent(self, event=None):
    key_enter = event is None or (event.key() == Qt.Key_Return) or \
        (event.key() == Qt.Key_Enter)

    if key_enter:
        statpan = self.parent()
        statpan.blackWhiteEdited.emit(statpan.offset.text(), statpan.white.text())

    if not event is None:
        QLineEdit.keyPressEvent(self, event) 
    
    
class StatusPanel(QWidget):

    def __init__(self, parent):        
        super().__init__(parent=parent)                
        self.panel = self.parent()
        
        self.chooseWidgetMenu = CheckMenu('Widgets')    
        
        self.addMenuItem(self.chooseWidgetMenu, 'Zoom',
            lambda: self.toggleWidgetVisible(self.zoomWidget), checkcall=lambda: self.zoomWidget.isVisible())        
        self.addMenuItem(self.chooseWidgetMenu, 'Values',
            lambda: self.toggleWidgetVisible(self.valuePanel), checkcall=lambda: self.valuePanel.isVisible())
        self.addMenuItem(self.chooseWidgetMenu, 'Contrast',
            lambda: self.toggleWidgetVisible(self.contrastPanel),  checkcall=lambda: self.contrastPanel.isVisible())

        self.chooseWidgetBtn = QtWidgets.QToolButton(self)
        self.chooseWidgetBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'menubar.png')))        
        self.chooseWidgetBtn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.chooseWidgetBtn.setMenu(self.chooseWidgetMenu)   
        
        self.zoomWidget = ZoomWidget(self)
        self.valuePanel = ValuePanel(self)
        self.contrastPanel = ContrastPanel(self)
        #self.contrastPanel.hide()                       
                
        hboxlayout = QtWidgets.QHBoxLayout()
        hboxlayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(hboxlayout)
        
        fontmetric = QtGui.QFontMetrics(self.font())
        fontheight = fontmetric.height()
        self.setFixedHeight(fontheight + 2)  
        
        hboxlayout.addWidget(self.chooseWidgetBtn)                       
        splitter = QSplitter(self)        
        hboxlayout.addWidget(splitter)        
        splitter.addWidget(self.zoomWidget)        
        splitter.addWidget(self.valuePanel)        
        splitter.addWidget(self.contrastPanel)                     
        splitter.setSizes([102, 183, 308])

    def addMenuItem(self, menu, text, triggered, checkcall=None, enabled=True, statusTip=None, icon=None, enablecall=None):                   
        action = QAction(text, self, enabled=enabled, statusTip=statusTip)
        action.triggered.connect(triggered)        
        
        if isinstance(icon, str):
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / icon))
        
        if not icon is None:
            action.setIcon(icon)
            
        menu.addAction(action, checkcall=checkcall, enablecall=enablecall)      
        return action        
        
    def toggleWidgetVisible(self, widget):
        widget.setVisible(not widget.isVisible())            
        
    def set_zoom(self, value):
        self.zoomWidget.set_zoom(value)        
        
    def set_val_format(self, fmt='dec'):        
        self.valuePanel.set_val_format(fmt)

    def set_xy_val(self, x, y, val=None):
        self.valuePanel.set_xy_val(x, y, val)

    def setOffsetGainInfo(self, offset, gain, white, gamma):
        self.contrastPanel.setOffsetGainInfo(offset, gain, white, gamma)
