from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets, API_NAME
from qtpy.QtCore import Qt, Signal

from ... import config
from .imgdata import MaskPresetButton

from qtpy.QtCore import Qt, Signal, QUrl
from gdesk import gui

from gdesk.panels.statistics.panel import Statistics, StatisticsToolBar


RESPATH = Path(config['respath'])        


class CornerWidget(QtWidgets.QWidget):

    def __init__(self, imviewer):
        super().__init__(imviewer)
        self.imviewer = imviewer

        self.cornerMenu = CornerToolBar()
        self.cornerMenu.toggleProfile.connect(self.imviewer.toggleProfileVisible)
        self.cornerMenu.selectRoi.connect(self.imviewer.selectRoi)
        self.cornerMenu.toggleMask.connect(self.imviewer.toggleMask)
        self.cornerMenu.toggleRoiMask.connect(self.imviewer.toggleRoiMask)
        self.cornerMenu.maskPreset.connect(self.imviewer.selectMasks)
        self.cornerMenu.showPanel.connect(self.imviewer.parent().showStatisticPanel)

        self.toolbar = StatisticsToolBar()

        self.statistics = Statistics(imviewer=self.imviewer.imviewer)
        self.imviewer.parent().contentChanged.connect(self.statistics.updateStatistics)         
        self.statistics.setActiveColumns(['Mean', 'Npix', 'Std'])        

        self.toolbar.copy.connect(self.statistics.copyTableToClipboard)
        self.toolbar.fitContent.connect(self.statistics.fitContent)
        self.toolbar.clearStats.connect(self.statistics.clearStatistics)
        self.toolbar.chooseStatistics.connect(self.statistics.chooseStatistics)        

        self.hlayout = QtWidgets.QHBoxLayout()
        self.hlayout.setContentsMargins(0, 0, 0, 0)
        self.hlayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.hlayout.setSpacing(0)
        
        self.cornerLayout = QtWidgets.QVBoxLayout(self)        
        self.cornerLayout.setContentsMargins(0, 0, 0, 0)
        self.cornerLayout.setSpacing(0)
        self.cornerLayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.cornerLayout.addLayout(self.hlayout)

        self.hlayout.addWidget(self.cornerMenu)
        self.hlayout.addWidget(self.toolbar)

        self.cornerLayout.addWidget(self.statistics)


    def setMiniLayout(self):
        self.toolbar.hide()
        self.statistics.hide()


    def setNormalLayout(self):
        self.toolbar.show()
        self.statistics.show()
    
        
        
class CornerToolBar(QtWidgets.QToolButton): 
    
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
