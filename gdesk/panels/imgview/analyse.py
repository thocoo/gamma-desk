import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

from qtpy import QtCore, QtGui
from qtpy.QtWidgets import QAction, QMenu, QColorDialog, QApplication

from .spectrogram import spectr_hori, spectr_vert

from ...panels import CheckMenu
from ...gcore.utils import ActionArguments
from ...dialogs.formlayout import fedit
from ...dialogs.colormap import ColorMapDialog

from ... import config, gui

RESPATH = Path(config['respath'])


class AnalyseMenu(CheckMenu):
    
    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)    
        
        self.basePanel = basePanel 

        basePanel.addMenuItem(self, 'Statistics', self.showStatisticPanel,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'table_sum.png')))            
            
        basePanel.addMenuItem(self, 'Levels', self.showLevelsPanel,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color_adjustment.png')))
        
        basePanel.addMenuItem(self, 'Horizontal Spectrogram', self.horizontalSpectrogram,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'diagramm.png')),
            statusTip="Horizontal Spectrogram")
            
        basePanel.addMenuItem(self, 'Vertical Spectrogram', self.verticalSpectrogram,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'diagramm_90.png')),
            statusTip="Vertical Spectrogram")
            
        basePanel.addMenuItem(self, 'Measure Distance', self.measureDistance,
            statusTip="Measure Distance",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'geolocation_sight.png')))
            
            
    def showStatisticPanel(self):        
        
        if not self.basePanel.bindedPanel('statistics') is None:
            self.basePanel.bindedPanel('statistics').show_me()
            return

        imgpanel = gui.qapp.panels['image'][self.basePanel.panid]
        statpanel =  gui.qapp.panels.new('statistics')        
        
        imgpanel.addBindingTo('statistics', statpanel.panid)
        statpanel.addBindingTo('image', self.basePanel.panid)        
        
        statpanel.setActiveColumns(["Mean", "Std", "Min", "Max"])
        
        imgpanel.roiConfigChanged.connect(statpanel.statistics.formatTable)
        
        
    def showLevelsPanel(self):        
        
        if not self.basePanel.bindedPanel('levels') is None:
            self.basePanel.bindedPanel('levels').show_me()
            return

        imgpanel = gui.qapp.panels['image'][self.basePanel.panid]
        levelspanel =  gui.qapp.panels.new('levels')
        
        imgpanel.addBindingTo('levels', levelspanel.panid)
        levelspanel.addBindingTo('image', self.basePanel.panid)      
    

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
        