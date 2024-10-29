import os
import time
import collections
from pathlib import Path
import types
from collections.abc import Iterable
import queue
from itertools import zip_longest
import logging

import numpy as np

logger = logging.getLogger(__name__)


from ... import config, gui

from qtpy import QtCore, QtGui, QtWidgets, API_NAME
from qtpy.QtCore import Qt, Signal, QUrl
from qtpy.QtGui import QFont, QTextCursor, QPainter, QPixmap, QCursor, QPalette, QColor, QKeySequence
from qtpy.QtWidgets import QAction, QVBoxLayout, QWidget

from ...panels import thisPanel

from .imgdata import ImageData
from .roi import SelRoiWidget


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
channels = ['R', 'G', 'B', 'A']

def getEventPos(event):
    if API_NAME in ['PySide6']:
        pos = event.position()
    else:
        pos = event.pos()        
    return pos


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
        
        self.sel_pix_x = 0
        self.sel_pix_y = 0

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
            #menu = self.parent().parent().get_select_menu()
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
            
        if (event.button() == Qt.RightButton):
            if self.roi.createState:
                self.roi.release_creation()
                #self.setCursor(self.pickCursor)
                
            else:
                x, y = self.getImageCoordOfMouseEvent(event)
                self.parent().parent().exec_select_menu(x, y)
                
                
        self.setCursor(self.pickCursor)

    def refresh(self):
        self._scaledImage = None
        self.repaint()
        
        if self.roi.isVisible():
            self.imgdata.update_roi_statistics()        

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
