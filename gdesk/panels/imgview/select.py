import logging
from pathlib import Path

logger = logging.getLogger(__name__)

import numpy as np

try:
    import scipy
    import scipy.ndimage
    HAS_SCIPY = True

except:
    HAS_SCIPY = False

from qtpy import QtCore, QtGui
from qtpy.QtWidgets import QAction, QMenu

from ...panels import CheckMenu
from ...gcore.utils import ActionArguments
from ...dialogs.formlayout import fedit
from .regoi import RoiConfigDialog

from ... import config, gui

RESPATH = Path(config['respath'])


def wrap(func, *args, **kwargs):
    def wrapper():
        func(*args, **kwargs)
        
    return wrapper
    

class CustomMaskMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__('Select Roi', parent)
        self.imgpanel = self.parent()
        self.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'selection_pane.png')))


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


class SelectMenu(CheckMenu):
    
    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)    
        
        self.basePanel = basePanel 
    
        basePanel.addMenuItem(self, 'Reselect', self.reselect,
            statusTip="Select or reselect a region of interest",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'select_restangular.png')))
            
        basePanel.addMenuItem(self, 'Deselect', self.selectNone,
            statusTip="Deselect, select nothing")
            
        basePanel.addMenuItem(self, 'Select Dialog...', self.setRoi,
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layer_select.png')),
            statusTip="Select with input numbers dialog")
            
        basePanel.addMenuItem(self, 'Select 1 Pixel...'   , self.jumpToDialog,
            statusTip="Select 1 pixel and zoom to it",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'canvas.png')))
        
        self.addSeparator()
            
        basePanel.addMenuItem(self, 'Add Roi Statistics...', self.addMaskStatistics,
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'create_from_selection.png')))
            
        basePanel.addMenuItem(self, 'Remove Roi Statistics...', self.removeMaskStatistics)            
                    
        basePanel.addMenuItem(self, "Configure Roi's...", self.configureRois,
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layers_map.png')))
                    
        dataSplitMenu = QMenu("Roi Presets")
        dataSplitMenu.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'select_by_color.png')))        
        
        basePanel.addMenuItem(dataSplitMenu, 'mono', lambda: self.setStatMasks('mono'), icon=str(RESPATH / 'icons' / 'px16' / 'color_gradient.png'))
        basePanel.addMenuItem(dataSplitMenu, 'rgb', lambda: self.setStatMasks('rgb'), icon=str(RESPATH / 'icons' / 'px16' / 'color.png'))            
        basePanel.addMenuItem(dataSplitMenu, 'bg', lambda: self.setStatMasks('bg'), icon=str(RESPATH / 'icons' / 'px16' / 'cfa_bg.png'))
        basePanel.addMenuItem(dataSplitMenu, 'gb', lambda: self.setStatMasks('gb'), icon=str(RESPATH / 'icons' / 'px16' / 'cfa_gb.png'))
        basePanel.addMenuItem(dataSplitMenu, 'rg', lambda: self.setStatMasks('rg'), icon=str(RESPATH / 'icons' / 'px16' / 'cfa_rg.png'))
        basePanel.addMenuItem(dataSplitMenu, 'gr', lambda: self.setStatMasks('gr'), icon=str(RESPATH / 'icons' / 'px16' / 'cfa_gr.png'))
                        
        self.addMenu(dataSplitMenu)                                            
        self.addMenu(CustomMaskMenu(self.basePanel))

        basePanel.addMenuItem(self, 'Show/Hide Mask Layer', self.toggle_mask,
            checkcall = lambda: self.imviewer.imgdata.layers.get('mask', {}).get('visible', False),
            statusTip="Show or hide the mask layer")
        
        basePanel.addMenuItem(self, 'Show/Hide Roi Pattern', self.toggle_roi_mask,
            checkcall = lambda: self.imviewer.imgdata.roi_mask_visible,
            statusTip="Show or hide the mask layer")        
            
        self.addSeparator()
        
        basePanel.searchForRoiSlots = []
        
        for i in range(4):
            action = QAction(f"Custom Mask {i}", self, triggered=wrap(self.selectNamedMask, i))
            action.setVisible(False)
            basePanel.searchForRoiSlots.append(action)
            self.addAction(action)
            

    @property
    def imviewer(self):
        return self.basePanel.imviewer
        
        
    def refresh(self):
        self.imviewer.refresh()        
        
        
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
        self.basePanel.roiChanged.emit(self.panid)


    def configureRois(self):
        dialog = RoiConfigDialog(self.imviewer.imgdata)
        dialog.exec_()
        self.basePanel.roiConfigChanged.emit()
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


    def selectNamedMask(self, i):
        # TO DO: check this !
        
        maskName = self.searchForRoiSlots[i].text()
        self.imgprof.selectMask(maskName)
        self.imgprof.setSelection(maskName, modify=True)        