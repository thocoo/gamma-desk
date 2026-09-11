import os
import collections
from pathlib import Path
from itertools import zip_longest
import logging
import struct

import numpy as np

logger = logging.getLogger(__name__)

try:
    import scipy
    import scipy.ndimage
    has_scipy = True

except:
    has_scipy = False
    
try:
    import cv2
    has_cv2 = True

except:
    has_cv2 = False    

from ... import config, gui

from qtpy import QtCore, QtGui, QtWidgets, API_NAME
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QFont, QPainter, QCursor, QColor
from qtpy.QtWidgets import (QApplication, QAction, QMainWindow, QWidget, QMenu, QColorDialog)

from ...panels import BasePanel, CheckMenu
from ...dialogs.formlayout import fedit
from ...dialogs.colormap import ColorMapDialog
from ...widgets.grid import GridSplitter
from ...utils import imconvert
from ...gcore.utils import ActionArguments
from ...external import client

from .profile import ProfilerPanel
from .quantiles import get_sigma_range_for_hist
from .spectrogram import spectr_hori, spectr_vert
from .corner import CornerWidget
from .regoi import RoiConfigDialog

from .fileio import import_raw_image, open_image, save_image_dialog, open_image_dialog, open_image_and_show
from .view_widgets import StatusPanel

from .canvas import CanvasMenu
from .imgedit import ImageEditMenu
from .imgprocess import ProcessMenu
from .operation import OperationMenu

if has_cv2:
    from .opencv import OpenCvMenu

here = Path(__file__).parent.absolute()
respath = Path(config['respath'])
channels = ['R', 'G', 'B', 'A']
    

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
        self.imgpanel.imgprof.setSelection(self.roiName, modify=True)               
    

class CustomMaskMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__('Select Roi', parent)
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
    roiConfigChanged = Signal()

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
        
        self.editMenu = CheckMenu("&Edit", self.menuBar())
        self.menuBar().addMenu(self.editMenu)
        self.viewMenu = CheckMenu("&View", self.menuBar())
        self.menuBar().addMenu(self.viewMenu)

        self.selectMenu = CheckMenu("&Select", self.menuBar())
        
        self.canvasMenu = CanvasMenu("&Canvas", self.menuBar(), self)
        self.imageMenu = ImageEditMenu("&Image", self.menuBar(), self)
        
        self.processMenu = ProcessMenu("&Process", self.menuBar(), self)
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

        self.addMenuItem(self.editMenu, 'Copy Scaled Selection', self.placeViewerOnClipboard,
            icon = str(respath / 'icons' / 'px16' /'resize_picture.png'))
            
        self.addMenuItem(self.editMenu, 'Copy 100% Zoom', self.placeQimgOnClipboard,
            statusTip="Place the 8bit image on clipboard, offset and gain applied",
            icon = str(respath / 'icons' / 'px16' / 'two_pictures.png'))            
            
        self.addMenuItem(self.editMenu, 'Paste', self.showFromClipboard,
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
        self.addMenuItem(zoomMenu, 'Zoom 800%', lambda: self.imviewer.setZoom(8),
            statusTip="Zoom to 800%")
        self.addMenuItem(zoomMenu, 'Zoom 12500%', lambda: self.imviewer.setZoom(125),
            statusTip="Zoom to 12500%")                        
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
            
        self.defaultGainMenu = QMenu('Set Default Gain')
        self.viewMenu.addMenu(self.defaultGainMenu)
        self.addMenuItem(self.defaultGainMenu, 'Set Current as Default', self.setCurrentOffsetGainAsDefault,
            statusTip="Set the current offset, gain and gamma as default")            
        self.addMenuItem(self.defaultGainMenu, 'Increase Default Gain', lambda: self.modifyDefaultGain(1))            
        self.addMenuItem(self.defaultGainMenu, 'Decrease Default Gain', lambda: self.modifyDefaultGain(-1))            
            
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
        self.bindMenu.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'image_link.png')))
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
        
        self.addMenuItem(self.viewMenu, 'Mask Appearance...'    , self.setMaskApperance,
            statusTip="Set the mask appearance...",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'mask.png')))

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
        
        self.selectMenu.addSeparator()
            
        self.addMenuItem(self.selectMenu, 'Add Roi Statistics...', self.addMaskStatistics,
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'create_from_selection.png')))
            
        self.addMenuItem(self.selectMenu, 'Remove Roi Statistics...', self.removeMaskStatistics)            
                    
        self.addMenuItem(self.selectMenu, "Configure Roi's...", self.configureRois,
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'layers_map.png')))
                    
        dataSplitMenu = QMenu("Roi Presets")
        dataSplitMenu.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'select_by_color.png')))        
        self.addMenuItem(dataSplitMenu, 'mono', lambda: self.setStatMasks('mono'), icon=str(respath / 'icons' / 'px16' / 'color_gradient.png'))
        self.addMenuItem(dataSplitMenu, 'rgb', lambda: self.setStatMasks('rgb'), icon=str(respath / 'icons' / 'px16' / 'color.png'))            
        self.addMenuItem(dataSplitMenu, 'bg', lambda: self.setStatMasks('bg'), icon=str(respath / 'icons' / 'px16' / 'cfa_bg.png'))
        self.addMenuItem(dataSplitMenu, 'gb', lambda: self.setStatMasks('gb'), icon=str(respath / 'icons' / 'px16' / 'cfa_gb.png'))
        self.addMenuItem(dataSplitMenu, 'rg', lambda: self.setStatMasks('rg'), icon=str(respath / 'icons' / 'px16' / 'cfa_rg.png'))
        self.addMenuItem(dataSplitMenu, 'gr', lambda: self.setStatMasks('gr'), icon=str(respath / 'icons' / 'px16' / 'cfa_gr.png'))
                
        
        self.selectMenu.addMenu(dataSplitMenu)                                            
        self.selectMenu.addMenu(CustomMaskMenu(self))

        self.addMenuItem(self.selectMenu, 'Show/Hide Mask Layer', self.toggle_mask,
            checkcall = lambda: self.imviewer.imgdata.layers.get('mask', {}).get('visible', False),
            statusTip="Show or hide the mask layer")
        
        self.addMenuItem(self.selectMenu, 'Show/Hide Roi Pattern', self.toggle_roi_mask,
            checkcall = lambda: self.imviewer.imgdata.roi_mask_visible,
            statusTip="Show or hide the mask layer")        
            
        self.selectMenu.addSeparator()
        
        self.searchForRoiSlots = []
        
        for i in range(4):
            action = QAction(f"Custom Mask {i}", self, triggered=wrap(self.selectNamedMask, i))
            action.setVisible(False)
            self.searchForRoiSlots.append(action)
            self.selectMenu.addAction(action)                                                      
        
        #Analyse
        vertical_spectr_icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'diagramm_90.png'))
        
        self.addMenuItem(self.analyseMenu, 'Statistics', self.showStatisticPanel,
            icon=QtGui.QIcon(str(respath / 'icons' / 'px16' / 'table_sum.png')))            
            
        self.addMenuItem(self.analyseMenu, 'Levels', self.showLevelsPanel,
            icon=QtGui.QIcon(str(respath / 'icons' / 'px16' / 'color_adjustment.png')))
        
        self.addMenuItem(self.analyseMenu, 'Horizontal Spectrogram', self.horizontalSpectrogram,
            icon=QtGui.QIcon(str(respath / 'icons' / 'px16' / 'diagramm.png')),
            statusTip="Horizontal Spectrogram")
        self.addMenuItem(self.analyseMenu, 'Vertical Spectrogram', self.verticalSpectrogram,
            icon=vertical_spectr_icon,
            statusTip="Vertical Spectrogram")
        self.addMenuItem(self.analyseMenu, 'Measure Distance', self.measureDistance,
            statusTip="Measure Distance",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'geolocation_sight.png')))

        self.addBaseMenu(['levels', 'values', 'image', 'statistics'])                                
        
        
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
        self.imgprof.setSelection(maskName, modify=True)
    

    def addBindingTo(self, category, panid):
        targetPanel = super().addBindingTo(category, panid)
        if targetPanel is None: return None
        
        if targetPanel.category == 'image':
            self.visibleRegionChanged.connect(targetPanel.changeVisibleRegion)
            
        elif targetPanel.category == 'levels':
            self.contentChanged.connect(targetPanel.imageContentChanged)
            self.roiChanged.connect(targetPanel.roiChanged)
            self.gainChanged.connect(targetPanel.imageGainChanged)
            
        elif targetPanel.category == 'statistics':
            self.contentChanged.connect(targetPanel.updateStatistics)
            
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
            
        elif targetPanel.category == 'statistics':
            self.contentChanged.disconnect(targetPanel.updateStatistics)            
            
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

            result = fedit(options_form, title='New Image')
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
        open_image_dialog(self)


    def openImage(self, filepath, format=None, zoom='full'):       
        open_image_and_show(self, filepath, format, zoom)                          
    

    def importRawImage(self):
        arr = import_raw_image()
        self.show_array(arr, zoomFitHist=True)
        self.zoomFull()
            

    def saveImageDialog(self):
        save_image_dialog()
                
                
    def send_array_to_gdesk(self):
        port = gui._qapp.cmdserver.port
        hostname = 'localhost'
        
        form = [('port', port), ('host', hostname), ('new panel', False)]
        results = fedit(form, title='Send Array to Host')
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

    # def placeRawOnClipboard(self):
        # clipboard = self.qapp.clipboard()
        # array = self.ndarray
        # qimg = imconvert.process_ndarray_to_qimage_8bit(array, 0, 1)
        # clipboard.setImage(qimg)


    def placeQimgOnClipboard(self):

        clipboard = self.qapp.clipboard()
        #If qimg is not copied, GH crashes on paste after the qimg instance has been garbaged!
        #Clipboard can only take ownership if the object is a local?
        qimg = self.imviewer.imgdata.qimg.copy()
        clipboard.setImage(qimg)
        
        
    def placeViewerOnClipboard(self):
        qimg, props = self.getViewerQImage()        
        clipboard = self.qapp.clipboard()
        clipboard.setImage(qimg.copy())        


    def placeViewerWithMemoOnClipboard(self):
        qimg, props = self.getViewerQImage()
        memo = props.get('memo', '')

        form = gui.fedit([
            ('Memo', memo + '\n'),
            ], title='Memo on image to clipboard')        
        if form is None: return

        memo = form[0]
        lines = memo.splitlines()        

        if len(lines) > 0:
            arr = imconvert.qimage_to_ndarray(qimg)
            avg = arr.mean()
            qp = QtGui.QPainter(qimg)
            font = QFont(config["console"]["font"])            
            font.setPixelSize(14)
            qp.setFont(font)
            if avg > 127:
                qp.setPen(QColor(0,0,0))
            else:
                qp.setPen(QColor(255,255,255))
            for line in lines:
                qp.drawText(5, 10, line)
                qp.translate(0, 15)
            qp.end()
        
        clipboard = self.qapp.clipboard()
        clipboard.setImage(qimg.copy())


    def getViewerQImage(self, slices=None, zoom=None, show_masks=True):
        imgdata = self.imviewer.imgdata
        
        if not slices is None or self.imviewer.roi.isVisible():            
            if slices is None:  
                slices = imgdata.selroi.getslices()
            height, width = self.ndarray.shape[:2]
            start_y, stop_y, step_y = slices[0].indices(imgdata.height)
            start_x, stop_x, step_x = slices[1].indices(imgdata.width)
        else:
            start_x, start_y, width, height = self.imviewer.visibleRegion()
            start_x = max(0, start_x)
            start_y = max(0, start_y)
            stop_y = min(start_y + height, imgdata.height)
            stop_x = min(start_x + width, imgdata.width)            

        qimg = self.imviewer.paintToQImageCropped(start_y, stop_y, start_x, stop_x, zoom=zoom, show_masks=show_masks)

        lines = []
        lines.append(f'{self.offset:.1f}→{self.white:.1f}')
        lines.append(f'{stop_y-start_y:.0f}x{stop_x-start_x:.0f}')   

        if (start_y > 0) or (start_x > 0):
            lines.append(f'{start_y:.0f},{start_x:.0f}')
        if self.gamma != 1:
            lines.append(f'Gamma: {self.gamma:.2f}')        

        # Statistics can be copy to clipboard from the statistcs table
        # for i, (name, stat) in enumerate(self.imviewer.imgdata.chanstats.items()):
            # if not name.startswith('roi.'): continue
            # if not stat.is_valid(): continue
            # lines.append(f'{name} {stat.slices_repr()}: {stat.Mean():.1f} ± {stat.Std():.1f}')                 

        props = {}
        
        props['memo'] = '\n'.join(lines)        
        props['start_y'] = start_y
        props['stop_y'] = stop_y
        props['start_x'] = start_x
        props['stop_x'] = stop_x
        
        return qimg, props


    def showFromClipboard(self):
        arr = gui.get_clipboard_image()
        self.show_array(arr)
        
        
    def grabDesktop(self):       
        screens = self.qapp.screens()    
        screen_names = [1] + [sc.name() for sc in screens]
        form = [
            ('Screen', screen_names),
            ('Delay', 1.0)]
        
        results = fedit(form, title='Screenshot')
        
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

            results = fedit(form, title = 'Offset & Gain')
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
        
        
    def modifyDefaultGain(self, step=1):
        
        if step > 0:
            new_default = 2 ** np.floor(np.log2(self.gain) + step)
        else:
            new_default = 2 ** np.ceil(np.log2(self.gain) + step)
            
        self.defaults['gain'] = new_default
        self.defaultOffsetGain()
            

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

            results = fedit(form, title='Black & White')
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

            results = fedit(form, title='Grey & Gain')
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
            results = fedit([('Zoom value %', args['zoom'])], title='Set Zoom')
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
        

    def zoomToRoi(self):
        self.imviewer.zoomToRoi()        
        
        
    def zoomToRegion(self, x, y, width, height):        
        self.imviewer.zoomToRegion(x, y, width, height)
        

    def setColorMap(self):
        with ActionArguments(self) as args:
            args['cmap'] = 'grey'

        if args.isNotSet():
            colormapdialog = ColorMapDialog()
            colormapdialog.exec_()
            if not colormapdialog.cm_name is None:
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

        color_scheme = QApplication.instance().color_scheme
        if color_scheme == "Dark":
            config["image background dark"] = rgb
            self.imviewer.setBackgroundColor(*config["image background dark"])
        else:
            config["image background"] = rgb
            self.imviewer.setBackgroundColor(*config["image background"])


    def setMaskApperance(self):
        old_color = QtGui.QColor(*config.get('mask color', (255,0,0)))
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

        if 'mask' in self.imviewer.imgdata.layers:
            self.imviewer.imgdata.change_layer_appearance('mask', color=rgb)

        config['mask color'] = list(rgb)
        self.refresh()


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


    def roiSelected(self, roi_name):
        # roi_names = roi_name.split(',')
        # self.imviewer.imgdata.highLightRois(roi_names)
        # self.refresh()
        self.imgprof.selectMask(roi_name)
        
        
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
        self.imviewer.imgdata.addMaskStatsDialog()        
        self.imviewer.roi.hideRoi()
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


    def configureRois(self):
        dialog = RoiConfigDialog(self.imviewer.imgdata)
        dialog.exec_()
        self.roiConfigChanged.emit()
        self.refresh()
        
        
    def toggle_mask(self):
        imgdata = self.imviewer.imgdata
        if imgdata.layers.get('mask', {}).get('visible', False):
            imgdata.hide_layer('mask')
        else:
            imgdata.show_layer('mask')
        self.imviewer.refresh()


    def toggle_roi_mask(self):
        imgdata = self.imviewer.imgdata
        imgdata.show_roi_mask(not imgdata.roi_mask_visible)
        self.imviewer.refresh()


    def setStatMasks(self, mode):
        self.imviewer.imgdata.init_channel_statistics(mode)
        self.refresh()        

        

    ############################
    # Analyse Menu Connections
    
    def showStatisticPanel(self):        
        
        if not self.bindedPanel('statistics') is None:
            self.bindedPanel('statistics').show_me()
            return

        imgpanel = gui.qapp.panels['image'][self.panid]
        statpanel =  gui.qapp.panels.new('statistics')
        
        imgpanel.addBindingTo('statistics', statpanel.panid)
        statpanel.addBindingTo('image', self.panid)
        
        statpanel.setActiveColumns(["Mean", "Std", "Min", "Max"])
        self.roiConfigChanged.connect(statpanel.statistics.formatTable)
        
        
    def showLevelsPanel(self):        
        
        if not self.bindedPanel('levels') is None:
            self.bindedPanel('levels').show_me()
            return

        imgpanel = gui.qapp.panels['image'][self.panid]
        levelspanel =  gui.qapp.panels.new('levels')
        
        imgpanel.addBindingTo('levels', levelspanel.panid)
        levelspanel.addBindingTo('image', self.panid)      
    

    def horizontalSpectrogram(self):
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(spectr_hori, args=(gui.vs,))
        

    def verticalSpectrogram(self):
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(spectr_vert, args=(gui.vs,))
        
        
    def measureDistance(self):
        panel = gui.qapp.panels.selected('console')

        from .proxy import ImageGuiProxy

        def stage1_done(mode, error_code, result):
            pass

        panel.task.call_func(ImageGuiProxy.get_distance, callback=stage1_done)        
        

    #############################

    def show_array(self, array, zoomFitHist=False, log=True, skip_init=False):
        self.refresh_offset_gain(array, log=log, skip_init=skip_init)                   
        self.contentChanged.emit(self.panid, zoomFitHist)


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


class ImageProfileWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent=parent)

        self.imviewer = ImageViewerWidget(self)

        self.corner = CornerWidget(self)
        self.corner.statistics.roiSelected.connect(self.parent().roiSelected)
        self.parent().roiConfigChanged.connect(self.corner.statistics.formatTable)        

        self.imviewer.imgdata.roi_pattern_visible_changed = self.corner.cornerMenu.setRoiMaskVisible
        
        self.rowPanel = ProfilerPanel(self, 'x', self.imviewer)
        self.colPanel = ProfilerPanel(self, 'y', self.imviewer)

        self.gridsplit = GridSplitter(None)

        self.imviewer.zoomPanChanged.connect(self.colPanel.zoomToImage)
        self.imviewer.zoomPanChanged.connect(self.rowPanel.zoomToImage)

        self.gridsplit.addWidget(self.corner, 0, 0, alignment=Qt.AlignLeft | Qt.AlignTop)
        self.gridsplit.addWidget(self.rowPanel, 0, 1)
        self.gridsplit.addWidget(self.colPanel, 1, 0)
        self.gridsplit.addWidget(self.imviewer, 1, 1)

        self.setLayout(self.gridsplit)

        self.profilesVisible = False
        self.selected_masks = []


    def toggleProfileVisible(self):
        self.profilesVisible = not self.profilesVisible
                
        
    def toggleMask(self):
        self.parent().toggle_mask()


    def toggleRoiMask(self):
        self.parent().toggle_roi_mask()
        
        
    def selectRoi(self, option):
    
        if option in ['show roi only']:
            self.imviewer.roi.showRoi()
            self.imviewer.imgdata.selectRoiOption(option)
            self.refresh()
            
        elif option == 'custom visibility':
            self.parent().configureRois()                                  
        

    def showOnlyRuler(self):
            
        self.corner.setFixedWidth(20)
        self.corner.setFixedHeight(20)
        self.rowPanel.showOnlyRuler()
        self.colPanel.showOnlyRuler()
        self._profilesVisible = False

        gui.qapp.processEvents()
        self.refresh_profile_views()


    def showProfiles(self):

        self.corner.show()
        self.corner.setMaximumHeight(500)
        self.corner.setMaximumWidth(500)        
        
        self.rowPanel.show()
        self.rowPanel.setMinimumHeight(20)
        self.rowPanel.setMaximumHeight(500)        
        self.colPanel.show()
        self.colPanel.setMinimumWidth(20)
        self.colPanel.setMaximumWidth(500)
        
        self.parent().parent().parent().setTabBarAutoHide(False)
        self.parent().statusBar().show()

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
        
    
    def hideRulers(self):        
        self.corner.hide()
        self.rowPanel.hide()
        self.colPanel.hide()                
        
        for splitter in self.gridsplit.splitters:
            splitter.hide()
        
        #Hide tab and layout button also
        self.parent().parent().parent().setTabBarAutoHide(True)
        self.parent().statusBar().hide()
            
        self.gridsplit.setColumnStretches([0, 1])
        self.gridsplit.setRowStretches([0, 1])

        
    def drawMaskProfiles(self):         
        self.rowPanel.drawMaskProfiles()
        self.colPanel.drawMaskProfiles()                           


    def selectMasks(self, masks):
        # This a selection of one of the roi presets (Mono, BG, ...)
        self.imviewer.imgdata.init_channel_statistics(masks)
        self.parent().roiConfigChanged.emit()
        self.refresh()

    
    def selectMask(self, mask):
        # This is a selection of one or more of the existing roi's
        if mask == '':
            masks = []
        else:
            masks = mask.split(',')            
            
        self.imviewer.imgdata.highLightRois(masks)
        self.rowPanel.selectProfiles(masks)
        self.colPanel.selectProfiles(masks)
        self.refresh()
        
        
    def setSelection(self, mask, modify=False):        
        roi = self.imviewer.roi
        
        if not (mask == ''):
            chanstats = self.imviewer.imgdata.chanstats[mask]            
            selroi = self.imviewer.imgdata.selroi  
            selroi.xr.setfromslice(chanstats.slices[1])
            selroi.yr.setfromslice(chanstats.slices[0])             
            
            if modify:
                color = chanstats.plot_color            
                roi.initUI(color)
                self.selected_masks = [mask]
                
            roi.clip()
            roi.show()
            roi.roiChanged.emit()

        else:
            self.selected_masks.clear()
            roi.initUI()
            
            
    def showBmask(self, mask_name, modify=False):
        chanstats = self.imviewer.imgdata.chanstats[mask_name]            
        bmask = chanstats.bmask
        self.imviewer.imgdata.set_mask(bmask, alpha=128)        
        self.imviewer.refresh()  
        
        
    def drawRoiProfile(self, rois=None):                     
        slices = self.roi_slices        
        self.rowPanel.drawMaskProfiles(roi_only=True, rois=rois)
        self.colPanel.drawMaskProfiles(roi_only=True, rois=rois)            
        

    def set_profiles_visible(self, visible):
        if visible:
            self.corner.setNormalLayout()
            self.showProfiles()
            
        else:
            self.corner.setMiniLayout()
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
        
        self.imviewer.refresh()
               
        
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
            checkcall = lambda: self.imgprof.profilesVisible,
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'chart_stock.png')),
            statusTip="Show or Hide the image column and row profiles")
            
        #self.addMenuItem(self.viewMenu, 'Show Only Image', self.imgprof.hideRulers)
            
        if not kwargs.get('empty', True): self.openTestImage()
        
        
    def addBindingTo(self, category, panid):            
        targetPanel = super().addBindingTo(category, panid)    
        if targetPanel is None: return None                

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
        imgdata = self.imviewer.imgdata
        selroi = imgdata.selroi            
        
        self.roiChanged.emit(self.panid)
        self.imgprof.drawRoiProfile(self.imgprof.selected_masks)
        #self.imgprof.refresh_profile_views()
        self.refresh()
        
        
    def removeRoiProfile(self):
        self.imgprof.selected_masks.clear()
        self.imgprof.imviewer.imgdata.disable_roi_statistics()
        self.imgprof.drawMaskProfiles()
        self.imgprof.refresh_profile_views()
        self.roiChanged.emit(self.panid)
        
    
    def refresh_profiles_and_stats(self):     
        
        if self.imgprof.profilesVisible:
            self.imgprof.drawMaskProfiles()
            self.imgprof.refresh_profile_views()  
            

    def show_array(self, array=None, zoomFitHist=False, log=True, skip_init=False):
        super().show_array(array, zoomFitHist, log=log, skip_init=skip_init)        
        self.refresh_profiles_and_stats()
        

    @property
    def imviewer(self):
        return self.imgprof.imviewer
    

    def refresh(self):
        self.imviewer.refresh()
        self.refresh_profiles_and_stats()


    def showHideProfiles(self):
        self.imgprof.profilesVisible = not self.imgprof.profilesVisible

