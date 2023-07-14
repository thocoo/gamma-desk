import os
import time
import collections
from pathlib import Path
import types
from collections.abc import Iterable
import queue
import logging

import numpy as np

logger = logging.getLogger(__name__)

try:
    import scipy
    import scipy.ndimage
    has_scipy = True

except:
    has_scipy = False

try:
    import imageio
    has_imafio= True

except:
    has_imafio = False
    
try:
    import cv2
    has_cv2 = True

except:
    has_cv2 = False    

from ... import config, gui

if has_imafio:
    if not config.get("path_imageio_freeimage_lib", None) is None:
        if os.getenv("IMAGEIO_FREEIMAGE_LIB", None) is None:
            os.environ["IMAGEIO_FREEIMAGE_LIB"] = config.get("path_imageio_freeimage_lib")

    try:
        import imageio.plugins.freeimage
        imageio.plugins._freeimage.get_freeimage_lib()

    except Exception as ex:
        logger.warning('Could not load freeimage dll')
        logger.warning(str(ex))
        
    try:
        imageio.plugins.freeimage.download()
        
    except Exception as ex:
        logger.warning('Downloading imageio dll failed')
        logger.warning(str(ex))
        logger.warning('Automatic download can be a problem when using VPN')
        logger.warning("Download the dll's from https://github.com/imageio/imageio-binaries/tree/master/freeimage/")
        logger.warning(f'And place it in {imageio.core.appdata_dir("imageio")}/freeimage')

        #You can also use a system environmental variable
        #IMAGEIO_FREEIMAGE_LIB=<the location>\FreeImage-3.18.0-win64.dll

    #The effective dll is refered at
    #imageio.plugins.freeimage.fi.lib

    #Prefer freeimage above pil
    #Freeimage seems to be a lot faster then pil
    imageio.formats.sort('-FI', '-PIL')

    FILTERS_NAMES = collections.OrderedDict()
    FILTERS_NAMES['All Formats (*)'] = None

    #for fmt in imageio.formats._formats_sorted:
    for fmt in imageio.formats:
        filter = f'{fmt.name} - {fmt.description} (' + ' '.join(f'*{fmt}' for fmt in fmt.extensions) + ')'
        FILTERS_NAMES[filter] = fmt.name

    IMAFIO_QT_READ_FILTERS = ';;'.join(FILTERS_NAMES.keys())
    IMAFIO_QT_WRITE_FILTERS = ';;'.join(FILTERS_NAMES.keys())    
    IMAFIO_QT_WRITE_FILTER_DEFAULT = "TIFF-FI - Tagged Image File Format (*.tif *.tiff)"


from qtpy import QtCore, QtGui, QtWidgets, API_NAME
from qtpy.QtCore import Qt, Signal, QUrl
from qtpy.QtGui import QFont, QTextCursor, QPainter, QPixmap, QCursor, QPalette, QColor, QKeySequence
from qtpy.QtWidgets import (QApplication, QAction, QMainWindow, QPlainTextEdit, QSplitter, QVBoxLayout, QHBoxLayout, QSplitterHandle,
    QMessageBox, QTextEdit, QLabel, QWidget, QStyle, QStyleFactory, QLineEdit, QShortcut, QMenu, QStatusBar, QColorDialog)

from ...panels import BasePanel, thisPanel, CheckMenu
from ...panels.base import MyStatusBar, selectThisPanel
from ...dialogs.formlayout import fedit
from ...dialogs.colormap import ColorMapDialog
from ...widgets.grid import GridSplitter
from ...utils import lazyf, clip_array
from ...utils import imconvert
from ...gcore.utils import ActionArguments
from ...external import client

if has_cv2:
    from .opencv import OpenCvMenu

from .operation import OperationMenu       

from .profile import ProfilerPanel
from .blueprint import make_thumbnail
from .demosaic import bayer_split
from .quantiles import get_sigma_range_for_hist
from .spectrogram import spectr_hori, spectr_vert
from .imgdata import ImageData
from .roi import SelRoiWidget
from .dialogs import RawImportDialog


ZOOM_VALUES = [
     0.005, 0.0064 , 0.008,
     0.01 , 0.0125 , 0.016,
     0.02 , 0.025  , 0.032,
     0.04 , 0.05   , 0.064,
     0.08 , 0.10   , 0.125,
     0.16 , 0.20   , 0.250,
     0.32 , 0.40   , 0.5  ,
     0.64 , 0.80   , 1.0  ,
     1.25 , 1.60   , 2.0  ,
     2.50 , 3.20   , 4.0  ,
     5.00 , 6.40   , 8.0  ,
    10.00 , 12.5   , 16.0 ,
    20.00 , 25.0   , 32.0 ,
    40.00 , 50.0   , 64.0 ,
    80.00 ,100.0   ,125.0 ,
    160.0 ,200.0   ,250.0 ,
    320.0 ,400.0   ,500.0 ,
    640.0 ,800.0   ,1000  ,
    1250  ,1600    ,2000  ,
    2500  ,3200    ,4000]

here = Path(__file__).parent.absolute()
respath = Path(config['respath'])
#sck = config['shortcuts']

channels = ['R', 'G', 'B', 'A']

def getEventPos(event):
    if API_NAME in ['PySide6']:
        pos = event.position()
    else:
        pos = event.pos()        
    return pos

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
        
        # self.hqBtn = QtWidgets.QPushButton('hq')       
        # self.hqBtn.setCheckable(True)
        # self.hqBtn.setFixedWidth(20)
        
        self.addWidget(self.zoomOutBtn)
        self.addWidget(self.zoom, 1)
        self.addWidget(self.zoomInBtn)
        # self.addWidget(self.hqBtn)
        
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
        
        console_font = QFont('Consolas', pointSize=config['console']['fontsize'])                      
        
        self.xy = QLabel('0,0')
        self.vallab = QLabel('val')
        self.val = QLineEdit('0')
        self.val.setFont(console_font)
        self.val.setStyleSheet(f"QLineEdit {{ background: rgb(224, 224, 224); color: rgb(0, 0, 0);}}");
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

    offsetGainEdited = Signal(str, str, str)
    blackWhiteEdited = Signal(str, str)

    def __init__(self, parent):
        super().__init__(parent=parent)

        self.panel = parent.panel
        
        console_font = QFont('Consolas', pointSize=config['console']['fontsize'])

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
        if not self.offset.hasFocus(): self.offset.setText(f'{offset:8.6g}')
        if not self.gain.hasFocus(): self.gain.setText(f'{gain:8.6g}')
        if not self.white.hasFocus(): self.white.setText(f'{white:8.6g}')
        if not self.gamma.hasFocus(): self.gamma.setText(f'{gamma:8.6g}')

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
               

class OpenImage(object):
    def __init__(self, imgpanel, path):
        self.imgpanel = imgpanel
        self.path = path

    def __call__(self):
        self.imgpanel.openImage(self.path)

class RecentMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__('Recent', parent)
        self.imgpanel = self.parent()
        self.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'images.png')))

    def showEvent(self, event):
        self.initactions()

    def initactions(self):
        self.clear()
        self.actions = []

        for rowid, timestamp, path in gui.qapp.history.yield_recent_paths():
            action = QAction(path, self)
            action.triggered.connect(OpenImage(self.imgpanel, path))
            self.addAction(action)
            self.actions.append(action)


