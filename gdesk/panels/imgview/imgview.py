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
from ...widgets.grid import GridSplitter
from ...utils import imconvert
from ...gcore.utils import ActionArguments

from .profile import ProfilerPanel

from .corner import CornerWidget
from .regoi import RoiConfigDialog

from .view_widgets import StatusPanel

from .fileio import FileMenu
from .edit import EditMenu
from .view import ViewMenu
from .select import SelectMenu
from .canvas import CanvasMenu
from .imgedit import ImageEditMenu
from .imgprocess import ProcessMenu
from .analyse import AnalyseMenu
from .operation import OperationMenu

if has_cv2:
    from .opencv import OpenCvMenu

here = Path(__file__).parent.absolute()
respath = Path(config['respath'])             


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

        self.createMenus()
        self.createStatusBar()

    def createMenus(self):
        self.fileMenu = FileMenu("&File", self.menuBar(), self)          
        self.editMenu = EditMenu("&Edit", self.menuBar(), self)
        self.viewMenu = ViewMenu("&View", self.menuBar(), self)
        self.selectMenu = SelectMenu("&Select", self.menuBar(), self)        
        self.canvasMenu = CanvasMenu("&Canvas", self.menuBar(), self)
        self.imageMenu = ImageEditMenu("&Image", self.menuBar(), self)        
        self.processMenu = ProcessMenu("&Process", self.menuBar(), self)
        self.analyseMenu = AnalyseMenu("&Analyse", self.menuBar(), self)
        
        if has_cv2:
            self.openCvMenu = OpenCvMenu("Open CV", self.menuBar(), self)
        
        self.operationMenu = OperationMenu("Operation", self.menuBar(), self)

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
        self.statusBar().addWidget(self.statuspanel, 1)
        

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
            
        elif targetPanel.category == 'statistics':
            self.contentChanged.connect(targetPanel.updateStatistics)
            self.roiChanged.connect(targetPanel.formatTable)
            
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
            self.roiChanged.disconnect(targetPanel.roiChanged)
            self.gainChanged.disconnect(targetPanel.imageGainChanged)
            
        elif targetPanel.category == 'statistics':
            self.contentChanged.disconnect(targetPanel.updateStatistics)            
            self.roiChanged.disconnect(targetPanel.formatTable)
            
        elif targetPanel.category == 'values':
            self.imviewer.pixelSelected.disconnect(targetPanel.pick)
            
        return targetPanel
    

    def changeVisibleRegion(self, x, y, w, h, zoomSnap, emit, zoomValue):
        self.imviewer.zoomNormalized(x, y, w, h, zoomSnap, emit, zoomValue)
        self.imviewer.roi.recalcGeometry()
        

    ############################
    # File Menu Connections
        
    def duplicate(self, floating=False):
        newPanel = super().duplicate(floating)
        newPanel.show_array(self.ndarray)
        return newPanel       
        

    def close_panel(self):
        super().close_panel()

        #Deleting self.imviewer doesn't seem to delete the imgdata
        del self.imviewer.imgdata


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
             

    def refresh(self):
        self.show_array(None)
        

    ############################
    # View Menu Connections

    def configureRois(self):
        self.selectMenu.configureRois()        
        

    #############################

    def show_array(self, array, zoomFitHist=False, log=True, skip_init=False):
        self.viewMenu.show_array(array, zoomFitHist, log, skip_init)


    def refresh_offset_gain(self, array=None, zoomFitHist=False, log=True, skip_init=False):
        self.viewMenu.refresh_offset_gain(array, zoomFitHist, log, skip_init)
        

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
        self.corner.statistics.roiSelected.connect(self.selectMask)
        self.parent().roiConfigChanged.connect(self.corner.statistics.formatTable)
        
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
        self.parent().selectMenu.toggle_mask()


    def toggleRoiMask(self):
        self.parent().selectMenu.toggle_roi_mask()
        
        
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
        self.fileMenu.openImage(respath / 'images' / 'gamma_test_22.png', zoom=1)


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
        self.refresh()                
        self.roiChanged.emit(self.panid)
        
        
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
        self.imgprof.corner.statistics.formatTable()


    def showHideProfiles(self):
        self.imgprof.profilesVisible = not self.imgprof.profilesVisible

