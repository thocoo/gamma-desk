from pathlib import Path

import numpy as np

from qtpy import QtCore, QtGui, QtWidgets, API_NAME
from qtpy.QtCore import Qt, Signal

from ...dialogs.formlayout import fedit
from ... import config
from .imgdata import get_next_color_tuple, MaskPresetButton

from qtpy.QtCore import Qt, Signal, QUrl
from gdesk import gui


RESPATH = Path(config['respath'])

RESERVED_MASK_FULL = []
RESERVED_MASK_ROI = []
    
if API_NAME == 'PySide6' and hasattr(QtGui, "QAbstractItemView"):
    NOEDITTRIGGERS = QtGui.QAbstractItemView.NoEditTriggers
else:
    NOEDITTRIGGERS = QtWidgets.QTableWidget.NoEditTriggers


def sort_masks(masks):
    return masks

    
def get_last_active(chanstats):
    
    n = len(chanstats)
    
    for i, key in enumerate(chanstats.order[::-1]):    
        if chanstats[key].active:
            return (n - i - 1)
            
    return 0       
        
        
class StatisticsToolBar(QtWidgets.QToolButton): 
    
    toggleProfile = Signal()
    toggleDock = Signal()
    selectRoi = Signal(str)
    toggleMask = Signal()
    toggleRoiMask = Signal()
    maskPreset = Signal(str)
    showPanel = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.menu = QtWidgets.QMenu(self)
        self.setMenu(self.menu)
        self.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.initUi()
        
        
    def initUi(self):
        fontHeight = self.fontMetrics().height()
        self.setIconSize(QtCore.QSize(int(fontHeight * 3 / 2), int(fontHeight * 3 / 2)))
        self.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'chart_stock.png')))
        self.setToolTip('Profile options')

        self.menu.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'chart_stock.png')),
            'Show/Hide profiles',
            lambda: self.toggleProfile.emit(),
        )

        self.menu.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layers_map.png')),
            "Configure Roi's",
            lambda: self.selectRoi.emit('custom visibility'),
        )

        self.menu.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'table_sum.png')),
            "Configure Roi's",
            self.showPanel.emit,
        )

        self.masksPresetBtn = MaskPresetButton()
        self.masksPresetBtn.maskPreset.connect(lambda mask: self.maskPreset.emit(mask))
        preset_action = QtWidgets.QWidgetAction(self)
        preset_action.setDefaultWidget(self.masksPresetBtn)
        self.menu.addAction(preset_action)

        self.maskBtn = QtWidgets.QToolButton(self)
        self.maskBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layer_mask.png')))
        self.maskBtn.setToolTip('Show/Hide Mask Layer')
        self.maskBtn.clicked.connect(self.toggleShowMask)
        mask_action = QtWidgets.QWidgetAction(self)
        mask_action.setDefaultWidget(self.maskBtn)
        self.menu.addAction(mask_action)

        self.roiMaskBtn = QtWidgets.QToolButton(self)
        self.roiMaskBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layer_grid.png')))
        self.roiMaskBtn.setCheckable(True)
        self.roiMaskBtn.setToolTip('Show/Hide Roi Pattern')
        self.roiMaskBtn.clicked.connect(self.toggleShowRoiMask)
        roi_mask_action = QtWidgets.QWidgetAction(self)
        roi_mask_action.setDefaultWidget(self.roiMaskBtn)
        self.menu.addAction(roi_mask_action)


    def toggleShowMask(self):
        self.toggleMask.emit()


    def setRoiMaskVisible(self, visible):
        if visible:
            self.roiMaskBtn.setChecked(True)
        else:
            self.roiMaskBtn.setChecked(False)


    def toggleShowRoiMask(self):
        self.toggleRoiMask.emit()
