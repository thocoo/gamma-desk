from pathlib import Path

import numpy as np

from qtpy import QtCore, QtGui, QtWidgets, API_NAME
from qtpy.QtCore import Qt, Signal

from ...dialogs.formlayout import fedit
from ... import config
from .imgdata import get_next_color_tuple

from qtpy.QtCore import Qt, Signal, QUrl
from gdesk import gui


RESPATH = Path(config['respath'])

RESERVED_MASK_FULL = ['K', 'B', 'G', 'Gb', 'Gr', 'R']
RESERVED_MASK_ROI = ['roi.B', 'roi.K', 'roi.G', 'roi.Gb', 'roi.Gr', 'roi.R']

FUNCMAP = {
    'Slices': {'fmt': '{0:s}', 'attr': 'slices_repr'},
    'Mean':   {'fmt': '{0:.6g}', 'attr': 'mean'},
    'Std':    {'fmt': '{0:.6g}', 'attr': 'std'},
    'Min':    {'fmt': '{0:.6g}', 'attr': 'min'},
    'Max':    {'fmt': '{0:.6g}', 'attr': 'max'},
    'N':      {'fmt': '{0:d}', 'attr': 'n'},
    'Sum':    {'fmt': '{0:.6g}', 'attr': 'sum'}}
    
if API_NAME == 'PySide6' and hasattr(QtGui, "QAbstractItemView"):
    NOEDITTRIGGERS = QtGui.QAbstractItemView.NoEditTriggers
else:
    NOEDITTRIGGERS = QtWidgets.QTableWidget.NoEditTriggers


def sort_masks(masks):
    return masks


# def sort_masks(masks):
    
    # def location(mask):
        # if mask in RESERVED_MASK_FULL:
            # return RESERVED_MASK_FULL.index(mask) - 1000
                
        # elif mask in RESERVED_MASK_ROI:
            # return RESERVED_MASK_ROI.index(mask) + 1000
            
        # else:
            # return masks.index(mask)
            
    # return sorted(masks, key=location)

    
def get_last_active(chanstats):
    
    n = len(chanstats)
    
    for i, key in enumerate(chanstats.order[::-1]):    
        if chanstats[key].active:
            return (n - i - 1)
            
    return 0


#https://github.com/yjg30737/pyqt-checkbox-table-widget/blob/main/pyqt_checkbox_table_widget/checkBox.py
class CheckBox(QtWidgets.QWidget):
    checkedSignal = Signal(int, bool)

    def __init__(self, r_idx, flag):
        super().__init__()
        self.__r_idx = r_idx
        self.__initUi(flag)

    def __initUi(self, flag):
        chkBox = QtWidgets.QCheckBox()
        chkBox.setChecked(flag)
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
    showMask = Signal(str)
    hideMask = Signal(str)
    
    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()
        
    def initUi(self):        
        self.table = QtWidgets.QTableWidget()                
        
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
        self.contextMenu.addAction(act)
        
        
    def setActiveColumns(self, columns=["Mean", "Std"]):
        self.columns = ["Name"] + columns
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)        
        
    
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
            
                if stats.active:
                    attr = FUNCMAP[column]['attr']
                    fmt = FUNCMAP[column]['fmt']
                    value = getattr(stats, attr)()                    
                    if isinstance(value, str):
                        text = value
                    else:
                        text = fmt.format(value)
                else:
                    text = ''
                    
                item = QtWidgets.QTableWidgetItem(text)                                        
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
            
                if stats.active:
                    attr = FUNCMAP[column]['attr']
                    fmt = FUNCMAP[column]['fmt']
                    value = getattr(stats, attr)()                    
                    if isinstance(value, str):
                        text = value
                    else:
                        text = fmt.format(value)
                else:
                    text = ''
                    
                item = self.table.item(i, j+1)
                item.setText(text)     
            
            
    def handleHeaderMenu(self, pos):
    
        form = []
        
        for stat in FUNCMAP.keys():
            form.append((stat, stat in self.columns))
            
        r = fedit(form, title='Choose Items')
        if r is None: return

        actives = [form[i][0] for i in range(len(form)) if r[i]]
        
        self.setActiveColumns(actives)
        self.formatTable()
        self.updateStatistics()
        
        
    def handleContextMenu(self, pos):      
        self.contextMenu.exec_(QtGui.QCursor().pos())
        
        
