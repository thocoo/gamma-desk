from pathlib import Path

import numpy as np

from qtpy import QtCore, QtGui, QtWidgets, API_NAME
from qtpy.QtCore import Qt, Signal

from ...dialogs.formlayout import fedit
from ... import config

from qtpy.QtCore import Qt, Signal, QUrl


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
    
    def location(mask):
        if mask in RESERVED_MASK_FULL:
            return RESERVED_MASK_FULL.index(mask) - 1000
                
        elif mask in RESERVED_MASK_ROI:
            return RESERVED_MASK_ROI.index(mask) + 1000
            
        else:
            return masks.index(mask)
            
    return sorted(masks, key=location)

    
def get_last_active(chanstats):
    
    n = len(chanstats)
    
    for i, key in enumerate(chanstats.order[::-1]):    
        if chanstats[key].active:
            return (n - i - 1)
            
    return 0


#https://github.com/yjg30737/pyqt-checkbox-table-widget/blob/main/pyqt_checkbox_table_widget/checkBox.py
class CheckBox(QtWidgets.QWidget):
    checkedSignal = Signal(int, Qt.CheckState)

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
        self.setFixedWidth(15)

    def __sendCheckedSignal(self, flag):
        flag = Qt.CheckState(flag)
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
        self.table.cellClicked.connect(self.cellClicked)
        self.table.customContextMenuRequested.connect(self.handleContextMenu)        
        
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setContentsMargins(0,0,0,0)
        self.vbox.setSpacing(0)
        self.setLayout(self.vbox)                       
        self.vbox.addWidget(self.table)
        
        self.contextMenu = QtWidgets.QMenu('Mask')
        #dataSplitMenu.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'select_by_color.png')))        
        
        act = QtWidgets.QAction('Activate', self, triggered=self.activateSelectedStatistics)
        self.contextMenu.addAction(act)
        act = QtWidgets.QAction('Deactivate', self, triggered=self.deactivateSelectedStatistics)
        self.contextMenu.addAction(act)
        act = QtWidgets.QAction('Select', self, triggered=self.setImviewSelection)
        self.contextMenu.addAction(act)
        act = QtWidgets.QAction('Modify', self, triggered=self.modifyMask)
        self.contextMenu.addAction(act)        
        act = QtWidgets.QAction('Remove', self, triggered=self.removeSelectedStatistics)
        self.contextMenu.addAction(act)

        self.showInActives = True
        
        
    def setActiveColumns(self, columns=["Mean", "Std"]):
        self.columns = ["Name", "V", "P", "H"] + columns
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        
        self.table.setColumnWidth(1, 20)
        self.table.setColumnWidth(2, 20)
        self.table.setColumnWidth(3, 20)
        
    
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
                            
            
    def modifyMask(self, row=None, column=None):
        
        if row is None and column is None:
            indices = self.table.selectionModel().selectedRows()
            row = list(indices)[0].row()
        
        maskName = self.table.item(row, 0).text()
        
        chanstat = self.imviewer.imgdata.chanstats.get(maskName)
        
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

        self.imviewer.imgdata.chanstats.pop(maskName)
        self.imviewer.imgdata.addMaskStatistics(newMaskName, (v_slice, h_slice), color)        
        self.updateStatistics()        

        
    def updateStatistics(self):    
    
        chanstats = self.imviewer.imgdata.chanstats
        
        if self.showInActives:
            valid_stats_names = [name for name, stats in chanstats.items() if stats.is_valid()]
        else:
            valid_stats_names = [name for name, stats in chanstats.items() if stats.is_valid() and stats.active]
            
        self.table.setRowCount(len(valid_stats_names))
        
        
        
        for i, name in enumerate(sort_masks(valid_stats_names)):
            stats = chanstats[name]       
            
            item_name = QtWidgets.QTableWidgetItem(name)
            R, G, B, A = stats.plot_color.getRgb()
            item_name.setBackground(QtGui.QColor(R, G, B, 128))
            item_name.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item_name.setCheckState(QtCore.Qt.Checked if stats.active else QtCore.Qt.Unchecked)
            
            self.table.setItem(i, 0, item_name)
            
            visCheck = CheckBox(i, stats.mask_visible)
            visCheck.checkedSignal.connect(self.setMaskView)
            self.table.setCellWidget(i, 1, visCheck)   
            
            if name in RESERVED_MASK_FULL: visCheck.setEnabled(False)

            pltCheck = CheckBox(i, stats.plot_visible)
            pltCheck.checkedSignal.connect(self.setMaskPlot)
            self.table.setCellWidget(i, 2, pltCheck) 
            
            histCheck = CheckBox(i, stats.hist_visible)
            histCheck.checkedSignal.connect(self.setMaskHist)
            self.table.setCellWidget(i, 3, histCheck)             
                        
            for j, column in enumerate(self.columns[4:]):
            
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
                self.table.setItem(i, 4 + j, item)
            
            self.table.setRowHeight(i, 20)
            
            
    def cellClicked(self, row, column):
        if column == 0:
        
            selection = self.table.selectionModel().selectedRows()            
            states = {}            
            
            nameCell = self.table.item(row, 0)
            new_state = nameCell.checkState() == Qt.Checked
            clickedMask = nameCell.text()
            
            if len(selection) == 0:        
                states[clickedMask] = new_state

            else:            
                for index in selection:
                    nameCell = self.table.item(index.row(), 0)
                    mask = nameCell.text()
                    states[mask] = new_state
                    
                if not clickedMask in states:
                    # The clicked row is not part of the selection
                    # Ignore the selection and give the click the priority
                    states = {clickedMask: new_state}
                
            do_update = False
            
            for mask, new_state in states.items():        
                if new_state != self.imviewer.imgdata.chanstats[mask].active:                 
                    chanstats = self.imviewer.imgdata.chanstats[mask]
                    chanstats.active = new_state
                    do_update = True
                    
            if do_update:
                self.activesChanged.emit()                
                
    def setMaskView(self, row, checked):
        
        nameCell = self.table.item(row, 0)
        maskName = nameCell.text()   

        if maskName in RESERVED_MASK_FULL: return
        
        stat = self.imviewer.imgdata.chanstats[maskName]
        stat.mask_visible = checked          
        self.activesChanged.emit()   
        
        # if checked:
            # self.showMask.emit(maskName)        
            
        # else:
            # self.hideMask.emit(maskName)
            
            
    def setMaskPlot(self, row, checked):
        nameCell = self.table.item(row, 0)
        maskName = nameCell.text()          
        stat = self.imviewer.imgdata.chanstats[maskName]
        stat.plot_visible = checked        
        self.activesChanged.emit()
                
        
    def setMaskHist(self, row, checked):
        nameCell = self.table.item(row, 0)
        maskName = nameCell.text()          
        stat = self.imviewer.imgdata.chanstats[maskName]
        stat.hist_visible = checked        
        self.activesChanged.emit()        
            
            
    def handleHeaderMenu(self, pos):
    
        form = []
        
        for stat in FUNCMAP.keys():
            form.append((stat, stat in self.columns))
            
        r = fedit(form, title='Choose Items')
        if r is None: return

        actives = [form[i][0] for i in range(len(form)) if r[i]]
        
        self.setActiveColumns(actives)
        self.updateStatistics()
        
        
    def handleContextMenu(self, pos):      
        self.contextMenu.exec_(QtGui.QCursor().pos())


    def activateSelectedStatistics(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.imviewer.imgdata.chanstats[roi_name].active = True
            
        self.updateStatistics()
        
        
    def deactivateSelectedStatistics(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.imviewer.imgdata.chanstats[roi_name].active = False
            
        self.updateStatistics()        
        
        
    def toggleShowInactives(self):
        self.showInActives = not self.showInActives
        self.updateStatistics()
        
        
    def removeSelectedStatistics(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.imviewer.imgdata.chanstats.pop(roi_name)
            
        self.updateStatistics()
                        
        
        
class TitleToolBar(QtWidgets.QWidget): 
    
    toggleProfile = Signal()
    showHideInactives = Signal()
    toggleDock = Signal()
    selectMasks = Signal(str)
    selectRoi = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)        
        
        self.hbox = QtWidgets.QHBoxLayout()
        self.hbox.setContentsMargins(0,0,0,0)
        self.hbox.setSpacing(0)
        self.setLayout(self.hbox)       
        
        self.profBtn = QtWidgets.QPushButton(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'diagramm.png')), None, self)
        self.profBtn.setToolTip('Show/Hide row and column profiles')
        # self.profBtn.setFixedHeight(20)
        # self.profBtn.setFixedWidth(20)
        self.profBtn.clicked.connect(lambda: self.toggleProfile.emit())           
        self.hbox.addWidget(self.profBtn)
                
        self.hbox.addStretch(1)
        self.hbox.addWidget(QtWidgets.QLabel('Masks'))
        self.hbox.addStretch(1)
        
        self.roiSelectMenu = QtWidgets.QMenu('Show Roi')
        self.roiSelectMenu.addAction(QtWidgets.QAction("All", self, triggered=lambda: self.selectRoi.emit('all')))
        self.roiSelectMenu.addAction(QtWidgets.QAction("Show Roi only",  self, triggered=lambda: self.selectRoi.emit('show roi only'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'region_of_interest.png'))))
        self.roiSelectMenu.addAction(QtWidgets.QAction("Hide ROI",   self, triggered=lambda: self.selectRoi.emit('hide roi')))        
        
        self.roiSelectBtn = QtWidgets.QToolButton()
        self.roiSelectBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'eye.png')))      
        self.roiSelectBtn.setToolTip('Show/Hide Roi')
        self.roiSelectBtn.setMenu(self.roiSelectMenu)
        self.roiSelectBtn.setPopupMode(QtWidgets.QToolButton.InstantPopup)          
        
        self.hbox.addWidget(self.roiSelectBtn)
        
        self.masksSelectMenu = QtWidgets.QMenu('Select Masks')
        #self.masksSelectMenu.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'select_by_color.png')))      
        self.masksSelectMenu.addAction(QtWidgets.QAction("mono", self, triggered=lambda: self.selectMasks.emit('mono'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color_gradient.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("rgb",  self, triggered=lambda: self.selectMasks.emit('rgb'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("bg",   self, triggered=lambda: self.selectMasks.emit('bg'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_bg.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("gb",   self, triggered=lambda: self.selectMasks.emit('gb'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_gb.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("rg",   self, triggered=lambda: self.selectMasks.emit('rg'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_rg.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("gr",   self, triggered=lambda: self.selectMasks.emit('gr'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_gr.png'))))
        
        self.masksSelectBtn = QtWidgets.QToolButton()
        self.masksSelectBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'select_by_color.png')))      
        self.masksSelectBtn.setToolTip('Select one of the default masks options')
        self.masksSelectBtn.setMenu(self.masksSelectMenu)
        self.masksSelectBtn.setPopupMode(QtWidgets.QToolButton.InstantPopup)          
        
        self.hbox.addWidget(self.masksSelectBtn)        
        
        self.showHideInactivesBtn = QtWidgets.QPushButton(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'check_boxes.png')), None, self)
        self.showHideInactivesBtn.setToolTip("Show/Hide Inactive Roi's")
        # self.showHideInactiveBtn.setFixedHeight(20)
        # self.showHideInactiveBtn.setFixedWidth(20)
        self.showHideInactivesBtn.clicked.connect(lambda: self.showHideInactives.emit())           
        self.hbox.addWidget(self.showHideInactivesBtn)                
        
        self.showHideInactivesBtn = QtWidgets.QPushButton(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'application_double.png')), None, self)
        self.showHideInactivesBtn.setToolTip("Dock/Undock")
        # self.showHideInactiveBtn.setFixedHeight(20)
        # self.showHideInactiveBtn.setFixedWidth(20)
        self.showHideInactivesBtn.clicked.connect(lambda: self.toggleDock.emit())           
        self.hbox.addWidget(self.showHideInactivesBtn)
