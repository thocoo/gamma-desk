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
from .imgdata import get_next_color_tuple
from .dialogs import RawImportDialog
from .statspanel import StatisticsPanel, TitleToolBar


here = Path(__file__).parent.absolute()
respath = Path(config['respath'])
#sck = config['shortcuts']

channels = ['R', 'G', 'B', 'A']

from .view_widgets import StatusPanel     
    

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
            
            
def wrap(func, *args, **kwargs):

    def wrapper():
        func(*args, **kwargs)
        
    return wrapper
    

class selectNamedMask():
    def __init__(self, imgpanel, roiName):
        self.imgpanel = imgpanel
        self.roiName = roiName
        
    def __call__(self):
        self.imgpanel.imgprof.selectMask(self.roiName)        
        self.imgpanel.imgprof.showSelection(self.roiName)               
    

class CustomMaskMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__('Custom Mask', parent)
        self.imgpanel = self.parent()
        self.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'selection_pane.png')))

    def showEvent(self, event):
        self.initactions()

    def initactions(self):
        self.clear()
        self.actions = []
        
        try:
            roiNames = self.imgpanel.imviewer.imgdata.customMaskNames()
        except:
            roiNames = []
                
        for roiName in roiNames:
            action = QAction(roiName, self)
            action.triggered.connect(selectNamedMask(self.imgpanel, roiName))
            self.addAction(action)
            self.actions.append(action)

