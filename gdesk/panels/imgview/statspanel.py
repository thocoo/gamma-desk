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


#https://github.com/yjg30737/pyqt-checkbox-table-widget/blob/main/pyqt_checkbox_table_widget/checkBox.py
class CheckBox(QtWidgets.QWidget):
    checkedSignal = Signal(int, bool)

    def __init__(self, r_idx, flag, read_only=False):
        super().__init__()
        self.__r_idx = r_idx
        self.__initUi(flag, read_only)

    def __initUi(self, flag, read_only):
        chkBox = QtWidgets.QCheckBox()
        chkBox.setChecked(flag)
        chkBox.setEnabled(not read_only)
        chkBox.stateChanged.connect(self.__sendCheckedSignal)

        lay = QtWidgets.QGridLayout()
        lay.addWidget(chkBox)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(chkBox, Qt.AlignmentFlag.AlignCenter)

        self.setLayout(lay)        

    def __sendCheckedSignal(self, flag):
        self.checkedSignal.emit(self.__r_idx, flag)

    def isChecked(self):
        f = self.layout().itemAt(0).widget().isChecked()
        return Qt.Checked if f else Qt.Unchecked

    def setChecked(self, f):
        if isinstance(f, Qt.CheckState):
            self.getCheckBox().setCheckState(f)
        elif isinstance(f, bool):
            self.getCheckBox().setChecked(f)

    def getCheckBox(self):
        return self.layout().itemAt(0).widget()    
    