class ImageViewerWidget(QWidget):
#class ImageViewerWidget(QtWidgets.QOpenGLWidget):
    #Image size seems to be limitted to 8192x8182
    #Tile shading limitation?

    pickerPositionChanged = Signal(int, int)
    zoomChanged = Signal(float)
    zoomPanChanged = Signal()
    pixelSelected = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent = parent)
        self.imgdata = ImageData()

        self.zoomValue = 1.0
        self.zoomPostScale = 1.0

        self.dispOffsetX = 0
        self.dispOffsetY = 0

        self.dragStartX = None
        self.dragStartY = None

        self.dispRoiStartX = self.dispOffsetX
        self.dispRoiStartY = self.dispOffsetY

        self.setBackgroundColor(*config['image background'])
        
        self.set_val_item_format('dec')

        self.roi = SelRoiWidget(self)

        self.pickCursor = QCursor(QPixmap(str(respath / "icons" / "pixPick256.png")), 15, 15)
        self.dragCursor = QCursor(Qt.OpenHandCursor)

        self.setCursor(self.pickCursor)

        self.setMouseTracking(True)

        self.zoomPanChanged.connect(self.roi.recalcGeometry)

        self.refresh_title()

        self._scaledImage = None
        self.hqzoomout = config['image'].get('render_detail_hq', False)
        self.zoombind = config['image'].get('bind_zoom_absolute', False)

        self.push_selected_pixel = False

        self.setAcceptDrops(True)

    def setBackgroundColor(self, r, g, b):
        palette = self.palette()
        self.bgcolor = QColor(r,g,b)
        palette.setColor(self.backgroundRole(), self.bgcolor)
        self.setPalette(palette)
        #self.setAutoFillBackground(True)
        #This auto fill background seems not to work fine if
        #color is changed at runtime
        #As soon the parent of self is set to None, it retores back to the prior color
        #So it also happens after a relayout. (Even after a distribute)
        #There seems to be some cache of the prior background
        self.qpainter = QPainter()
        

    def set_val_item_format(self, fmt):
        if fmt == 'dec':
            self.val_item_format = '{0:.5g}'
        elif fmt == 'hex':
            self.val_item_format = '0x{0:04X}'
        elif fmt == 'bin':
            self.val_item_format = '{0:_b}'  

        self.val_format = fmt

    @property
    def vd(self):
        return self.imgdata

    def getImageCoordOfMouseEvent(self, event):
        pos = getEventPos(event)
            
        x_float = pos.x() / self.zoomDisplay + self.dispOffsetX
        y_float = pos.y() / self.zoomDisplay + self.dispOffsetY
        #Round down
        return (int(x_float), int(y_float))

    def getImageCoordOfDisplayCenter(self):
        #get the current pixel position as seen on center of screen
        rect = self.geometry()
        centPointX = rect.width() // 2 / self.zoomDisplay + self.dispOffsetX
        centPointY = rect.height() // 2 / self.zoomDisplay + self.dispOffsetY
        return (centPointX, centPointY)

    def setZoomValue(self, value):
        self._scaledImage = None
        self._zoomValue = value

    def getZoomValue(self):
        return self._zoomValue

    def getZoomDisplay(self):
        return self._zoomValue * self.zoomPostScale

    zoomValue = property(getZoomValue, setZoomValue)
    zoomDisplay = property(getZoomDisplay)

    def setHigherZoomValue(self):
        if self.zoomValue in ZOOM_VALUES:
            i = ZOOM_VALUES.index(self.zoomValue)
            self.zoomValue = ZOOM_VALUES[min(i + 1, len(ZOOM_VALUES) - 1)]
            return self.zoomValue

        n = 0
        for zoomVal in ZOOM_VALUES:
            if zoomVal < self._zoomValue:
                n += 1
            else:
                self.zoomValue = ZOOM_VALUES[min(n, len(ZOOM_VALUES) - 1)]
                return self._zoomValue


        self.zoomValue = ZOOM_VALUES[0]
        return self.zoomValue

    def setLowerZoomValue(self):
        if self.zoomValue in ZOOM_VALUES:
            i = ZOOM_VALUES.index(self.zoomValue)
            self.zoomValue = ZOOM_VALUES[max(i - 1, 0)]
            return self.zoomValue

        n = 0
        for zoomVal in ZOOM_VALUES:
            if zoomVal < self.zoomValue:
                n += 1
            else:
                self.zoomValue = ZOOM_VALUES[max(n-1, 0)]
                return self.zoomValue

        self.zoomValue = ZOOM_VALUES[-1]
        return self.zoomValue

    def setClosestZoomValue(self):
        if self.zoomValue in ZOOM_VALUES:
            i = ZOOM_VALUES.index(self.zoomValue)
            self.zoomValue = ZOOM_VALUES[max(i - 1, 0)]
            return self.zoomValue

        n = 0
        for zoomVal in ZOOM_VALUES:
            if zoomVal < self.zoomValue:
                n += 1
            else:
                lower = ZOOM_VALUES[max(n-2, 0)]
                upper = ZOOM_VALUES[max(n-1, 0)]
                if (zoomVal - lower) < (upper - zoomVal):
                    self.zoomValue = lower
                else:
                    self.zoomValue = upper
                return self.zoomValue

        self.zoomValue = ZOOM_VALUES[-1]
        return self.zoomValue

    def setZoom(self, value=1, fixPointX = -1, fixPointY=-1):
        self.zoom(value, fixPointX, fixPointY, step=False)

    def zoomIn(self, fixPointX=-1, fixPointY=-1, fine=False):
        self.zoom(1, fixPointX, fixPointY, step=True, fine=fine)

    def zoomOut(self, fixPointX=-1, fixPointY=-1, fine=False):
        self.zoom(-1, fixPointX, fixPointY, step=True, fine=fine)

    def zoom(self, zoomValue=0, fixPointX=-1, fixPointY=-1, step=True, fine=False):
        self.dragStartX = None
        self.dragStartY = None

        if fixPointX == -1 or fixPointY == -1:
            (fixPointX, fixPointY) = self.getImageCoordOfDisplayCenter()

        tmpX = (fixPointX - self.dispOffsetX) * self.zoomDisplay
        tmpY = (fixPointY - self.dispOffsetY) * self.zoomDisplay

        if step == True:
            if fine:
                self.zoomValue = self.zoomValue + zoomValue * 0.01 * self.zoomValue
            else:
                if zoomValue > 0:
                    self.setHigherZoomValue()
                elif zoomValue < 0:
                    self.setLowerZoomValue()
        else:
            self.zoomValue = zoomValue

        # TO DO
        #Note that there is a rounding effect because the viewer will
        #Always round the top left corner to an integer
        #Start display a full pixel, not a part of a pixel
        #A lot of zoom ins and zoom outs will move the image to bottom, right
        #This effect also exists on the bigger steps but is less pronounced
        self.dispOffsetX = fixPointX - tmpX / self.zoomDisplay
        self.dispOffsetY = fixPointY - tmpY / self.zoomDisplay
        self.zoomPanChanged.emit()
        self.zoomChanged.emit(self.zoomValue)
        self.repaint()

        self.refresh_title()

    def refresh_title(self):
        #self.parent().setWindowTitle(f'Image Viewer {self.parent().id} - {self.zoomValue*100:.3g}%')
        pass

    def set_info_xy(self):
        self.parent().statuspanel.set_xy()

    def zoomAuto(self):
        if self.roi.isVisible():
            if not self.zoomToRoi():
                self.zoomFull()
        else:
            if not self.zoomFull():
                self.zoomFit()

    def zoomFull(self):
        """Zoom to the full image and do a best fit."""
        zoomRegionWidth = self.imgdata.qimg.width()
        zoomRegionHeight = self.imgdata.qimg.height()
        return self.zoomToRegion(0, 0, zoomRegionWidth, zoomRegionHeight, zoomSnap = False)

    def zoomFit(self):
        """Zoom to the full image and do a best fit. Snap of lower zoom value"""
        zoomRegionWidth = self.imgdata.qimg.width()
        zoomRegionHeight = self.imgdata.qimg.height()
        return self.zoomToRegion(0, 0, zoomRegionWidth, zoomRegionHeight, zoomSnap = True)

    def zoomToRoi(self):
        """Zoom to the region of interest and do a best fit."""
        zoomRegionX = self.roi.selroi.xr.start
        zoomRegionY = self.roi.selroi.yr.start
        zoomRegionWidth = self.roi.selroi.xr.stop - self.roi.selroi.xr.start
        zoomRegionHeight =  self.roi.selroi.yr.stop - self.roi.selroi.yr.start
        return self.zoomToRegion(zoomRegionX, zoomRegionY, zoomRegionWidth, zoomRegionHeight)

    def zoomNormalized(self, zoomRegionX, zoomRegionY, zoomRegionWidth, zoomRegionHeight, zoomSnap=True, emit=True, zoomValue=0):
        area = self.imgdata.width * self.imgdata.height
        zoomRegionX *= self.imgdata.width
        zoomRegionY *= self.imgdata.height
        zoomRegionWidth *= self.imgdata.width
        zoomRegionHeight *= self.imgdata.height
        self.zoomToRegion(zoomRegionX, zoomRegionY, zoomRegionWidth, zoomRegionHeight, zoomSnap, emit, zoomValue)

    def zoomToRegion(self, zoomRegionX, zoomRegionY, zoomRegionWidth, zoomRegionHeight, zoomSnap=True, emit=True, zoomValue=0):
        """Zoom to a certain region and do a best fit."""
        self.dragStartX = None
        self.dragStartY = None

        oldZoomValue = self.zoomValue
        oldDispOffsetX = self.dispOffsetX
        oldDispOffsetY = self.dispOffsetY

        xscale = self.width() / zoomRegionWidth
        yscale = self.height() / zoomRegionHeight

        if zoomValue == 0:

            self.zoomValue = min(xscale, yscale)

            if zoomSnap and (not self.zoomValue in ZOOM_VALUES):
                self.setLowerZoomValue()
                #self.setClosestZoomValue()

        else:
            self.zoomValue = zoomValue

        self.dispOffsetX = zoomRegionX - (self.width() / self.zoomDisplay - zoomRegionWidth) / 2
        self.dispOffsetY = zoomRegionY - (self.height() / self.zoomDisplay - zoomRegionHeight) / 2

        if (oldZoomValue != self.zoomValue) or \
            (oldDispOffsetX != self.dispOffsetX) or \
            (oldDispOffsetY != self.dispOffsetY):
            if emit:
                self.zoomPanChanged.emit()
            self.zoomChanged.emit(self.zoomValue)
            self.repaint()
            self.refresh_title()
            return True
        else:
            return False

    def visibleRegion(self, normalized=False, clip_square=False, width=None, height=None):
        width = width or self.width()
        height = height or self.height()
        x, y, w, h = self.dispOffsetX, self.dispOffsetY, width / self.zoomDisplay, height / self.zoomDisplay
        if clip_square:
            if h < w:
                x += (w - h) / 2
                w = h
            elif h > w:
                y += (h - w) / 2
                h = w

        if normalized:
            return x / self.imgdata.width, y / self.imgdata.height, w / self.imgdata.width, h / self.imgdata.height,
        return x, y, w, h

    def panned(self, manhattan=False):
        if (self.dragStartX is None) or (self.dragStartY is None):
            return None

        self.shiftX = (self.dragStartX - self.dragEndX) / self.zoomDisplay
        self.shiftY = (self.dragStartY - self.dragEndY) / self.zoomDisplay

        if manhattan:
            if abs(self.shiftX) < abs(self.shiftY):
                self.shiftX = 0
            else:
                self.shiftY = 0

        if self.shiftX != 0 or self.shiftY != 0:
            self.dispOffsetX = self.dispRoiStartX + self.shiftX
            self.dispOffsetY = self.dispRoiStartY + self.shiftY
            self.zoomPanChanged.emit()
            self.repaint()

    def mouseDoubleClickEvent(self, event):
        self.zoomAuto()

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            fine = True
        else:
            fine = False

        wheel_delta = event.angleDelta().y()
        # QT5: wheel_delta = event.delta()
        
        if wheel_delta < 0:
            self.zoomOut(*self.getImageCoordOfMouseEvent(event), fine)
        else:
            self.zoomIn(*self.getImageCoordOfMouseEvent(event), fine)

    def mousePressEvent(self, event):
        if event.buttons() == Qt.LeftButton or \
            (event.buttons() == Qt.MiddleButton):
            pos = event.pos()
            self.dragStartX = pos.x()
            self.dragStartY = pos.y()
            #roi value at the start of the dragging
            self.dispRoiStartX = self.dispOffsetX
            self.dispRoiStartY = self.dispOffsetY

        elif event.buttons() == Qt.RightButton:
            self.roiDragStartX, self.roiDragStartY = self.getImageCoordOfMouseEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() == Qt.LeftButton) or \
                (event.buttons() == Qt.MiddleButton):
            self.setCursor(self.dragCursor)
            pos = event.pos()
            self.dragEndX = pos.x()
            self.dragEndY = pos.y()
            self.panned(event.modifiers() & QtCore.Qt.ShiftModifier)

        elif (event.buttons() == Qt.RightButton):
            self.roiDragEndX, self.roiDragEndY = self.getImageCoordOfMouseEvent(event)
            self.roi.createState = True
            self.roi.setStartEndPoints(self.roiDragStartX, self.roiDragStartY, \
                self.roiDragEndX, self.roiDragEndY)
            self.roi.show()

        self.pickerPositionChanged.emit(*self.getImageCoordOfMouseEvent(event))

    def dragDistance(self, event):
        if self.dragStartX is None or self.dragStartY is None:
            return None

        pos = event.pos()
        return ((pos.x() - self.dragStartX)**2 + (pos.y() - self.dragStartY)**2) ** 0.5

    def mouseReleaseEvent(self, event):
        drag_distance = self.dragDistance(event)
        if not drag_distance is None and drag_distance <= 2:
            pixel_position = self.getImageCoordOfMouseEvent(event)
            if self.push_selected_pixel:
                panel = gui.qapp.panels.selected('console')
                panel.task.send_input(str(pixel_position))
                self.push_selected_pixel = False
            self.pixelSelected.emit(*pixel_position)

        self.setCursor(self.pickCursor)

        if self.roi.createState:
            self.roi.release_creation()

    def refresh(self):
        self._scaledImage = None
        self.repaint()

    def paintEvent(self, event):
        try:
            self.qpainter.begin(self)
            self.qpainter.fillRect(event.rect(), self.bgcolor)
            self.paintImage(self.qpainter)
        finally:
            self.qpainter.end()

    def scaledImage(self):
        qimg = self.imgdata.qimg
        if self._scaledImage is None:
            self._scaledImage = qimg.scaledToWidth(int(qimg.width() * self.zoomDisplay), Qt.SmoothTransformation)
        return self._scaledImage

    def paintImage(self, qp, position=None):
        if position is None:
            sx = self.dispOffsetX
            sy = self.dispOffsetY
        else:
            sx, sy = position

        qp.setOpacity(1.0)

        if (self.zoomDisplay < 1) and (self.hqzoomout):
            qp.scale(1, 1)
            qp.drawImage(0, 0, self.scaledImage(), int(sx * self.zoomDisplay), int(sy * self.zoomDisplay), -1, -1)

        else:
            if config["image"].get('render_detail_smooth', False) and self.zoomDisplay < 1:
                qp.setRenderHint(qp.RenderHint.SmoothPixmapTransform)

            qp.scale(self.zoomDisplay, self.zoomDisplay)
            qp.translate(-sx, -sy)

            qp.drawImage(0, 0, self.imgdata.qimg, 0, 0, -1, -1)                       

            for layer in self.imgdata.layers.values():
                qp.setCompositionMode(layer['composition'])
                qp.drawImage(0, 0, layer['qimage'], 0, 0, -1, -1)
        
        qp.resetTransform() 
        
        if config['image'].get('pixel_labels', True) and self.zoomDisplay >= 125:
            qp.setPen(QColor(128,128,128))
            
            font = QFont("Consolas")
            fontSize = round(self.zoomDisplay / 10)
            font.setPixelSize(fontSize)
            font.setStyleStrategy(QFont.NoAntialias)            
            
            if self.imgdata.statarr.dtype in ['double']:
                fmt = '{0:.5g}'
            else:
                fmt = self.val_item_format
            
            qp.setFont(font)
            qp.setCompositionMode(QtGui.QPainter.RasterOp_SourceXorDestination)
            #qp.setRenderHint(qp.Antialiasing, False)
            
            x, y, w, h = self.visibleRegion()
            mh, mw = self.imgdata.statarr.shape[:2]
            startx, starty = max(0, round(x - 0.5)), max(0, round(y - 0.5))
            endx, endy = min(mw, round(x + w + 0.5)), min(mh, round(y + h + 0.5))
        
            for sx in range(startx, endx):
                for sy in range(starty, endy):     
                    xpos = round((sx + 0.05 - self.dispOffsetX) * self.zoomDisplay)
                    ypos = round((sy + 0.95 - self.dispOffsetY) * self.zoomDisplay)
                    val = self.imgdata.statarr[sy, sx]                    
                    
                    if isinstance(val, Iterable):
                        values = list(val)
                        ypos -= (len(values) - 1) * (fontSize + 1)
                        for i, v in enumerate(values):
                            try:
                                label = fmt.format(v)
                            except:
                                label = 'invalid'
                            qp.drawText(xpos, ypos + i * (fontSize + 1), f'{channels[i]}: {label}')    
                    else:
                        try:
                            label = fmt.format(val)
                        except:
                            label = 'invalid'
                        qp.drawText(xpos, ypos, label)

    def dragEnterEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        panel = thisPanel(self)
        mimeData = event.mimeData()

        dropedInFiles = []
        if mimeData.hasUrls():
            filenamelist = []

            for url in mimeData.urls():
                filename = url.toString(QUrl.FormattingOptions(QUrl.RemoveScheme)).replace('///','')
                dropedInFiles.append(filename)

        elif mimeData.hasText():

            filename = mimeData.text()
            dropedInFiles.append(filename)

        panel.openImage(dropedInFiles[0])

        for path in dropedInFiles[1:]:
            gui.img.open(path)