from .imgpaint import ImageViewerWidget


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
            statusTip="Set the color map for monochrome images",
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

        ####################
        ### Select
        
        self.addMenuItem(self.selectMenu, 'Reselect', self.reselect,
            statusTip="Select or reselect a region of interest",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'select_restangular.png')))
            
        self.addMenuItem(self.selectMenu, 'Deselect', self.selectNone,
            statusTip="Deselect, select nothing")
            
        self.addMenuItem(self.selectMenu, 'Select Dialog...', self.setRoi,
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'layer_select.png')),
            statusTip="Select with input numbers dialog")
            
        self.addMenuItem(self.selectMenu, 'Select 1 Pixel...'   , self.jumpToDialog,
            statusTip="Select 1 pixel and zoom to it",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'canvas.png')))
            
        self.addMenuItem(self.selectMenu, 'Add Mask Statistics...', self.addMaskStatistics,
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'create_from_selection.png')))
            
        self.addMenuItem(self.selectMenu, 'Remove Mask Statistics...', self.removeMaskStatistics)            
                    
            
        dataSplitMenu = QMenu('Default Masks')
        dataSplitMenu.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'select_by_color.png')))        
        self.addMenuItem(dataSplitMenu, 'mono', lambda: self.setStatMasks('mono'), icon=str(respath / 'icons' / 'px16' / 'color_gradient.png'))
        self.addMenuItem(dataSplitMenu, 'rgb', lambda: self.setStatMasks('rgb'), icon=str(respath / 'icons' / 'px16' / 'color.png'))            
        self.addMenuItem(dataSplitMenu, 'bg', lambda: self.setStatMasks('bg'), icon=str(respath / 'icons' / 'px16' / 'cfa_bg.png'))
        self.addMenuItem(dataSplitMenu, 'gb', lambda: self.setStatMasks('gb'), icon=str(respath / 'icons' / 'px16' / 'cfa_gb.png'))
        self.addMenuItem(dataSplitMenu, 'rg', lambda: self.setStatMasks('rg'), icon=str(respath / 'icons' / 'px16' / 'cfa_rg.png'))
        self.addMenuItem(dataSplitMenu, 'gr', lambda: self.setStatMasks('gr'), icon=str(respath / 'icons' / 'px16' / 'cfa_gr.png'))
                
        
        self.selectMenu.addMenu(dataSplitMenu)                    
        
        self.selectMenu.addMenu(CustomMaskMenu(self))
            
        self.selectMenu.addSeparator()
        
        self.searchForRoiSlots = []
        
        for i in range(4):
            action = QAction(f"Custom Mask {i}", self, triggered=wrap(self.selectNamedMask, i))
            action.setVisible(False)
            self.searchForRoiSlots.append(action)
            self.selectMenu.addAction(action)
                                                      

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
        self.addMenuItem(self.imageMenu, 'to Monochrome', self.toMonochrome,
            statusTip="Convert an RGB image to monochrome grey",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'convert_color_to_gray.png')))
        self.addMenuItem(self.imageMenu, 'to Photometric Monochrome', self.toPhotoMonochrome,
            statusTip="Convert an RGB image to photometric monochrome grey",
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
        return self.menuBar().children()[4]
        

    def exec_select_menu(self, x, y):
        #The select menu should be index 4 from the menuBar children
        roi_names = self.imviewer.imgdata.find_chanstat_for_pixel(x, y)
        self.refresh_roi_slots(roi_names)
        selectMenu = self.get_select_menu()
        selectMenu.exec_(QtGui.QCursor.pos())
        self.refresh_roi_slots([])
        
        
    def refresh_roi_slots(self, roi_names=None):
        if roi_names is None: roi_names = []
        
        for roi_name, searchForRoiSlot in zip_longest(roi_names, self.searchForRoiSlots):
            if roi_name is None:
                searchForRoiSlot.setVisible(False)
                
            elif searchForRoiSlot is None:
                pass
            
            else:
                searchForRoiSlot.setVisible(True)
                searchForRoiSlot.setText(roi_name)        
        

    def createStatusBar(self):
        self.statuspanel = StatusPanel(self)
        self.statusBar().addWidget(self.statuspanel)
        

    def set_info_xy_val(self, x, y):
        try:
            val = self.imviewer.imgdata.statarr[y, x]

        except:
            val = None
                    
        self.statuspanel.set_xy_val(x, y, val)
        
        
    def selectNamedMask(self, i):
        maskName = self.searchForRoiSlots[i].text()
        self.imgprof.selectMask(maskName)
        self.imgprof.showSelection(maskName)
    

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
            #self.long_title = str(filepath)
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

        blacks = dict()
        whites = dict()
        
        skip_dim = not all(stats.dim for stats in self.imviewer.imgdata.chanstats.values() if (stats.is_valid() and stats.active))
        
        for clr, stats in  self.imviewer.imgdata.chanstats.items():            
            if not (stats.is_valid() and stats.active): continue
            if skip_dim and stats.dim: continue
            
            hist = stats.histogram(1)
            starts = stats.starts(1)
            blacks[clr], whites[clr] = get_sigma_range_for_hist(starts, hist, sigma)

        black = min(blacks.values())
        white = max(whites.values())

        if self.ndarray.dtype in ['uint8', 'uint16']:
            if black == white:
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
        rgb = old_color.getRgb()[:3]
        with ActionArguments(self) as args:
            args['r'] = rgb[0]
            args['g'] = rgb[1]
            args['b'] = rgb[2]

        if args.isNotSet():
            color = QColorDialog.getColor(old_color)
            try:
                rgb = color.getRgb()[:3]
            except:
                rgb = (0,0,0)

        else:
            rgb = (args['r'], args['g'], args['b'])

        config['image background'] = rgb
        self.imviewer.setBackgroundColor(*config['image background'])


    def setRoiColor(self):
        
        old_color = QtGui.QColor(*config['roi color'])
        rgb = old_color.getRgb()[:3]
        with ActionArguments(self) as args:
            args['r'] = rgb[0]
            args['g'] = rgb[1]
            args['b'] = rgb[2]
            
        if args.isNotSet():
            color = QColorDialog.getColor(old_color)
            try:
                rgb = color.getRgb()[:3]
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

    def reselect(self):
        self.imviewer.roi.showRoi()
        

    def selectNone(self):
        self.imviewer.roi.hideRoi()
        

    def setRoi(self):
        selroi = self.imviewer.imgdata.selroi

        form = [('x start', selroi.xr.start),
                ('x stop', selroi.xr.stop),
                ('x step', selroi.xr.step),
                ('y start', selroi.yr.start),
                ('y stop', selroi.yr.stop),
                ('y step', selroi.yr.step)]

        r = fedit(form, title='Select')
        if r is None: return

        selroi.xr.start = r[0]
        selroi.xr.stop = r[1]
        selroi.xr.step = r[2]
        selroi.yr.start = r[3]
        selroi.yr.stop = r[4]
        selroi.yr.step = r[5]

        self.imviewer.roi.clip()
        self.imviewer.roi.show()
        

    def addMaskStatistics(self):
        selroi = self.imviewer.imgdata.selroi
        
        color = get_next_color_tuple()
        
        color_str = '#' + ''.join(f'{v:02X}' for v in color[:3])

        form = [('Name',  'custom'),
                ('Color',  color_str),
                ('x start', selroi.xr.start),
                ('x stop', selroi.xr.stop),
                ('x step', selroi.xr.step),
                ('y start', selroi.yr.start),
                ('y stop', selroi.yr.stop),
                ('y step', selroi.yr.step)]

        r = fedit(form, title='Add Mask Statistics')
        if r is None: return

        name = r[0]                
        color = QtGui.QColor(r[1])
        h_slice = slice(r[2], r[3], r[4])
        v_slice = slice(r[5], r[6], r[7])

        self.imviewer.imgdata.addMaskStatistics(name, (v_slice, h_slice), color)     
        self.refresh()

        
    def removeMaskStatistics(self):
        masks = self.imviewer.imgdata.customMaskNames()                
        
        if len(masks) < 1: return
        
        form = [('Mask', [1] + masks)]
        result = fedit(form, title='Removing Mask')
        mask = masks[result[0] - 1]
        self.imviewer.imgdata.chanstats.pop(mask)
        

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
        
        
    def setStatMasks(self, mode):
        self.imviewer.imgdata.init_channel_statistics(mode)
        self.refresh()
        

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


    def toMonochrome(self):
        array = self.ndarray

        if not array.ndim == 3:
            return

        dtype = array.dtype
        procarr = clip_array(array.mean(2), dtype)
        self.show_array(procarr)


    def toPhotoMonochrome(self):
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

    def show_array(self, array, zoomFitHist=False, log=True, skip_init=False):
        self.refresh_offset_gain(array, log=log, skip_init=skip_init)                   
        self.contentChanged.emit(self.panid, zoomFitHist)

    def select(self):
        was_selected = super().select()
        if not was_selected:
            self.gainChanged.emit(self.panid, False)
            self.contentChanged.emit(self.panid, False)
        return was_selected

    def refresh_offset_gain(self, array=None, zoomFitHist=False, log=True, skip_init=False):
        self.imviewer.imgdata.show_array(array, self.offset, self.white, self.colormap, self.gamma, log, skip_init)
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

    panelShortName = 'basic'
    userVisible = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.imviewer = ImageViewerWidget(self)
        self.imviewer.roi.roiChanged.connect(self.passRoiChanged)
        self.imviewer.roi.get_context_menu = self.get_select_menu

        self.setCentralWidget(self.imviewer)
        
        self.imviewer.pickerPositionChanged.connect(self.set_info_xy_val)
        self.imviewer.zoomChanged.connect(self.statuspanel.set_zoom)
        self.imviewer.zoomPanChanged.connect(self.emitVisibleRegionChanged)
        self.imviewer.contextMenuRequest.connect(self.exec_select_menu)


    def passRoiChanged(self):
        self.roiChanged.emit(self.panid)


    def emitVisibleRegionChanged(self):
        if self.imviewer.zoombind:
            self.visibleRegionChanged.emit(*self.imviewer.visibleRegion(normalized=True, clip_square=True), False, False, self.imviewer.zoomValue)
        else:
            self.visibleRegionChanged.emit(*self.imviewer.visibleRegion(normalized=True, clip_square=True), False, False, 0.0)
            
            
class RoiToolBar(QtWidgets.QToolBar):
    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()     
        
    def toggleProfileVisible(self):
        self.parent().parent().toggleProfileVisible()        
        
    def initUi(self):
        self.addAction(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'diagramm.png')), 'Refresh', self.toggleProfileVisible)
        fontHeight = self.fontMetrics().height()
        self.setIconSize(QtCore.QSize(int(fontHeight * 3 / 2), int(fontHeight * 3 / 2)))


class ImageProfileWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent=parent)

        self.imviewer = ImageViewerWidget(self)

        self.profBtn1 = QtWidgets.QPushButton(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'diagramm.png')), None, self)
        self.profBtn1.setToolTip('Show/Hide row and column profiles')
        self.profBtn1.setFixedHeight(20)
        self.profBtn1.setFixedWidth(20)
        self.profBtn1.clicked.connect(self.toggleProfileVisible)     

        # self.profBtn2 = QtWidgets.QPushButton(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'diagramm.png')), None, self)
        # self.profBtn2.setToolTip('Show/Hide row and column profiles')
        # self.profBtn2.setFixedHeight(20)
        # self.profBtn2.setFixedWidth(20)
        # self.profBtn2.clicked.connect(self.toggleProfileVisible)          
        
        self.corner = QtWidgets.QMainWindow()        
        self.corner.setCentralWidget(self.profBtn1)        
        
        self.statsPanel = StatisticsPanel()
        self.statsPanel.maskSelected.connect(self.selectMask)
        self.statsPanel.activesChanged.connect(self.refresh)        
        
        self.statsPanel.setSelection.connect(self.setSelection)        
        self.statsPanel.showSelection.connect(self.showSelection)        
        self.statsPanel.hideSelection.connect(self.hideSelection)        
        
        self.statsToolbar = TitleToolBar()
        self.statsToolbar.toggleProfile.connect(self.toggleProfileVisible)
        self.statsToolbar.showHideInactives.connect(self.statsPanel.toggleShowInactives)        
        
        self.statsDock = QtWidgets.QDockWidget("Statistics", self.corner)
        #self.toolbar = RoiToolBar(self.corner)
        self.statsDock.setTitleBarWidget(self.statsToolbar)
        self.statsDock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.statsDock.setFeatures(QtWidgets.QDockWidget.DockWidgetFloatable)
        self.statsDock.setWidget(self.statsPanel)        
        
        self.statsToolbar.toggleDock.connect(self.toggleStatsDockFloating)
        self.statsToolbar.selectMasks.connect(self.selectMasks)
        self.statsToolbar.selectRoi.connect(self.selectRoi)
        
        
        self.corner.addDockWidget(Qt.BottomDockWidgetArea, self.statsDock)
        
        #self.corner.hide()
        self.rowPanel = ProfilerPanel(self, 'x', self.imviewer)
        self.colPanel = ProfilerPanel(self, 'y', self.imviewer)

        self.gridsplit = GridSplitter(None)

        self.imviewer.zoomPanChanged.connect(self.colPanel.zoomToImage)
        self.imviewer.zoomPanChanged.connect(self.rowPanel.zoomToImage)
        
        # self.corner.toolbar = RoiToolBar(self.corner)
        # self.corner.toolbar.hide()
        # self.corner.addToolBar(self.corner.toolbar)        

        self.gridsplit.addWidget(self.corner, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        self.gridsplit.addWidget(self.rowPanel, 0, 1)
        self.gridsplit.addWidget(self.colPanel, 1, 0)
        self.gridsplit.addWidget(self.imviewer, 1, 1)

        self.setLayout(self.gridsplit)

        self.profilesVisible = False


    def toggleProfileVisible(self):
        self.profilesVisible = not self.profilesVisible
        
    def toggleStatsDockFloating(self):    
        if self.statsDock.isFloating():
            self.statsDock.setFloating(False)
            
            if self.profBtn1.isVisible():
                # Docking while profiles are not visible
                self.statsDock.hide()
        else:
            self.statsDock.setFloating(True)
            
            
    def selectMasks(self, masks):
        self.imviewer.imgdata.init_channel_statistics(masks)
        self.refresh()
        
        
    def selectRoi(self, option):
    
        if option in ['show roi only']:
            self.imviewer.roi.showRoi()
    
        self.imviewer.imgdata.selectRoiOption(option)
        self.refresh()        
        

    def showOnlyRuler(self):
    
        if not self.statsDock.isFloating():
            self.statsDock.hide()
            
        self.corner.setFixedWidth(20)
        self.corner.setFixedHeight(20)
        self.rowPanel.showOnlyRuler()
        self.colPanel.showOnlyRuler()
        self._profilesVisible = False

        gui.qapp.processEvents()
        self.refresh_profile_views()


    def showProfiles(self):

        self.statsDock.show()
        #self.corner.setMinimumHeight(20)
        self.corner.setMaximumHeight(500)
        #self.corner.setMinimumWidth(20)
        self.corner.setMaximumWidth(500)        
        
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
        self.drawMaskProfiles()

        gui.qapp.processEvents()
        self.refresh_profile_views()
        
        
    def drawMaskProfiles(self):         
        self.rowPanel.drawMaskProfiles()
        self.colPanel.drawMaskProfiles()                           
        
    
    def selectMask(self, mask):
        if mask == '':
            masks = []
        else:
            masks = mask.split(',')            
            
        self.imviewer.imgdata.selectChannelStat(masks)
        self.rowPanel.selectProfiles(masks)
        self.colPanel.selectProfiles(masks)
        
        
    def setSelection(self, mask):
        roi = self.imviewer.roi
        
        if not (mask == ''):
            chanstats = self.imviewer.imgdata.chanstats[mask]
        
            selroi = self.imviewer.imgdata.selroi  
            selroi.xr.setfromslice(chanstats.slices[1])
            selroi.yr.setfromslice(chanstats.slices[0])                                    
            roi.clip()
            roi.show()
            roi.roiChanged.emit()  
            
        
    def showSelection(self, mask): 
        if mask == '': return
        
        chanstats = self.imviewer.imgdata.chanstats[mask]
        
        if mask.startswith('roi.'):
            roi = self.imviewer.roi
            
        elif mask in self.imviewer.custom_rois:                        
            roi = self.imviewer.custom_rois[mask]
            
        else:
            self.imviewer.set_custom_selection(mask, color=chanstats.plot_color)
            roi = self.imviewer.custom_rois[mask]
                        
        roi.selroi.xr.setfromslice(chanstats.slices[1])
        roi.selroi.yr.setfromslice(chanstats.slices[0])        
        roi.clip()
        roi.show()
        roi.roiChanged.emit()    
        

    def hideSelection(self, mask): 
        if mask == '': return
        
        chanstats = self.imviewer.imgdata.chanstats[mask]
        
        if mask.startswith('roi.'):
            roi = self.imviewer.roi
            
        elif mask in self.imviewer.custom_rois:                        
            roi = self.imviewer.custom_rois[mask]
            
        else:
            pass
                        
        roi.hide()          
        
        
    def drawRoiProfile(self):                     
        slices = self.roi_slices        
        self.rowPanel.drawMaskProfiles(roi_only=True)
        self.colPanel.drawMaskProfiles(roi_only=True)            
        

    def set_profiles_visible(self, visible):
        if visible:
            self.profBtn1.hide()
            self.showProfiles()
            self.statsPanel.updateStatistics()
            
        else:
            self.profBtn1.show()
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
        
        
    def refresh(self):
        parent = self.parent()        
        parent.contentChanged.emit(parent.panid, False)
        parent.refresh_profiles_and_stats()
               
        
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
        self.imviewer.roi.roiRemoved.connect(self.removeRoiProfile)
        
        self.imviewer.roi.get_context_menu = self.get_select_menu
        self.imviewer.contextMenuRequest.connect(self.exec_select_menu)

        self.addMenuItem(self.viewMenu, 'Show/Hide Profiles'    , self.showHideProfiles,
            checkcall=lambda: self.imgprof.profilesVisible,
            statusTip="Show or Hide the image column and row profiles")
            
        if not kwargs.get('empty', True): self.openTestImage()
        
        
    def addBindingTo(self, category, panid):            
        targetPanel = super().addBindingTo(category, panid)    
        if targetPanel is None: return None        
        
        if targetPanel.category == 'levels':
            self.imgprof.statsPanel.maskSelected.connect(targetPanel.selectMasks)

        return targetPanel                
        
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
        self.imgprof.statsPanel.updateStatistics()
        self.imgprof.drawRoiProfile()
        self.imgprof.refresh_profile_views()
        
        
    def removeRoiProfile(self):
        self.imgprof.imviewer.imgdata.disable_roi_statistics()
        self.imgprof.drawMaskProfiles()
        self.imgprof.refresh_profile_views()
        self.imgprof.statsPanel.updateStatistics()  
        self.roiChanged.emit(self.panid)
        
    
    def refresh_profiles_and_stats(self):  
    
        if self.imgprof.statsPanel.isVisible():        
            self.imgprof.statsPanel.updateStatistics()    
        
        if self.imgprof.profilesVisible:
            self.imgprof.drawMaskProfiles()
            self.imgprof.refresh_profile_views()  
            

    def show_array(self, array=None, zoomFitHist=False, log=True, skip_init=False):
        super().show_array(array, zoomFitHist, log=log, skip_init=skip_init)        
        self.refresh_profiles_and_stats()
        

    @property
    def imviewer(self):
        return self.imgprof.imviewer


    def showHideProfiles(self):
        self.imgprof.profilesVisible = not self.imgprof.profilesVisible

