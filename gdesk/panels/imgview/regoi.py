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


class RoiConfigDialog(QtWidgets.QDialog): 
    
    def __init__(self, imgdata):    
        super().__init__()
        self.imgdata = imgdata
        self.chanstats = imgdata.chanstats
        self.initUi()
        
        
    def initUi(self):
        self.setWindowTitle('Region of Interest Configuration')                        
        self.setMinimumWidth(640)
        self.setMinimumWidth(640)
                
        self.vbox = QtWidgets.QVBoxLayout()
        self.setLayout(self.vbox)     
        
        self.toolbar = VisibilityToolBar(self)
        self.toolbar.selectRoi.connect(self.selectRoi)
        self.toolbar.moveItem.connect(self.moveItem)
        self.toolbar.addMask.connect(self.addMask)
        self.toolbar.editMask.connect(self.editMask)
        self.toolbar.removeMask.connect(self.removeMask)
        self.toolbar.maskPreset.connect(self.maskPreset)
        self.toolbar.showMask.connect(self.showMask)
        self.toolbar.showRoiMask.connect(self.showRoiMask)
        
        self.vbox.addWidget(self.toolbar)
        self.table = QtWidgets.QTableWidget()       
        self.vbox.addWidget(self.table)
        
        headers = ['Name', 'Active', 'Viewer', 'Profile', 'Levels', 'Dim', 'Slices', 'Mask', 'Valid']
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu) 
        self.table.customContextMenuRequested.connect(self.handleContextMenu)
        
        hbox = QtWidgets.QHBoxLayout()
        self.vbox.addLayout(hbox)
        
        hbox.addStretch(1)
        self.okBtn = QtWidgets.QPushButton('Ok')
        self.okBtn.clicked.connect(self.okPressed)
        hbox.addWidget(self.okBtn)
        
        self.only_valids = False
        self.populateTable()
        self.table.resizeColumnsToContents() 
        
        
    def okPressed(self):
        self.accept()        
        
        
    def populateTable(self):
        chanstats = self.chanstats
        
        if self.only_valids:
            stats_names = [name for name in chanstats.order if chanstats[name].is_valid()]
        else:
            stats_names = chanstats.order
            
        self.table.setRowCount(len(stats_names))        
        self.table.setVerticalHeaderLabels(stats_names)
        
        for i, name in enumerate(stats_names):
            self.table.setRowHeight(i, 20)
            stats = chanstats[name]                              
            
            item_name = QtWidgets.QTableWidgetItem(name)
            R, G, B, A = stats.plot_color.getRgb()
            item_name.setBackground(QtGui.QColor(R, G, B, 128))            
            item_name.setFlags(item_name.flags() ^ Qt.ItemIsEditable) 
            self.table.setItem(i, 0, item_name)                        
      
            statsheck = CheckBox(i, stats.active)
            statsheck.checkedSignal.connect(lambda row, checked: self.changeCheck(row, 2, checked))
            self.table.setCellWidget(i, 1, statsheck)               
            
            visCheck = CheckBox(i, stats.mask_visible)
            visCheck.checkedSignal.connect(lambda row, checked: self.changeCheck(row, 3, checked))
            self.table.setCellWidget(i, 2, visCheck)   
            
            if name in RESERVED_MASK_FULL: visCheck.setEnabled(False)
            if name in RESERVED_MASK_ROI: visCheck.setEnabled(False)

            pltCheck = CheckBox(i, stats.plot_visible)
            pltCheck.checkedSignal.connect(lambda row, checked: self.changeCheck(row, 4, checked))
            self.table.setCellWidget(i, 3, pltCheck) 
            
            histCheck = CheckBox(i, stats.hist_visible)
            histCheck.checkedSignal.connect(lambda row, checked: self.changeCheck(row, 5, checked))
            self.table.setCellWidget(i, 4, histCheck) 
            
            dimCheck = CheckBox(i, stats.dim)
            dimCheck.checkedSignal.connect(lambda row, checked: self.changeCheck(row, 6, checked))
            self.table.setCellWidget(i, 5, dimCheck)             
      
            slices = QtWidgets.QTableWidgetItem(stats.slices_repr())
            slices.setFlags(slices.flags() ^ Qt.ItemIsEditable)      
            self.table.setItem(i, 6, slices)      
            
            bmask_str = QtWidgets.QTableWidgetItem(str(not stats.mask_not_cropped is None))
            self.table.setItem(i, 7, bmask_str)
            
            validCheck = CheckBox(i, stats.is_valid(), read_only=True)
            #validCheck.checkedSignal.connect(lambda row, checked: self.changeCheck(row, 9, checked))
            self.table.setCellWidget(i, 8, validCheck)            
 

    def handleContextMenu(self, pos):      
        
        self.contextMenu = QtWidgets.QMenu('Mask') 
        
        act = QtWidgets.QAction('Modify', self, triggered=self.editMask)
        self.contextMenu.addAction(act)      
        act = QtWidgets.QAction('Remove', self, triggered=self.removeMask)
        self.contextMenu.addAction(act)
        self.contextMenu.exec_(QtGui.QCursor().pos())
        
        
    def maskPreset(self, preset):
        self.imgdata.init_channel_statistics(preset)
        self.populateTable()
        
        
    def showMask(self, visible):
        if visible:
            self.imgdata.show_layer('mask')
        else:
            self.imgdata.hide_layer('mask')


    def showRoiMask(self, visible):
        if visible:
            self.imgdata.show_roi_mask(True)
        else:
            self.imgdata.show_roi_mask(False)

        
    def changeCheck(self, row, column, checked): 
        selection = self.table.selectionModel().selectedRows()        
        rows = [index.row() for index in selection]
        
        if not (len(rows) > 1 and row in rows):
            rows = [row]
        
        for row in rows:
            nameCell = self.table.item(row, 0)
            maskName = nameCell.text()           
            stat = self.chanstats[maskName]
            if column == 2: stat.active = checked                          
            if column == 3: stat.mask_visible = checked                          
            if column == 4: stat.plot_visible = checked                          
            if column == 5: stat.hist_visible = checked                          
            if column == 6: stat.dim = checked                          
            
        self.populateTable()                              
        
        
    def selectRoi(self, preset):
        
        def setMaskStats(name, row, checked):
            item = self.table.cellWidget(row, 1)
            item.setChecked(checked)
            stat = self.chanstats[name]
            stat.active = checked
        
        if preset == 'show roi only':
            
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                name = item.text()
                
                if name.startswith('roi.'):
                    setMaskStats(name, row, True)
                    
                else:
                    setMaskStats(name, row, False)
            
        elif preset == 'hide roi':
            
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                name = item.text()            
                
                if name.startswith('roi.'):
                    setMaskStats(name, row, False)
                    
                else:
                    setMaskStats(name, row, True)
                    
        else:        
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                name = item.text()
                setMaskStats(name, row, True)
                
                
    def addMask(self):                
        self.imgdata.addMaskStatsDialog()        
        self.populateTable()      
        
                
    def moveItem(self, direction):
        selectionModel = self.table.selectionModel()
        selection = selectionModel.selectedRows()
        
        new_positions = []
        
        if direction == 'up':
            for index in selection:
                row = index.row()
                cell = self.table.item(row, 0)
                name = cell.text()
                pos = self.chanstats.get_position(name)
                self.chanstats.move_to_position(name, pos-1)
                new_positions.append(row-1)
            
        elif direction == 'down':
            for index in reversed(selection):
                row = index.row()
                cell = self.table.item(row, 0)
                name = cell.text()
                pos = self.chanstats.get_position(name)
                self.chanstats.move_to_position(name, pos+1)      
                new_positions.append(row+1)

        selectionModel.clearSelection()                
        
        topLeft = selectionModel.model().createIndex(min(new_positions), 0)
        bottomRight = selectionModel.model().createIndex(max(new_positions), 8)
        selection = QtCore.QItemSelection(topLeft, bottomRight)        
        selectionModel.select(selection, QtCore.QItemSelectionModel.Select)
          
        self.populateTable()
        
            
    def editMask(self):
        indices = self.table.selectionModel().selectedRows()
        row = list(indices)[0].row()
        
        maskName = self.table.item(row, 0).text()
  
        if maskName in  RESERVED_MASK_FULL or maskName in RESERVED_MASK_ROI:
            gui.msgbox('You can not change this reserved mask.\nThis is not a user mask.', title='Warning', icon='warn')
            return
            
        self.imgdata.addMaskStatsDialog(maskName)        
        self.populateTable()


    def removeMask(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.chanstats.pop(roi_name)

        self.populateTable()                     