class TitleToolBar(QtWidgets.QToolBar): 
    
    toggleProfile = Signal()
    toggleDock = Signal()
    selectRoi = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)                
        self.initUi()
        
        
    def initUi(self):
        fontHeight = self.fontMetrics().height()
        self.setIconSize(QtCore.QSize(int(fontHeight * 3 / 2), int(fontHeight * 3 / 2)))
 
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'diagramm.png')), 'Show/Hide profiles', lambda: self.toggleProfile.emit())
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layers_map.png')), 'Configure Masks', lambda: self.selectRoi.emit('custom visibility'))
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'application_double.png')), 'Dock/Undock', lambda: self.toggleDock.emit())


class VisibilityToolBar(QtWidgets.QToolBar):

    selectRoi = QtCore.Signal(str)
    addMask = QtCore.Signal()
    editMask = QtCore.Signal()
    removeMask = QtCore.Signal()
    moveItem = QtCore.Signal(str)
    maskPreset = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()
        
    def initUi(self):        
        self.masksSelectMenu = QtWidgets.QMenu('Select Masks')
        self.masksSelectMenu.addAction(QtWidgets.QAction("mono", self, triggered=lambda: self.maskPreset.emit('mono'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color_gradient.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("rgb",  self, triggered=lambda: self.maskPreset.emit('rgb'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("bg",   self, triggered=lambda: self.maskPreset.emit('bg'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_bg.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("gb",   self, triggered=lambda: self.maskPreset.emit('gb'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_gb.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("rg",   self, triggered=lambda: self.maskPreset.emit('rg'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_rg.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("gr",   self, triggered=lambda: self.maskPreset.emit('gr'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_gr.png'))))
        
        self.masksPresetBtn = QtWidgets.QToolButton()
        self.masksPresetBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'select_by_color.png')))      
        self.masksPresetBtn.setToolTip('Select one of the default masks options')
        self.masksPresetBtn.setMenu(self.masksSelectMenu)
        self.masksPresetBtn.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        self.addWidget(self.masksPresetBtn)         
        
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'add.png')), "Add mask",  lambda: self.addMask.emit())
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'delete.png')), "Remove mask",  lambda: self.removeMask.emit())
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'application_form_edit.png')), "Edit mask",  lambda: self.editMask.emit())
        
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'arrow_up.png')), "Move Up",  lambda: self.moveItem.emit('up'))        
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'arrow_down.png')), "Move Down",   lambda: self.moveItem.emit('down')) 
        
        self.addAction('All', lambda: self.selectRoi.emit('all'))
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'region_of_interest.png')), 'Show Only Roi', lambda: self.selectRoi.emit('show roi only'))
        self.addAction("Hide ROI",  lambda: self.selectRoi.emit('hide roi'))                      


class VisibilityDialog(QtWidgets.QDialog): 
    
    def __init__(self, imgdata):    
        super().__init__()
        self.imgdata = imgdata
        self.chanstats = imgdata.chanstats
        self.initUi()
        
        
    def initUi(self):
        self.setWindowTitle('Masks Configuration')                        
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
        
        self.vbox.addWidget(self.toolbar)
        self.table = QtWidgets.QTableWidget()       
        self.vbox.addWidget(self.table)
        
        headers = ['Name', 'Stats', 'Viewer', 'Profile', 'Levels', 'Dim', 'Slices']
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
        
        self.populateTable()
        self.table.resizeColumnsToContents() 
        
        
    def okPressed(self):
        self.accept()        
        
        
    def populateTable(self):
        chanstats = self.chanstats
        valid_stats_names = sort_masks([name for name, stats in chanstats.items() if stats.is_valid()])
        self.table.setRowCount(len(valid_stats_names))        
        self.table.setVerticalHeaderLabels(valid_stats_names)
        
        for i, name in enumerate(valid_stats_names):
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
        bottomRight = selectionModel.model().createIndex(max(new_positions), 6)
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
        
        chanstat = self.chanstats.get(maskName)
        
        form = [('Name',  maskName),
                ('Color',  chanstat.plot_color.name()),
                ('x start', chanstat.slices[1].start),
                ('x stop', chanstat.slices[1].stop),
                ('x step', chanstat.slices[1].step),
                ('y start', chanstat.slices[0].start),
                ('y stop',chanstat.slices[0].stop),
                ('y step', chanstat.slices[0].step)]

        r = fedit(form, title='Change Roi Statistics') 
        if r is None: return        

        newMaskName = r[0]
        color = QtGui.QColor(r[1])
        h_slice = slice(r[2], r[3], r[4])
        v_slice = slice(r[5], r[6], r[7])    

        pos = self.chanstats.get_position(maskName)
        self.chanstats.pop(maskName)
        self.imgdata.addMaskStatistics(newMaskName, (v_slice, h_slice), color)
        self.chanstats.move_to_position(maskName, pos)  
        
        self.populateTable()


    def removeMask(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.chanstats.pop(roi_name)

        self.populateTable()                     
                


        
        
        