class StatisticsPanel(QtWidgets.QWidget):    
    
    maskSelected = Signal(str)
    activesChanged = Signal()
    
    setSelection = Signal(str)
    showBmask = Signal(str)
    hideMask = Signal(str)
    
    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()
        
    def initUi(self):        
        self.table = QtWidgets.QTableWidget()                
        self.table.viewport().installEventFilter(self)
        
        headers = self.table.horizontalHeader()
        headers.setContextMenuPolicy(Qt.CustomContextMenu)
        headers.customContextMenuRequested.connect(self.handleHeaderMenu)        
        headers.setMinimumSectionSize(20)
        
        self.setActiveColumns(["Mean", "Std", "Min", "Max"])
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)               
        self.table.setEditTriggers(NOEDITTRIGGERS)
        
        self.table.horizontalHeader().setDefaultSectionSize(20)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.selectionModel().currentRowChanged.connect(self.currentRowChanged)
        self.table.selectionModel().selectionChanged.connect(self.selectionChanged)
        self.table.cellDoubleClicked.connect(self.setImviewSelection)        
        self.table.customContextMenuRequested.connect(self.handleContextMenu)
        
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setContentsMargins(0,0,0,0)
        self.vbox.setSpacing(0)
        self.setLayout(self.vbox)                       
        self.vbox.addWidget(self.table)
        
        self.contextMenu = QtWidgets.QMenu('Mask')
        act = QtWidgets.QAction('Select', self, triggered=self.setImviewSelection)
        act.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'select_restangular.png')))
        self.contextMenu.addAction(act)
        
        # act = QtWidgets.QAction('Show Bmask', self, triggered=self.setImviewBmask)
        # act.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'mask.png')))
        # self.contextMenu.addAction(act)

        act = QtWidgets.QAction('Show/Hide Levels', self, triggered=self.showHideLevels)
        act.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color_adjustment.png')))
        self.contextMenu.addAction(act)        

        act = QtWidgets.QAction('Show/Hide Profiles', self, triggered=self.showHideProfiles)
        act.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'chart_stock.png')))
        self.contextMenu.addAction(act)

        act = QtWidgets.QAction('Show/Hide Image Viewer', self, triggered=self.showHideViewer)
        act.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'picture.png')))
        self.contextMenu.addAction(act)        

        act = QtWidgets.QAction('Copy', self, triggered=self.copyTableToClipboard)
        act.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'page_copy.png')))
        self.contextMenu.addAction(act)        


    def eventFilter(self, obj, event):
        if obj is self.table.viewport() and event.type() == QtCore.QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton and event.modifiers() == Qt.NoModifier:
                index = self.table.indexAt(event.pos())
                if index.isValid() and self.table.selectionModel().isRowSelected(index.row(), index.parent()):
                    self.table.clearSelection()
                    return True

        return super().eventFilter(obj, event)
        
        
    def setActiveColumns(self, columns=["Mean", "Std"]):
        self.columns = ["Name"] + columns
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)        


    def copyTableToClipboard(self):
        selection = self.table.selectionModel().selectedRows()
        
        text = ''
        for index in selection:
            row = index.row()
            rowText = []
            for col in range(self.table.columnCount()):
                cell = self.table.item(row, col)
                if cell is not None:
                    rowText.append(cell.text())
                else:
                    rowText.append('')
            text += '\t'.join(rowText) + '\n'
            
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        
    
    @property
    def imviewer(self):
        return self.parent().parent().parent().imviewer
        
        
    def currentRowChanged(self, index):
        row = index.row()
        selectedRow = self.table.item(row, 0)
        if selectedRow is None: return
        maskName = selectedRow.text()
        self.maskSelected.emit(maskName)
        
        
    def setImviewSelection(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.setSelection.emit(roi_name)


    def showHideLevels(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.imviewer.imgdata.chanstats[roi_name].hist_visible = not self.imviewer.imgdata.chanstats[roi_name].hist_visible
            self.maskSelected.emit(roi_name)


    def showHideProfiles(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.imviewer.imgdata.chanstats[roi_name].plot_visible = not self.imviewer.imgdata.chanstats[roi_name].plot_visible
            self.maskSelected.emit(roi_name)


    def showHideViewer(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.imviewer.imgdata.chanstats[roi_name].mask_visible = not self.imviewer.imgdata.chanstats[roi_name].mask_visible
            self.maskSelected.emit(roi_name)
            

    def setImviewBmask(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.showBmask.emit(roi_name)            
        
        
    def selectionChanged(self, selected, deselected):
        if selected.count() == 0:
            self.maskSelected.emit('')
            
        else:
            indices = self.table.selectionModel().selectedRows()
            maskNames = []
            for index in indices:
                row = index.row()
                maskName = self.table.item(row, 0).text()
                maskNames.append(maskName)
            self.maskSelected.emit(','.join(maskNames))


    def formatTable(self):    
    
        chanstats = self.imviewer.imgdata.chanstats        
        valid_stats_names = [name for name, stats in chanstats.items() if stats.is_valid() and stats.active]
            
        self.table.setRowCount(len(valid_stats_names))
        
        for i, name in enumerate(sort_masks(valid_stats_names)):
            stats = chanstats[name]       
            
            item_name = QtWidgets.QTableWidgetItem(name)
            R, G, B, A = stats.plot_color.getRgb()
            item_name.setBackground(QtGui.QColor(R, G, B, 128))            
            self.table.setItem(i, 0, item_name)            
                        
            for j, column in enumerate(self.columns[1:]):
                item = QtWidgets.QTableWidgetItem('')
                self.table.setItem(i, 1 + j, item)
            
            self.table.setRowHeight(i, 20)      

        self.table.resizeColumnsToContents()

        
    def updateStatistics(self):    
    
        chanstats = self.imviewer.imgdata.chanstats        
        
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            name = item.text()
            if not name in chanstats: continue
            if not chanstats[name].is_valid(): continue
            
            stats = chanstats[name] 
                        
            for j, column in enumerate(self.columns[1:]):
            
                if stats.active and column in stats.report_items:
                    value = stats.report_items[column]['func']()
                    
                    if value is None: continue
                    
                    fmt = stats.report_items[column]['fmt']

                    if isinstance(value, str):
                        text = value
                    else:
                        text = fmt.format(value)
                else:
                    text = ''
                    
                item = self.table.item(i, j+1)
                item.setText(text)     
            
            
    def handleHeaderMenu(self, pos):
        
        chanstats = self.imviewer.imgdata.chanstats  
        
        all_items = set()
        
        for channel_name, imgstat in chanstats.items():
            all_items = all_items.union(set(imgstat.report_items.keys()))        
    
        form = []
        
        for stat in all_items:
            form.append((stat, stat in self.columns))
            
        r = fedit(form, title='Choose Items')
        if r is None: return

        actives = [form[i][0] for i in range(len(form)) if r[i]]
        
        self.setActiveColumns(actives)
        self.formatTable()
        self.updateStatistics()
        
        
    def handleContextMenu(self, pos):      
        self.contextMenu.exec_(QtGui.QCursor().pos())
        
        
class StatisticsToolBar(QtWidgets.QToolBar): 
    
    toggleProfile = Signal()
    toggleDock = Signal()
    selectRoi = Signal(str)
    toggleMask = Signal()
    toggleRoiMask = Signal()
    maskPreset = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)                
        self.initUi()
        
        
    def initUi(self):
        fontHeight = self.fontMetrics().height()
        self.setIconSize(QtCore.QSize(int(fontHeight * 3 / 2), int(fontHeight * 3 / 2)))
 
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'chart_stock.png')), 'Show/Hide profiles', lambda: self.toggleProfile.emit())
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layers_map.png')), "Configure Roi's", lambda: self.selectRoi.emit('custom visibility'))        

        self.masksPresetBtn = MaskPresetButton()
        self.masksPresetBtn.maskPreset.connect(lambda mask: self.maskPreset.emit(mask))
        self.addWidget(self.masksPresetBtn)  
        
        self.maskBtn = QtWidgets.QToolButton(self)
        self.maskBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layer_mask.png')))            
        self.maskBtn.setToolTip('Show/Hide Mask Layer')
        self.maskBtn.clicked.connect(self.toggleShowMask)
        self.addWidget(self.maskBtn)

        self.roiMaskBtn = QtWidgets.QToolButton(self)
        self.roiMaskBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layer_grid.png')))
        self.roiMaskBtn.setCheckable(True)
        self.roiMaskBtn.setToolTip('Show/Hide Roi Pattern')
        self.roiMaskBtn.clicked.connect(self.toggleShowRoiMask)
        self.addWidget(self.roiMaskBtn)        


    def toggleShowMask(self):
        self.toggleMask.emit()


    def setRoiMaskVisible(self, visible):
        if visible:
            self.roiMaskBtn.setChecked(True)
        else:
            self.roiMaskBtn.setChecked(False)


    def toggleShowRoiMask(self):
        self.toggleRoiMask.emit()


class VisibilityToolBar(QtWidgets.QToolBar):

    selectRoi = QtCore.Signal(str)
    addMask = QtCore.Signal()
    editMask = QtCore.Signal()
    showMask = QtCore.Signal(bool)
    showRoiMask = QtCore.Signal(bool)
    removeMask = QtCore.Signal()
    moveItem = QtCore.Signal(str)
    maskPreset = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()
        
    def initUi(self):                
        self.masksPresetBtn = MaskPresetButton()
        self.masksPresetBtn.maskPreset.connect(lambda mask: self.maskPreset.emit(mask))
        self.addWidget(self.masksPresetBtn)         
        
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'add.png')), "Add mask",  lambda: self.addMask.emit())
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'delete.png')), "Remove mask",  lambda: self.removeMask.emit())
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'application_form_edit.png')), "Edit mask",  lambda: self.editMask.emit())
        
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'arrow_up.png')), "Move Up",  lambda: self.moveItem.emit('up'))        
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'arrow_down.png')), "Move Down",   lambda: self.moveItem.emit('down')) 
        
        self.addAction('All', lambda: self.selectRoi.emit('all'))
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'region_of_interest.png')), 'Show Only Roi', lambda: self.selectRoi.emit('show roi only'))
        self.addAction("Hide ROI",  lambda: self.selectRoi.emit('hide roi'))        
        
        self.maskBtn = QtWidgets.QToolButton(self)
        self.maskBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layer_mask.png')))
        #self.maskBtn.setText('Mask Layer')
        self.maskBtn.setCheckable(True)
        
        if self.parent().imgdata.is_layer_visible('mask'):
            self.maskBtn.setChecked(True)
        else:
            self.maskBtn.setChecked(False)
            
        self.maskBtn.setToolTip('Show/Hide Mask Layer')
        self.maskBtn.clicked.connect(self.toggleShowMask)
        self.addWidget(self.maskBtn)      

        self.roiMaskBtn = QtWidgets.QToolButton(self)
        self.roiMaskBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layer_grid.png')))
        #self.roiMaskBtn.setText('Roi Mask')
        self.roiMaskBtn.setCheckable(True)

        if self.parent().imgdata.roi_mask_visible:
            self.roiMaskBtn.setChecked(True)
        else:
            self.roiMaskBtn.setChecked(False)        
        
        self.roiMaskBtn.setToolTip('Show/Hide Roi Pattern')
        self.roiMaskBtn.clicked.connect(self.toggleShowRoiMask)
        self.addWidget(self.roiMaskBtn)
        
    def toggleShowMask(self):
        if self.maskBtn.isChecked():
            self.showMask.emit(True)
        else:
            self.showMask.emit(False)

    def toggleShowRoiMask(self):
        if self.roiMaskBtn.isChecked():
            self.showRoiMask.emit(True)
        else:
            self.showRoiMask.emit(False)            