class ImageViewerBase(BasePanel):
    panelCategory = 'image'
    panelShortName = 'base'
    userVisible = False

    contentChanged = Signal(int, bool)
    gainChanged = Signal(int, bool)
    visibleRegionChanged = Signal(float, float, float, float, bool, bool, float)
    roiChanged = Signal(int)

    classIconFile = str(respath / 'icons' / 'px16' / 'picture.png')

    def __init__(self, parent=None, panid=None, **kwargs):
        super().__init__(parent, panid, type(self).panelCategory)

        self.offset = 0
        self.white = 256
        self.gamma = 1
        self.colormap = config['image color map']

        self.defaults = dict()
        self.defaults['offset'] = 0
        self.defaults['gain'] = 1
        self.defaults['gamma'] = 1

        self.createMenus()
        self.createStatusBar()                

    def createMenus(self):
        self.fileMenu = self.menuBar().addMenu("&File")
        #self.editMenu = self.menuBar().addMenu("&Edit")
        self.editMenu = CheckMenu("&Edit", self.menuBar())
        self.menuBar().addMenu(self.editMenu)
        self.viewMenu = CheckMenu("&View", self.menuBar())
        self.menuBar().addMenu(self.viewMenu)
        self.selectMenu = self.menuBar().addMenu("&Select")
        self.canvasMenu = self.menuBar().addMenu("&Canvas")
        #self.imageMenu = self.menuBar().addMenu("&Image")
        self.imageMenu = CheckMenu("&Image", self.menuBar())
        self.processMenu = self.menuBar().addMenu("&Process")
        self.analyseMenu = self.menuBar().addMenu("&Analyse")
        
        if has_cv2:
            self.openCvMenu = OpenCvMenu("Open CV", self.menuBar(), self)
        
        self.operationMenu = OperationMenu("Operation", self.menuBar(), self)

        ### File
        self.addMenuItem(self.fileMenu, 'New...'            , self.newImage,
            statusTip="Make a new image in this image viewer",
            icon = 'picture_empty.png')
        self.addMenuItem(self.fileMenu, 'Duplicate'         , self.duplicate,
            statusTip="Duplicate the image to a new image viewer",
            icon = 'application_double.png')
        self.addMenuItem(self.fileMenu, 'Open Image...' , self.openImageDialog,
            statusTip="Open an image",
            icon = 'folder_image.png')
        self.addMenuItem(self.fileMenu, 'Import Raw Image...', self.importRawImage,
            statusTip="Import Raw Image",
            icon = 'picture_go.png')
        self.fileMenu.addMenu(RecentMenu(self))
        self.addMenuItem(self.fileMenu, 'Save Image...' , self.saveImageDialog,
            statusTip="Save the image",
            icon = 'picture_save.png')
            
        self.addMenuItem(self.fileMenu, 'Send to other GDesk' , self.send_array_to_gdesk)
            
        self.addMenuItem(self.fileMenu, 'Close' , self.close_panel,
            statusTip="Close this image panel",
            icon = 'cross.png')

        ### Edit

        self.addMenuItem(self.editMenu, 'Show Prior Image', self.piorImage,
            enablecall = lambda: self.imviewer.imgdata.imghist.prior_length() > 0,
            statusTip="Get the prior image from the history stack and show it",
            icon = 'undo.png')
        self.addMenuItem(self.editMenu, 'Show Next Image', self.nextImage,
            enablecall = lambda: self.imviewer.imgdata.imghist.next_length() > 0,
            statusTip="Get the next image from the history stack and show it",
            icon = 'redo.png')

        self.editMenu.addSeparator()

        self.addMenuItem(self.editMenu, 'Copy 8bit Image to clipboard', self.placeRawOnClipboard,
            statusTip="Place the 8bit image on clipboard, offset and gain applied",
            icon = 'page_copy.png')
        self.addMenuItem(self.editMenu, 'Copy Display Image to clipboard', self.placeQimgOnClipboard,
            statusTip="Place the displayed image on clipboard with display processing applied",
            icon = 'page_copy.png')
        self.addMenuItem(self.editMenu, 'Paste into New Image', self.showFromClipboard,
            statusTip="Paste content of clipboard in this image viewer",
            icon = 'picture_clipboard.png')
        self.addMenuItem(self.editMenu, 'Grab Desktop', self.grabDesktop,
            icon = 'lcd_tv_image.png')

        self.editMenu.addSeparator()

        ### View
        self.addMenuItem(self.viewMenu, 'Refresh', self.refresh,
            statusTip="Refresh the image",
            icon = 'update.png')
        self.addMenuItem(self.viewMenu, 'Zoom In' , self.zoomIn,
            statusTip="Zoom in 1 step",
            icon = 'zoom_in.png')
        self.addMenuItem(self.viewMenu, 'Zoom Out', self.zoomOut,
            statusTip="Zoom out 1 step",
            icon = 'zoom_out.png')

        zoomMenu = QMenu('Zoom')
        zoomMenu.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'zoom.png')))
        self.viewMenu.addMenu(zoomMenu)
        self.addMenuItem(zoomMenu, 'Zoom 100%', self.setZoom100,
            statusTip="Zoom to a actual size (100%)",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'zoom_actual.png')))
        self.addMenuItem(zoomMenu, 'Zoom Fit'     , self.zoomFit,
            statusTip="Zoom to fit the image in the image viewer, snap on predefined zoom value",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'zoom_fit.png')))
        self.addMenuItem(zoomMenu, 'Zoom Full'    , self.zoomFull,
            statusTip="Zoom to fit the image in the image viewer",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'zoom_extend.png')))
        self.addMenuItem(zoomMenu, 'Zoom Auto'    , self.zoomAuto,
            statusTip="Toggle between to to selection and full image",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'zoom_refresh.png')))
        self.addMenuItem(zoomMenu, 'Zoom exact...'     , self.setZoom,
            statusTip="Zoom to a defined value",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'zoom_actual_equal.png')))

        self.viewMenu.addSeparator()

        self.addMenuItem(self.viewMenu, 'Default Offset && Gain', self.defaultOffsetGain,
            statusTip="Apply default offset, gain and gamma",
            icon=QtGui.QIcon(str(respath / 'icons' / 'px16' / 'unmark_to_download.png')))
        self.addMenuItem(self.viewMenu, 'Set Current as Default', self.setCurrentOffsetGainAsDefault,
            statusTip="Set the current offset, gain and gamma as default")
        self.addMenuItem(self.viewMenu, 'Offset && Gain...', self.offsetGainDialog,
            statusTip="Set offset and gain",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'weather_cloudy.png')))
        self.addMenuItem(self.viewMenu, 'Black && White...', self.blackWhiteDialog,
            statusTip="Set the black and white point",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'color_adjustment.png')))
        self.addMenuItem(self.viewMenu, 'Grey && Gain...', self.changeGreyGainDialog,
            statusTip="Set the mid grey level and gain",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'contrast.png')))
        self.addMenuItem(self.viewMenu, 'Gain to Min-Max', self.gainToMinMax,
            statusTip="Auto level to min and max")
        self.gainSigmaMenu = QMenu('Gain to Sigma')
        self.viewMenu.addMenu(self.gainSigmaMenu)
        self.addMenuItem(self.gainSigmaMenu, 'Gain to Sigma 1', self.gainToSigma1)
        self.addMenuItem(self.gainSigmaMenu, 'Gain to Sigma 2', self.gainToSigma2)
        self.addMenuItem(self.gainSigmaMenu, 'Gain to Sigma 3', self.gainToSigma3)

        self.viewMenu.addSeparator()

        self.addMenuItem(self.viewMenu, 'HQ Zoom Out', self.toggle_hq,
            checkcall = lambda: self.imviewer.hqzoomout,
            statusTip = "Use high quality resampling on zoom levels < 100%")
            
        self.bindMenu = CheckMenu("Bind", self.viewMenu)
        self.addMenuItem(self.bindMenu, 'Bind All Image Viewers', self.bindImageViewers)
        self.addMenuItem(self.bindMenu, 'Unbind All Image Viewers', self.unbindImageViewers)        
        self.addMenuItem(self.bindMenu, 'Absolute Zoom Link', self.toggle_zoombind,
            checkcall = lambda: self.imviewer.zoombind,
            statusTip = "If binded to other image viewer, bind with absolute zoom value")        
        
        self.addMenuItem(self.viewMenu, 'Colormap...'    , self.setColorMap,
            statusTip="Set the color map for monochroom images",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'dopplr.png')))
        self.addMenuItem(self.viewMenu, 'Background Color...'    , self.setBackground,
            statusTip="Set the background color...",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'document_background.png')))
        self.addMenuItem(self.viewMenu, 'Selection Color...'    , self.setRoiColor,
            statusTip="Set the Selection color...",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'color_swatch.png')))

        self.chooseValFormat = QMenu('Value Format')
        self.chooseValFormat.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'pilcrow.png')))
        self.chooseValFormat.addAction(QAction("Decimal", self, triggered=lambda: self.statuspanel.set_val_format('dec')))
        self.chooseValFormat.addAction(QAction("Hex", self, triggered=lambda: self.statuspanel.set_val_format('hex')))
        self.chooseValFormat.addAction(QAction("Binary", self, triggered=lambda: self.statuspanel.set_val_format('bin')))
        self.chooseValFormat.addAction(QAction("Pixel Labels", self, triggered=self.togglePixelLabels))
        self.viewMenu.addMenu(self.chooseValFormat)

        ### Select
        self.addMenuItem(self.selectMenu, 'Select Full Image', self.selectAll,
            statusTip="Select Full Image")
        self.addMenuItem(self.selectMenu, 'Deselect', self.selectNone,
            statusTip="Deselect, select nothing")
        self.addMenuItem(self.selectMenu, 'Select dialog...', self.setRoi,
            statusTip="Select with input numbers dialog",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'region_of_interest.png')))
        self.addMenuItem(self.selectMenu, 'Copy slices to clipboard...', self.copySliceToClipboard,
            statusTip="Copy the slice definition to the clipboard")            
        self.addMenuItem(self.selectMenu, 'Jump to Coordinates'   , self.jumpToDialog,
            statusTip="Select 1 pixel and zoom to it",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'canvas.png')))
        self.addMenuItem(self.selectMenu, 'Mask Value...'   , self.maskValue,
            statusTip="Mask pixels based on value",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'find.png')))

        ### Canvas
        self.addMenuItem(self.canvasMenu, 'Flip Horizontal', self.flipHorizontal,
            statusTip="Flip the image Horizontal",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'shape_flip_horizontal.png')))
        self.addMenuItem(self.canvasMenu, 'Flip Vertical'  , self.flipVertical,
            statusTip="Flip the image Vertical",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'shape_flip_vertical.png')))
        self.addMenuItem(self.canvasMenu, 'Rotate Left 90' , self.rotate90,
            statusTip="Rotate the image 90 degree anti clockwise",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'shape_rotate_anticlockwise.png')))
        self.addMenuItem(self.canvasMenu, 'Rotate Right 90', self.rotate270,
            statusTip="Rotate the image 90 degree clockwise",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'shape_rotate_clockwise.png')))
        self.addMenuItem(self.canvasMenu, 'Rotate 180'     , self.rotate180,
            statusTip="Rotate the image 180 degree")
        self.addMenuItem(self.canvasMenu, 'Rotate any Angle...', triggered=self.rotateAny, enabled=has_scipy,
            statusTip="Rotate any angle")
        self.addMenuItem(self.canvasMenu, 'Crop on Selection', self.crop,
            statusTip="Crop the image on the current rectangle selection",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'transform_crop.png')))
        self.addMenuItem(self.canvasMenu, 'Resize Canvas...', self.canvasResize,
            statusTip="Add or remove borders",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'canvas_size.png')))
        self.addMenuItem(self.canvasMenu, 'Resize Image', triggered=self.resize, enabled=has_scipy,
            statusTip="Resize the image by resampling",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'resize_picture.png')))

        ### Image
        self.addMenuItem(self.imageMenu, 'Swap RGB | BGR', self.swapRGB,
            statusTip="Swap the blue with red channel",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'color.png')))
        self.addMenuItem(self.imageMenu, 'to Monochroom', self.toMonochroom,
            statusTip="Convert an RGB image to monochroom grey",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'convert_color_to_gray.png')))
        self.addMenuItem(self.imageMenu, 'to Photometric Monochroom', self.toPhotoMonochroom,
            statusTip="Convert an RGB image to photometric monochroom grey",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'convert_color_to_gray.png')))
        self.addMenuItem(self.imageMenu, 'to 8-bit', self.to8bit,
            enablecall = self.is16bit)
        self.addMenuItem(self.imageMenu, 'to 16-bit', self.to16bit,
            enablecall = self.is8bit)
        self.addMenuItem(self.imageMenu, 'to Data Type', self.to_dtype)
        self.addMenuItem(self.imageMenu, 'Swap MSB LSB Bytes', self.swapbytes,
            enablecall = self.is16bit)
        
        self.addMenuItem(self.imageMenu, 'Fill...'          , self.fillValue,
            statusTip="Fill the image with the same value",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'paintcan.png')))
        self.addMenuItem(self.imageMenu, 'Add noise...'     , self.addNoise,
            statusTip="Add Gaussian noise")
        self.addMenuItem(self.imageMenu, 'Invert', self.invert,
            statusTip="Invert the image")
        self.addMenuItem(self.imageMenu, 'Adjust Lighting...', self.adjustLighting,
            statusTip="Adjust the pixel values",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'contrast.png')))
        self.addMenuItem(self.imageMenu, 'Adjust Gamma...', self.adjustGamma,
            statusTip="Adjust the gamma")

        #Process
        self.addMenuItem(self.processMenu, 'Bayer Split', self.bayer_split_tiles,
            statusTip="Split to 4 images based on the Bayer kernel",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'pictures_thumbs.png')))
        self.addMenuItem(self.processMenu, 'Colored Bayer', self.colored_bayer)
        self.addMenuItem(self.processMenu, 'Demosaic', self.demosaic, enabled=has_scipy,
            statusTip="Demosaic",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'things_digital.png')))
        self.addMenuItem(self.processMenu, 'Make Blueprint', self.makeBlueprint,
            statusTip="Make a thumbnail (8x smaller) with blowup high frequencies",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'map_blue.png')))

        #Analyse
        self.addMenuItem(self.analyseMenu, 'Horizontal Spectrogram', self.horizontalSpectrogram,
            statusTip="Horizontal Spectrogram")
        self.addMenuItem(self.analyseMenu, 'Vertical Spectrogram', self.verticalSpectrogram,
            statusTip="Vertical Spectrogram")
        self.addMenuItem(self.analyseMenu, 'Measure Distance', self.measureDistance,
            statusTip="Measure Distance",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'geolocation_sight.png')))

        self.addBaseMenu(['levels', 'values', 'image'])                                

    def get_select_menu(self):
        #The select menu should be index 4 from the menuBar children
        return self.menuBar().children()[4]

    def createStatusBar(self):
        self.statuspanel = StatusPanel(self)
        self.statusBar().addWidget(self.statuspanel)

    def set_info_xy_val(self, x, y):
        try:
            val = self.imviewer.imgdata.statarr[y, x]

        except:
            val = None

        self.statuspanel.set_xy_val(x, y, val)

    def addBindingTo(self, category, panid):
        targetPanel = super().addBindingTo(category, panid)
        if targetPanel is None: return None
        if targetPanel.category == 'image':
            self.visibleRegionChanged.connect(targetPanel.changeVisibleRegion)
        elif targetPanel.category == 'levels':
            self.contentChanged.connect(targetPanel.imageContentChanged)
            self.roiChanged.connect(targetPanel.roiChanged)
            self.gainChanged.connect(targetPanel.imageGainChanged)
        elif targetPanel.category == 'values':
            self.imviewer.pixelSelected.connect(targetPanel.pick)
        return targetPanel

    def removeBindingTo(self, category, panid):
        targetPanel = super().removeBindingTo(category, panid)
        if targetPanel is None: return None
        if targetPanel.category == 'image':
            self.visibleRegionChanged.disconnect(targetPanel.changeVisibleRegion)
        elif targetPanel.category == 'levels':
            self.contentChanged.disconnect(targetPanel.imageContentChanged)
            self.gainChanged.disconnect(targetPanel.imageGainChanged)
        elif targetPanel.category == 'values':
            self.imviewer.pixelSelected.disconnect(targetPanel.pick)
        return targetPanel

    def changeVisibleRegion(self, x, y, w, h, zoomSnap, emit, zoomValue):
        self.imviewer.zoomNormalized(x, y, w, h, zoomSnap, emit, zoomValue)
        self.imviewer.roi.recalcGeometry()

    ############################
    # File Menu Connections
    def newImage(self):

        with ActionArguments(self) as args:
            args['width'] = 1920*2
            args['height'] = 1080*2
            args['channels'] = 1
            args['dtype'] = 'uint8'
            args['mean'] = 128

        if args.isNotSet():
            dtypes = ['uint8', 'int8', 'uint16', 'int16', 'uint32', 'int32', 'float32', 'float64']

            options_form = [('Width', args['width']),
                       ('Height', args['height']),
                       ('Channels', args['channels']),
                       ('dtype', [1] + dtypes),
                       ('mean', args['mean'])]

            result = fedit(options_form)
            if result is None: return
            args['width'], args['height'], args['channels'], dtype_ind, args['mean'] = result
            args['dtype'] = dtypes[dtype_ind-1]

        shape = [args['height'], args['width']]
        if args['channels'] > 1: shape = shape + [args['channels']]

        arr = np.ndarray(shape, args['dtype'])
        arr[:] = args['mean']

        self.show_array(arr, zoomFitHist=True)

    def duplicate(self, floating=False):
        newPanel = super().duplicate(floating)
        newPanel.show_array(self.ndarray)
        return newPanel

    def openImageDialog(self):
        filepath = here / 'images' / 'default.png'

        with ActionArguments(self) as args:
            args['filepath'] = here / 'images' / 'default.png'
            args['format'] = None

        if args.isNotSet():
            if has_imafio:
                args['filepath'], filter = gui.getfile(filter=IMAFIO_QT_READ_FILTERS, title='Open Image File (Imafio)', file=str(args['filepath']))
                if args['filepath'] == '': return
                args['format'] = FILTERS_NAMES[filter]

            else:
                args['filepath'], filter = gui.getfile(title='Open Image File (PIL)', file=str(args['filepath']))
                args['format'] = None
                if args['filepath'] == '': return

        self.openImage(args['filepath'], args['format'])

    def openImage(self, filepath, format=None, zoom='full'):
        if has_imafio:
            arr = self.openImageImafio(filepath, format)
        else:
            arr = self.openImagePIL(filepath)

        if not arr is None:
            self.long_title = str(filepath)
            gui.qapp.history.storepath(str(filepath))            
            
            if arr.dtype == 'uint8':                
                self.offset = 0
                self.white = 1 << 8
                self.gamma = 1
                
            elif arr.dtype == 'uint16':
                self.offset = 0
                self.white = 1 << 16
                self.gamma = 1
                
            self.show_array(arr, zoomFitHist=True)
            if zoom == 'full':
                self.zoomFull()
            else:
                self.setZoomValue(zoom)

    def openImagePIL(self, filepath):
        with gui.qapp.waitCursor(f'Opening image using PIL {filepath}'):
            from PIL import Image
            logger.info(f'Using PIL library')
            image = Image.open(str(filepath))
            arr = np.array(image)
        return arr

    def openImageImafio(self, filepath, format=None):
        with gui.qapp.waitCursor(f'Opening image using imageio {filepath} {format}'):
            logger.info(f"Using FormatClass {repr(imageio.imopen(filepath, 'r').__class__)}")
            arr = imageio.imread(str(filepath), format=format)
        return arr

    def importRawImage(self):
        import struct

        filepath = here / 'images' / 'default.png'
        filepath = gui.getfile(file=str(filepath))[0]
        if filepath == '': return

        fp = open(filepath, 'br')
        data = fp.read()
        fp.close()

        #somehwhere in the header, there is the resolution
        #image studio: 128 bytes header, 4 bytes=width, 4 bytes=height, 120 bytes=???
        header = 128
        dtype = 'uint16'
        width = struct.unpack('<I', data[0:4])[0]
        height = struct.unpack('<I', data[4:8])[0]
        
        print(f'Width x Height: {width} x {height}')
                
        dialog = RawImportDialog(data)
        dialog.form.offset.setText(str(header))
        dialog.form.dtype.setText(dtype)
        dialog.form.width.setText(str(width))
        dialog.form.height.setText(str(height))
        dialog.exec_()
        
        offset = int(dialog.form.offset.text())
        dtype = dialog.form.dtype.text()
        byteorder = dialog.form.byteorder.currentText()
        width = int(dialog.form.width.text())
        height = int(dialog.form.height.text())


        with gui.qapp.waitCursor():
            dtype = np.dtype(dtype)

            leftover = len(data) - (width * height  * dtype.itemsize + offset)

            if leftover > 0:
                print('Too much data found (%d bytes too many)' % leftover)

            elif leftover < 0:
                print('Not enough data found (missing %d bytes)' % (-leftover))

            arr = np.ndarray(shape=(height, width), dtype=dtype, buffer=data[offset:])
            if byteorder == 'big endian':
                arr = arr.byteswap()
            self.show_array(arr, zoomFitHist=True)
            self.zoomFull()
            gui.qapp.history.storepath(str(filepath))

    def saveImageDialog(self):
        if has_imafio:
            filepath, filter = gui.putfile(filter=IMAFIO_QT_WRITE_FILTERS, title='Save Image using Imafio',
                                    defaultfilter=IMAFIO_QT_WRITE_FILTER_DEFAULT)
            if filepath == '': return
            format = FILTERS_NAMES[filter]
            self.saveImage(filepath, format)
        else:
            filepath, filter = gui.putfile(title='Save Image using PIL')
            if filepath == '': return
            self.saveImage(filepath)

    def saveImage(self, filepath, format=None):
        if has_imafio:
            self.saveImageImafio(filepath, format)
        else:
            self.saveImagePIL(filepath)

        gui.qapp.history.storepath(str(filepath))

    def saveImagePIL(self, filepath):
        with gui.qapp.waitCursor():
            from PIL import Image

            image = Image.fromarray(self.ndarray)
            image.save(str(filepath))

    def saveImageImafio(self, filepath, format):
        if format is None:
            from imageio.core import Request
            format = imageio.formats.search_write_format(Request(filepath, 'wi')).name

        if format == 'JPEG-FI':
            (quality, progressive, optimize, baseline) = gui.fedit([('quality', 90), ('progressive', False), ('optimize', False), ('baseline', False)])

            with gui.qapp.waitCursor(f'Saving to {filepath}'):
                imageio.imwrite(filepath, self.ndarray, format,
                    quality=quality, progressive=progressive,
                    optimize=optimize, baseline=baseline)

        elif format == 'TIFF-FI':
            compression_options = {
                'none': imageio.plugins.freeimage.IO_FLAGS.TIFF_NONE,
                'default': imageio.plugins.freeimage.IO_FLAGS.TIFF_DEFAULT,
                'packbits': imageio.plugins.freeimage.IO_FLAGS.TIFF_PACKBITS,
                'adobe': imageio.plugins.freeimage.IO_FLAGS.TIFF_ADOBE_DEFLATE,
                'lzw': imageio.plugins.freeimage.IO_FLAGS.TIFF_LZW,
                'deflate': imageio.plugins.freeimage.IO_FLAGS.TIFF_DEFLATE,
                'logluv': imageio.plugins.freeimage.IO_FLAGS.TIFF_LOGLUV}
            (compression_index,) = gui.fedit([('compression', [2] + list(compression_options.keys()))])
            compression = list(compression_options.keys())[compression_index-1]
            compression_flag = compression_options[compression]

            with gui.qapp.waitCursor(f'Saving to {filepath}'):
                imageio.imwrite(filepath, self.ndarray, format, flags=compression_flag)

        elif format == 'PNG-FI':
            compression_options = [('None', 0), ('Best Speed', 1), ('Default', 6), ('Best Compression', 9)]
            (compression_index, quantize, interlaced) = gui.fedit([('compression', [2] + [item[0] for item in compression_options]), ('quantize', 0), ('interlaced', True)])
            compression = compression_options[compression_index-1][1]

            print(f'compression: {compression}')

            with gui.qapp.waitCursor(f'Saving to {filepath}'):
                imageio.imwrite(filepath, self.ndarray, format, compression=compression, quantize=quantize, interlaced=interlaced)

        elif format == 'PNG-PIL':
            compression_options = [('None', 0), ('Best Speed', 1), ('Default', 6), ('Best Compression', 9)]
            (compression_index, quantize, optimize) = gui.fedit([('compression', [4] + [item[0] for item in compression_options]), ('quantize', 0), ('optimize', True)])
            compression = compression_options[compression_index-1][1]
            if quantize == 0: quantize = None

            print(f'compression: {compression}')

            with gui.qapp.waitCursor(f'Saving to {filepath}'):
                imageio.imwrite(filepath, self.ndarray, format, compression=compression,
                    quantize=quantize, optimize=optimize, prefer_uint8=False)

        else:
            with gui.qapp.waitCursor(f'Saving to {filepath}'):
                imageio.imwrite(filepath, self.ndarray, format)
                
                
    def send_array_to_gdesk(self):
        port = gui._qapp.cmdserver.port
        hostname = 'localhost'
        
        form = [('port', port), ('host', hostname), ('new panel', False)]
        results = fedit(form)
        if results is None: return
        
        port = results[0]        
        hostname = results[1]
        new = results[2]
        
        client.send_array_to_gui(self.ndarray, port, hostname, new)

    def close_panel(self):
        super().close_panel()

        #Deleting self.imviewer doesn't seem to delete the imgdata
        del self.imviewer.imgdata


    ############################
    # Edit Menu Connections

    def piorImage(self):
        if self.imviewer.imgdata.imghist.prior_length() > 0:
            arr = self.imviewer.imgdata.imghist.prior(self.ndarray)
            self.show_array(arr, log=False)

    def nextImage(self):
        if self.imviewer.imgdata.imghist.next_length() > 0:
            arr = self.imviewer.imgdata.imghist.next(self.ndarray)
            self.show_array(arr, log=False)

    #---------------------------

    def placeRawOnClipboard(self):
        clipboard = self.qapp.clipboard()
        array = self.ndarray
        qimg = imconvert.process_ndarray_to_qimage_8bit(array, 0, 1)
        clipboard.setImage(qimg)

    def placeQimgOnClipboard(self):
        clipboard = self.qapp.clipboard()
        #If qimg is not copied, GH crashes on paste after the qimg instance has been garbaged!
        #Clipboard can only take ownership if the object is a local?
        qimg = self.imviewer.imgdata.qimg.copy()
        clipboard.setImage(qimg)

    def showFromClipboard(self):
        arr = gui.get_clipboard_image()
        self.show_array(arr)
        
    def grabDesktop(self):       
        screens = self.qapp.screens()    
        screen_names = [1] + [sc.name() for sc in screens]
        form = [
            ('Screen', screen_names),
            ('Delay', 1.0)]
        
        results = fedit(form)
        
        if results is None: return
        
        screen_index, delay = results
        screen_name = screen_names[screen_index]
        
        screen = [sc for sc in screens if sc.name() == screen_name][0]        
        
        def screenGrab():
            pixmap = screen.grabWindow(0)
            
            qimage = pixmap.toImage()
            arr = imconvert.qimage_to_ndarray(qimage)
            self.show_array(arr)
        
        QtCore.QTimer.singleShot(delay * 1000, screenGrab)               

    ############################
    # View Menu Connections

    def refresh(self):
        #with gui.qapp.waitCursor(f'Refreshing {self.short_title}'):
        self.show_array(None)
        
    def get_gain(self):
        natrange = self.imviewer.imgdata.get_natural_range()
        gain = natrange / (self.white - self.offset)
        return gain
        
    def set_gain(self, gain):
        natrange = self.imviewer.imgdata.get_natural_range()
        self.white = self.offset + natrange / gain
        
    gain = property(get_gain, set_gain)

    def offsetGainDialog(self):

        with ActionArguments(self) as args:
            args['offset'] = self.offset
            args['gain'] = self.gain
            args['gamma'] = self.gamma
            args['cmap'] = self.colormap

        if args.isNotSet():
            colormaps = imconvert.colormaps
            cmapind = colormaps.index(self.colormap) + 1

            form = [('Offset', self.offset * 1.0),
                    ('Gain', self.gain * 1.0),
                    ('Gamma', self.gamma * 1.0),
                    ('Color Map', [cmapind] + colormaps)]

            results = fedit(form)
            if results is None: return
            offset, gain, gamma, cmapind = results
            self.colormap = colormaps[cmapind-1]

        else:
            offset, gain = args['offset'], args['gain']
            gamma, self.colormap = args['gamma'], args['cmap']

        self.changeOffsetGain(offset, gain, gamma)


    def setCurrentOffsetGainAsDefault(self):
        self.defaults['offset'] = self.offset
        self.defaults['gain'] = self.gain
        self.defaults['gamma'] = self.gamma


    def defaultOffsetGain(self):
        offset = self.defaults['offset']
        gain = self.defaults['gain']
        gamma = self.defaults['gamma']
        self.changeOffsetGain(offset, gain, gamma)


    def changeOffsetGain(self, offset, gain, gamma, reset_levels=True):
        if isinstance(offset, str):
            if offset == 'default':
                offset = self.defaults['offset']
            else:
                offset = eval(offset)
        if isinstance(gain, str):
            if gain == 'default':
                gain = self.defaults['gain']
            else:
                gain = eval(gain)
        if isinstance(gamma, str):
            if gamma == 'default':
                gamma = self.defaults['gamma']
            else:
                gamma = eval(gamma)

        if not offset is None: self.offset = offset
        if not gain is None: self.gain = gain
        if not gamma is None: self.gamma = gamma
        self.refresh_offset_gain(zoomFitHist=reset_levels)

    def blackWhiteDialog(self):

        with ActionArguments(self) as args:
            args['black'] = self.offset
            args['white'] = self.white
            args['cmap'] = self.colormap

        if args.isNotSet():
            colormaps = imconvert.colormaps
            cmapind = colormaps.index(self.colormap) + 1

            black = self.offset
            gain1_range = self.imviewer.imgdata.get_natural_range()

            form = [('Black', black),
                    ('White', self.white),
                    ('Color Map', [cmapind] + colormaps)]

            results = fedit(form)
            if results is None: return
            black, white, cmapind = results
            self.colormap = colormaps[cmapind-1]

        else:
            black, white = args['black'], args['white']
            self.colormap  = args['cmap']

        self.changeBlackWhite(black, white)

    def changeBlackWhite(self, black, white):
        if isinstance(black, str):
            black = eval(black)
        if isinstance(white, str):
            white = eval(white)

        if black == white:
            print(f'Warning: black and white are set the same ({black}). Setting to mid grey!')
            self.changeMidGrey(black)
            return

        gain1_range = self.imviewer.imgdata.get_natural_range()

        if not (black is None or white is None):
            self.offset = black
            self.gain = gain1_range / (white - black)
        elif white is None:
            white = self.white
            self.offset = black
            self.gain = gain1_range / (white - self.offset)
        elif black is None:
            self.gain = gain1_range / (white - self.offset)

        self.refresh_offset_gain()

    def changeGreyGainDialog(self):

        gain1_range = self.imviewer.imgdata.get_natural_range()
        grey = self.offset + gain1_range / self.gain / 2

        with ActionArguments(self) as args:
            args['grey'] = grey
            args['gain'] = self.gain
            args['cmap'] = self.colormap

        if args.isNotSet():
            colormaps = imconvert.colormaps
            cmapind = colormaps.index(self.colormap) + 1

            form = [('Grey', grey),
                    ('Gain', self.gain * 1.0),
                    ('Color Map', [cmapind] + colormaps)]

            results = fedit(form)
            if results is None: return
            grey, gain, cmapind = results
            self.colormap = colormaps[cmapind-1]

        else:
            grey = args['grey']
            gain = args['gain']
            self.colormap = args['cmap']

        self.changeMidGrey(grey, gain)

    def changeMidGrey(self, midgrey, gain=None):
        if not gain is None: self.gain = gain
        gain1_range = self.imviewer.imgdata.get_natural_range()
        self.offset = midgrey - gain1_range / self.gain / 2
        self.refresh_offset_gain()

    def gainToMinMax(self):
        black = self.ndarray.min()
        white = self.ndarray.max()
        self.changeBlackWhite(black, white)

    def gainToSigma1(self):
        with gui.qapp.waitCursor('Gain 1 sigma'):
            self.gainToSigma(1)

    def gainToSigma2(self):
        with gui.qapp.waitCursor('Gain 2 sigma'):
            self.gainToSigma(2)

    def gainToSigma3(self):
        with gui.qapp.waitCursor('Gain 3 sigma'):
            self.gainToSigma(3)

    def gainToSigma(self, sigma=3, roi=None):
        chanstats = self.imviewer.imgdata.chanstats

        if roi is None:
            roi = self.imviewer.roi.isVisible()

        elif roi and not self.imviewer.roi.isVisible():
            roi = False

        if roi:
            clrs = set(('RK','RR', 'RG', 'RB'))
        else:
            clrs = set(('K', 'R', 'G', 'B'))

        clrs = clrs.intersection(set(chanstats.keys()))

        blacks = dict()
        whites = dict()
        for clr in clrs:
            stats = chanstats[clr]
            if stats.arr2d is None: continue
            hist = stats.histogram(1)
            starts = stats.starts(1)
            blacks[clr], whites[clr] = get_sigma_range_for_hist(starts, hist, sigma)

        black = min(blacks.values())
        white = max(whites.values())

        if self.ndarray.dtype in ['uint8', 'uint16']:
            if black == white:
                self.defaultOffsetGain()
                return
            else:
                white += 1

        self.changeBlackWhite(black, white)

    def zoomIn(self):
        self.imviewer.zoomIn()

    def zoomOut(self):
        self.imviewer.zoomOut()

    def setZoom100(self):
        self.imviewer.setZoom(1)

    def setZoom(self):
        with ActionArguments(self) as args:
            args['zoom'] = self.imviewer.zoomValue * 100

        if args.isNotSet():
            results = fedit([('Zoom value %', args['zoom'])])
            if results is None: return
            args['zoom'] = results[0]

        self.imviewer.setZoom(args['zoom'] / 100)

    def setZoomValue(self, value):
        self.imviewer.setZoom(value)

    def zoomFit(self):
        self.imviewer.zoomFit()

    def zoomFull(self):
        self.imviewer.zoomFull()

    def zoomAuto(self):
        self.imviewer.zoomAuto()

    def setColorMap(self):
        with ActionArguments(self) as args:
            args['cmap'] = 'grey'

        if args.isNotSet():
            colormapdialog = ColorMapDialog()
            colormapdialog.exec_()
            self.colormap = colormapdialog.cm_name
        else:
            self.colormap = args['cmap']

        self.refresh_offset_gain()

    def toggle_hq(self):
        self.imviewer.hqzoomout = not self.imviewer.hqzoomout
        self.show_array(None)

    def toggle_zoombind(self):
        self.imviewer.zoombind = not self.imviewer.zoombind
        
    def bindImageViewers(self):
        for src_panid, src_panel in gui.qapp.panels['image'].items():
            for tgt_panid, tgt_panel in gui.qapp.panels['image'].items():            
                if src_panid == tgt_panid: continue
                src_panel.addBindingTo('image', tgt_panid)
                
    def unbindImageViewers(self):
        for src_panid, src_panel in gui.qapp.panels['image'].items():
            for tgt_panid, tgt_panel in gui.qapp.panels['image'].items():            
                if src_panid == tgt_panid: continue
                src_panel.removeBindingTo('image', tgt_panid)                

    def setBackground(self):

        old_color = self.imviewer.palette().window().color()
        rgb = old_color.toTuple()[:3]

        with ActionArguments(self) as args:
            args['r'] = rgb[0]
            args['g'] = rgb[1]
            args['b'] = rgb[2]

        if args.isNotSet():
            color = QColorDialog.getColor(old_color)

            try:
                rgb = color.toTuple()[:3]
            except:
                rgb = (0,0,0)

        else:
            rgb = (args['r'], args['g'], args['b'])

        config['image background'] = rgb
        self.imviewer.setBackgroundColor(*config['image background'])


    def setRoiColor(self):
        
        old_color = QtGui.QColor(*config['roi color'])
        rgb = old_color.toTuple()[:3]
        
        with ActionArguments(self) as args:
            args['r'] = rgb[0]
            args['g'] = rgb[1]
            args['b'] = rgb[2]
            
        if args.isNotSet():
            color = QColorDialog.getColor(old_color)

            try:
                rgb = color.toTuple()[:3]
            except:
                rgb = (0,0,0)
                
        else:
            rgb = (args['r'], args['g'], args['b'])                
            
        config['roi color'] = list(rgb)
        self.imviewer.roi.initUI()
        
        
    def copySliceToClipboard(self):
        clipboard = self.qapp.clipboard()
        sls =self.imviewer.imgdata.selroi.getslices()
        clipboard.setText(str(sls))        
        
        
    def togglePixelLabels(self):
        v = config['image'].get('pixel_labels', False)
        config['image']['pixel_labels'] = not v

    ############################
    # Select Menu Connections

    def selectAll(self):
        selroi = self.imviewer.imgdata.selroi
        selroi.reset()
        self.imviewer.roi.clip()
        self.imviewer.roi.show()

    def selectNone(self):
        self.imviewer.imgdata.selroi.reset()
        self.imviewer.roi.clip()
        self.imviewer.roi.hide()

    def setRoi(self):
        selroi = self.imviewer.imgdata.selroi

        form = [('x start', selroi.xr.start),
                ('x stop', selroi.xr.stop),
                ('x step', selroi.xr.step),
                ('y start', selroi.yr.start),
                ('y stop', selroi.yr.stop),
                ('y step', selroi.yr.step)]

        r = fedit(form, title='ROI')
        if r is None: return

        selroi.xr.start = r[0]
        selroi.xr.stop = r[1]
        selroi.xr.step = r[2]
        selroi.yr.start = r[3]
        selroi.yr.stop = r[4]
        selroi.yr.step = r[5]

        self.imviewer.roi.clip()
        self.imviewer.roi.show()

    def jumpToDialog(self):
        selroi = self.imviewer.imgdata.selroi

        form = [('x', selroi.xr.start),
                ('y', selroi.yr.start)]

        results = fedit(form, title='Position')
        if results is None: return
        x, y = results
        self.jumpTo(x, y)

    def jumpTo(self, x, y):
        selroi = self.imviewer.imgdata.selroi

        selroi.xr.start, selroi.yr.start = x, y
        selroi.xr.stop = selroi.xr.start + 1
        selroi.xr.step = 1
        selroi.yr.stop = selroi.yr.start + 1
        selroi.yr.step = 1

        self.imviewer.roi.clip()
        self.imviewer.roi.show()
        self.imviewer.zoomToRoi()
        self.roiChanged.emit(self.panid)

    def maskValue(self):
        array = self.ndarray
        evalOptions = ['Equal', 'Smaller', 'Larger']

        if array.ndim == 2:
            form = [('Evaluate', [1] + evalOptions),
                    ('Value', 0)]
        elif array.ndim == 3:
            form = [('Evaluate', [1] + evalOptions),
                ('Red', 0),
                ('Green', 0),
                ('Blue', 0)]

        result = fedit(form, title='Mask')

        if result is None:
            self.imviewer.imgdata.set_mask(None)
            self.imviewer.refresh()
            return

        evalind, *values = result

        if evalind == 1:
            if array.ndim == 2:
                mask = (array == values[0])

            elif array.ndim == 3:
                mask0 = (array[:,:,0] == values[0])
                mask1 = (array[:,:,1] == values[1])
                mask2 = (array[:,:,2] == values[2])
                mask = mask0 & mask1 & mask2

        elif evalind == 2:
            if array.ndim == 2:
                mask = (array < values[0])

            elif array.ndim == 3:
                mask0 = (array[:,:,0] < values[0])
                mask1 = (array[:,:,1] < values[1])
                mask2 = (array[:,:,2] < values[2])
                mask = mask0 & mask1 & mask2

        elif evalind == 3:
            if array.ndim == 2:
                mask = (array > values[0])

            elif array.ndim == 3:
                mask0 = (array[:,:,0] > values[0])
                mask1 = (array[:,:,1] > values[1])
                mask2 = (array[:,:,2] > values[2])
                mask = mask0 & mask1 & mask2

        self.imviewer.imgdata.set_mask(mask)
        self.imviewer.refresh()

    ############################
    # Canvas Menu Connections

    def flipHorizontal(self):
        self.show_array(self.ndarray[:, ::-1])


    def flipVertical(self):
        self.show_array(self.ndarray[::-1, :])


    def rotate90(self):
        rotated = np.rot90(self.ndarray, 1).copy()
        self.show_array(rotated)


    def rotate180(self):
        self.show_array(self.ndarray[::-1, ::-1])


    def rotate270(self):
        rotated = np.rot90(self.ndarray, 3).copy()
        self.show_array(rotated)


    def rotateAny(self):
        with ActionArguments(self) as args:
            args['angle'] = 0.0

        if args.isNotSet():
            form = [('Angle', args['angle'])]
            results = fedit(form)
            if results is None: return
            args['angle'] = results[0]

        with gui.qapp.waitCursor(f'Rotating {args["angle"]} degree'):
            procarr = scipy.ndimage.rotate(self.ndarray, args['angle'], reshape=True)
            self.show_array(procarr)


    def crop(self):
        self.select()
        croped_array = gui.vr.copy()
        gui.img.show(croped_array)
        self.selectNone()


    def canvasResize(self):
        old_height, old_width = self.ndarray.shape[:2]

        with ActionArguments(self) as args:
            args['width'], args['height'] = old_width, old_height

        channels = self.ndarray.shape[2] if self.ndarray.ndim == 3 else 1

        if args.isNotSet():

            form = [('Width', args['width']), ('Height', args['height'])]
            results = fedit(form)
            if results is None: return
            args['width'], args['height'] = results

        new_width = args['width']
        new_height = args['height']

        if channels == 1:
            procarr = np.ndarray((new_height, new_width), dtype=self.ndarray.dtype)
        else:
            procarr = np.ndarray((new_height, new_width, channels), dtype=self.ndarray.dtype)

        #What with the alpha channel?
        procarr[:] = 0

        width = min(old_width, new_width)
        height = min(old_height, new_height)
        ofow = (old_width - width) // 2
        ofnw = (new_width - width) // 2
        ofoh = (old_height - height) // 2
        ofnh = (new_height - height) // 2
        procarr[ofnh:ofnh+height, ofnw:ofnw+width, ...] = self.ndarray[ofoh:ofoh+height, ofow:ofow+width, ...]
        self.show_array(procarr)


    def resize(self):
        source = self.ndarray
        shape = self.ndarray.shape

        form = [("width", shape[1]), ("height", shape[0]), ("order", 1)]
        results = fedit(form)
        if results is None: return
        width, height, order = results

        factorx = width / shape[1]
        factory = height / shape[0]

        if source.ndim == 2:
            scaled = scipy.ndimage.zoom(source, (factory, factorx), order=order, mode="nearest")

        elif source.ndim == 3:
            #some bug here
            scaled = scipy.ndimage.zoom(source, (factory, factorx, 1.0), order=order, mode="nearest")
            #returned array dimensions are not on the expected index

        self.show_array(scaled)


    ############################
    # Image Menu Connections

    def fillValue(self):
        """
        :param float value:
        """
        with ActionArguments(self) as args:
            args['value'] = 0.0

        if args.isNotSet():
            form = [('Value', args['value'])]
            results = fedit(form)
            if results is None: return
            args['value'] = results[0]

        procarr = self.ndarray.copy()
        procarr[:] = args['value']
        self.show_array(procarr)


    def addNoise(self):
        form = [('Standard Deviation', 1.0)]
        results = fedit(form)
        if results is None: return
        std = float(results[0])

        def run_in_console(std):
            arr = gui.vs
            shape = arr.shape
            dtype = arr.dtype            
            procarr = clip_array(arr + np.random.randn(*shape) * std + 0.5, dtype)
            gui.show(procarr)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(run_in_console, args=(std,))

    def invert(self):
        procarr =  ~self.ndarray
        self.show_array(procarr)

    def swapRGB(self):
        if not self.ndarray.ndim >= 3:
            gui.dialog.msgbox('The image has not 3 or more channels', icon='error')
            return
        procarr = self.ndarray.copy()
        procarr[:,:,0] = self.ndarray[:,:,2]
        procarr[:,:,1] = self.ndarray[:,:,1]
        procarr[:,:,2] = self.ndarray[:,:,0]
        self.show_array(procarr)


    def toMonochroom(self):
        array = self.ndarray

        if not array.ndim == 3:
            return

        dtype = array.dtype
        procarr = clip_array(array.mean(2), dtype)
        self.show_array(procarr)


    def toPhotoMonochroom(self):
        array = self.ndarray

        if not array.ndim == 3:
            return

        clip_low, clip_high = imconvert.integer_limits(array.dtype)
        mono = np.dot(array, [0.299, 0.587, 0.144])
        procarr = clip_array(mono, array.dtype)
        self.show_array(procarr)
        
    def is8bit(self):
        return self.ndarray.dtype in ['uint8', 'int8']
    
    def is16bit(self):
        return self.ndarray.dtype in ['uint16', 'int16']
        
    def to8bit(self):
        if not self.is16bit(): return
        self.show_array((self.ndarray >> 8).astype('uint8'))
        
    def to16bit(self):
        if not self.is8bit(): return
        self.show_array(self.ndarray.astype('uint16') << 8)
        
    def to_dtype(self):
        dtypes = ['uint8', 'uint16', 'double']
        scales = ['bit shift', 'clip']
        
        form = [
            ('Data Type', [1] + dtypes),
            ('Scale', [1] + scales)]
            
        results = fedit(form, title='Convert Data Type')
        if results is None: return
        dtype = dtypes[results[0]-1]
        scale = scales[results[1]-1]
        
        array = gui.vs
        if scale == 'clip' and dtype in ['uint8', 'uint16']:
            if dtype == 'uint8':
                lower, upper = 0, 255
                
            elif dtype == 'uint16':
                lower, upper = 0, 65535
                
            array = array.clip(lower, upper)
            array = array.astype(dtype)
            
        elif scale == 'bit shift' and dtype in ['uint8', 'uint16']:
            if array.dtype == 'uint8' and dtype == 'uint16':
                array = gui.vs.astype(dtype)
                array <<= 8
                
            elif array.dtype == 'uint16' and dtype == 'uint8':
                array >>= 8                
                array = gui.vs.astype(dtype)
            
        else:
            array = array.astype(dtype)
            
        gui.show(array)
        
    def swapbytes(self):
        gui.show(gui.vs.byteswap())

    def adjustLighting(self):
        """
        :param float offset:
        :param float gain:
        """
        with ActionArguments(self) as args:
            args['offset'] = -self.offset * 1.0
            args['gain'] = self.gain * 1.0

        if args.isNotSet():
            form = [('Offset', args['offset']),
                    ('Gain', args['gain'])]

            results = fedit(form, title='Adjust Lighting')
            if results is None: return
            offset, gain = results

        else:
            offset, gain = args['offset'], args['gain']

        #TO DO: use value mapping if possible
        array = self.ndarray
        procarr = clip_array(array * gain + offset, array.dtype)
        self.show_array(procarr)


    def adjustGamma(self):
        """
        :param float gamma:
        :param float upper:
        """
        with ActionArguments(self) as args:
            args['gamma'] = 1.0
            args['upper'] = 255

        if args.isNotSet():
            form = [('Gamma', args['gamma']),
                    ('Upper', args['upper'])]

            results = fedit(form, title='Adjust Gamma')
            if results is None: return
            gamma, upper = results

        else:
            gamma, upper = args['gamma'], args['upper']

        #TO DO: use value mapping if possible
        array = self.ndarray
        procarr = clip_array(np.power(array, gamma) * upper ** (1-gamma), array.dtype)
        self.show_array(procarr)


    ############################
    # Process Menu Connections

    def bayer_split_tiles(self):
        arr = self.ndarray
        blocks = []
        for y, x in [(0,0),(0,1),(1,0),(1,1)]:
            blocks.append(arr[y::2, x::2, ...])
        split = np.concatenate([
            np.concatenate([blocks[0], blocks[1]], axis=1),
            np.concatenate([blocks[2], blocks[3]], axis=1)])
        self.show_array(split)


    def colored_bayer(self):
        baypatns = ['RGGB', 'BGGR', 'GRBG', 'GBRG']
        form = [('Bayer Pattern', [1] + baypatns)]
        ind = fedit(form, title='Demosaic')[0]
        baypatn = baypatns[ind-1]

        procarr = bayer_split(self.ndarray, baypatn)
        self.show_array(procarr)


    def demosaic(self):
        baypatns = ['RGGB', 'BGGR', 'GRBG', 'GBRG']
        form = [('Bayer Pattern', [1] + baypatns)]
        ind = fedit(form, title='Demosaic')[0]
        baypatn = baypatns[ind-1]

        code = f"""\
        from gdesk.panels.imgview.demosaic import demosaicing_CFA_Bayer_bilinear
        procarr = demosaicing_CFA_Bayer_bilinear(gui.vs, '{baypatn}')
        gui.show(procarr)"""

        panel = gui.qapp.panels.selected('console')
        panel.exec_cmd(code)


    def makeBlueprint(self):
        with gui.qapp.waitCursor('making blueprint'):
            arr = self.ndarray

            if arr.ndim == 3:
                dtype = arr.dtype
                arr = arr.mean(2).astype(dtype)

            blueprint = make_thumbnail(arr)
            gui.img.new()
            gui.img.show(blueprint)


    def externalProcessDemo(self):
        panel = gui.qapp.panels.select_or_new('console', None, 'child')
        panel.task.wait_process_ready()

        from .proxy import ImageGuiProxy

        def stage1_done(mode, error_code, result):
            gui.msgbox('Mirroring done')
            panel.task.call_func(ImageGuiProxy.high_pass_current_image, callback=stage2_done)

        def stage2_done(mode, error_code, result):
            gui.msgbox('Highpass filter done')

        panel.task.call_func(ImageGuiProxy.mirror_x, callback=stage1_done)


    def measureDistance(self):
        panel = gui.qapp.panels.selected('console')
        #panel.task.wait_process_ready()

        from .proxy import ImageGuiProxy

        def stage1_done(mode, error_code, result):
            pass

        panel.task.call_func(ImageGuiProxy.get_distance, callback=stage1_done)

    ############################
    # Analyse Menu Connections

    def horizontalSpectrogram(self):
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(spectr_hori, args=(gui.vs,))

    def verticalSpectrogram(self):
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(spectr_vert, args=(gui.vs,))

    #############################

    def show_array(self, array, zoomFitHist=False, log=True):
        self.refresh_offset_gain(array, log=log)
        self.contentChanged.emit(self.panid, zoomFitHist)

    def select(self):
        was_selected = super().select()
        if not was_selected:
            self.gainChanged.emit(self.panid, False)
            self.contentChanged.emit(self.panid, False)
        return was_selected

    def refresh_offset_gain(self, array=None, zoomFitHist=False, log=True):
        self.imviewer.imgdata.show_array(array, self.offset, self.white, self.colormap, self.gamma, log)
        self.statuspanel.setOffsetGainInfo(self.offset, self.gain, self.white, self.gamma)
        self.gainChanged.emit(self.panid, zoomFitHist)
        self.imviewer.refresh()

    @property
    def ndarray(self):
        return self.imviewer.imgdata.statarr    
    
    @property    
    def roi_slices(self):            
        return self.imviewer.imgdata.selroi.getslices()
        
    @property
    def srcarray(self):
        return self.imviewer.imgdata.array


