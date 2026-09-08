from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets, API_NAME
from qtpy.QtCore import Qt, Signal

from ... import config
from .imgdata import MaskPresetButton

from qtpy.QtCore import Qt, Signal, QUrl
from gdesk import gui


RESPATH = Path(config['respath'])        
        
        
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
            "Statistics Panel",
            self.showPanel.emit,
        )

        self.masksPresetBtn = MaskPresetButton()
        self.masksPresetBtn.setText('ROI presets')
        self.masksPresetBtn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.masksPresetBtn.maskPreset.connect(lambda mask: self.maskPreset.emit(mask))
        
        preset_action = QtWidgets.QWidgetAction(self)
        preset_action.setDefaultWidget(self.masksPresetBtn)
        self.menu.addAction(preset_action)

        self.menu.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layer_mask.png')),
            'Show/Hide Mask Layer',
            self.toggleMask.emit
        )

        self.roiMaskAction = QtWidgets.QAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layer_grid.png')),
            'Show/Hide Roi Pattern',
            self,
        )
        self.roiMaskAction.setCheckable(True)
        self.roiMaskAction.toggled.connect(self.toggleShowRoiMask)
        self.menu.addAction(self.roiMaskAction)


    def setRoiMaskVisible(self, visible):
        if visible:
            self.roiMaskBtn.setChecked(True)
        else:
            self.roiMaskBtn.setChecked(False)


    def toggleShowRoiMask(self):
        self.toggleRoiMask.emit()