class ImageViewer(ImageViewerBase):

    #contentChanged = Signal(int)
    #gainChanged = Signal(int)
    panelShortName = 'basic'
    userVisible = True

    def __init__(self, *args, **kwargs):
        #super().__init__(parent, panid, 'image')
        super().__init__(*args, **kwargs)

        self.imviewer = ImageViewerWidget(self)
        self.imviewer.roi.roiChanged.connect(self.passRoiChanged)
        self.imviewer.roi.get_context_menu = self.get_select_menu

        self.setCentralWidget(self.imviewer)
        self.imviewer.pickerPositionChanged.connect(self.set_info_xy_val)
        self.imviewer.zoomChanged.connect(self.statuspanel.set_zoom)
        self.imviewer.zoomPanChanged.connect(self.emitVisibleRegionChanged)


    def passRoiChanged(self):
        self.roiChanged.emit(self.panid)


    def emitVisibleRegionChanged(self):
        if self.imviewer.zoombind:
            self.visibleRegionChanged.emit(*self.imviewer.visibleRegion(normalized=True, clip_square=True), False, False, self.imviewer.zoomValue)
        else:
            self.visibleRegionChanged.emit(*self.imviewer.visibleRegion(normalized=True, clip_square=True), False, False, 0.0)


class ImageProfileWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent=parent)

        self.imviewer = ImageViewerWidget(self)

        self.profBtn = QtWidgets.QPushButton(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'diagramm.png')), None, self)
        self.profBtn.setFixedHeight(20)
        self.profBtn.setFixedWidth(20)
        self.profBtn.clicked.connect(self.toggleProfileVisible)
        self.rowPanel = ProfilerPanel(self, 'x', self.imviewer)
        self.colPanel = ProfilerPanel(self, 'y', self.imviewer)

        self.gridsplit = GridSplitter(None)


        self.imviewer.zoomPanChanged.connect(self.colPanel.zoomToImage)
        self.imviewer.zoomPanChanged.connect(self.rowPanel.zoomToImage)

        self.gridsplit.addWidget(self.rowPanel, 0, 1)
        self.gridsplit.addWidget(self.colPanel, 1, 0)
        self.gridsplit.addWidget(self.imviewer, 1, 1)

        self.cornerLayout = QtWidgets.QGridLayout()
        self.cornerLayout.addWidget(self.profBtn, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        self.gridsplit.addLayout(self.cornerLayout, 0, 0)

        self.setLayout(self.gridsplit)

        self.profilesVisible = False


    def toggleProfileVisible(self):
        self.profilesVisible = not self.profilesVisible


    def showOnlyRuler(self):
        self.rowPanel.showOnlyRuler()
        self.colPanel.showOnlyRuler()
        self._profilesVisible = False

        gui.qapp.processEvents()
        self.refresh_profile_views()


    def showProfiles(self):
        self.rowPanel.setMinimumHeight(20)
        self.rowPanel.setMaximumHeight(500)
        self.colPanel.setMinimumWidth(20)
        self.colPanel.setMaximumWidth(500)

        strow = self.gridsplit.getRowStretches()
        stcol = self.gridsplit.getColumnStretches()
        rowspan = strow[0]+ strow[1]
        colspan = stcol[0] + stcol[1]
        target = rowspan // 5
        self.gridsplit.setRowStretches((target,rowspan-target))
        self.gridsplit.setColumnStretches((target,colspan-target))
        self.colPanel.showAll()
        self.rowPanel.showAll()

        self._profilesVisible = True
        self.drawMeanProfile()

        gui.qapp.processEvents()
        self.refresh_profile_views()


    def drawMeanProfile(self):       
        arr = self.ndarray

        if arr.ndim > 2:
            arr = arr.mean(2)

        if self.rowPanel.view.fullActive.isChecked():
            rowProfile = arr.mean(0)        
            self.rowPanel.drawMeanProfile(np.arange(len(rowProfile)), rowProfile)
        
        if self.colPanel.view.fullActive.isChecked():
            colProfile = arr.mean(1)
            self.colPanel.drawMeanProfile(np.arange(len(colProfile)), colProfile)

        self.refresh_profile_views()
        
        
    def drawRoiProfile(self):       
        rowChecked = self.rowPanel.view.roiActive.isChecked()
        colChecked = self.colPanel.view.roiActive.isChecked()

        if arr.ndim > 2 and (rowChecked or colChecked):
            arr = arr.mean(2)
            
        arr = self.ndarray
        slices = self.roi_slices        

        if rowChecked:
            rowProfile = arr[slices].mean(0)            
            self.rowPanel.drawRoiProfile(np.arange(*slices[1].indices(arr.shape[1])), rowProfile)
            
        if colChecked:
            colProfile = arr[slices].mean(1)
            self.colPanel.drawRoiProfile(np.arange(*slices[0].indices(arr.shape[0])), colProfile)

        if rowChecked or colChecked:
            self.refresh_profile_views()        


    def set_profiles_visible(self, value):
        if value:
            self.showProfiles()
        else:
            self.showOnlyRuler()

    profilesVisible = property(lambda self: self._profilesVisible, set_profiles_visible)

    def refresh_profile_views(self):
        self.colPanel.zoomToImage()
        self.rowPanel.zoomToImage()

        if self.colPanel.view.auto_zoom:
            self.colPanel.zoomFit()
        self.colPanel.view.refresh()
        if self.rowPanel.view.auto_zoom:
            self.rowPanel.zoomFit()
        self.rowPanel.view.refresh()
        
    @property
    def ndarray(self):    
        return self.imviewer.imgdata.statarr
        
        
    @property
    def roi_slices(self):
        return self.imviewer.imgdata.selroi.getslices()


class ImageProfilePanel(ImageViewerBase):
    panelShortName = 'image-profile'
    userVisible = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.imgprof = ImageProfileWidget(self)
        self.setCentralWidget(self.imgprof)

        self.imviewer.pickerPositionChanged.connect(self.set_info_xy_val)
        self.imviewer.zoomChanged.connect(self.statuspanel.set_zoom)
        self.imviewer.zoomPanChanged.connect(self.emitVisibleRegionChanged)
        self.imviewer.roi.roiChanged.connect(self.passRoiChanged)
        self.imviewer.roi.get_context_menu = self.get_select_menu

        self.addMenuItem(self.viewMenu, 'Show/Hide Profiles'    , self.showHideProfiles,
            checkcall=lambda: self.imgprof.profilesVisible,
            statusTip="Show or Hide the image column and row profiles")
            
        if not kwargs.get('empty', True): self.openTestImage()
        
        
    def postLayoutInit(self):
        self.openTestImage()
        
            
    def openTestImage(self):        
        self.openImage(respath / 'images' / 'gamma_test_22.png', zoom=1)


    def emitVisibleRegionChanged(self):
        if self.imviewer.zoombind:
            self.visibleRegionChanged.emit(*self.imviewer.visibleRegion(normalized=True, clip_square=True), False, False, self.imviewer.zoomValue)
        else:
            self.visibleRegionChanged.emit(*self.imviewer.visibleRegion(normalized=True, clip_square=True), False, False, 0.0)


    def changeVisibleRegion(self, x, y, w, h, zoomSnap, emit, zoomValue):
        self.imgprof.imviewer.zoomNormalized(x, y, w, h, zoomSnap, emit, zoomValue)
        self.imgprof.colPanel.zoomToImage()
        self.imgprof.rowPanel.zoomToImage()
        self.imviewer.roi.recalcGeometry()


    def passRoiChanged(self):
        self.roiChanged.emit(self.panid)
        self.imgprof.drawRoiProfile()


    def show_array(self, array, zoomFitHist=False, log=True):
        super().show_array(array, zoomFitHist, log=log)
        if self.imgprof.profilesVisible:
            self.imgprof.drawMeanProfile()
            self.imgprof.drawRoiProfile()
        else:
            self.imgprof.refresh_profile_views()


    @property
    def imviewer(self):
        return self.imgprof.imviewer


    def showHideProfiles(self):
        self.imgprof.profilesVisible = not self.imgprof.profilesVisible

