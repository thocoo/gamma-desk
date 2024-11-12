from pathlib import Path

import numpy as np

from qtpy import QtCore, QtGui, QtWidgets, API_NAME
from qtpy.QtCore import Qt, Signal

from ...dialogs.formlayout import fedit
from ... import config

from qtpy.QtCore import Qt, Signal, QUrl


RESPATH = Path(config['respath'])

PREFERED_MASK_ORDER = ['K', 'B', 'G', 'Gb', 'Gr', 'R', 'roi.B', 'roi.K', 'roi.G', 'roi.Gb', 'roi.Gr', 'roi.R']

FUNCMAP = {
    'Slices': {'fmt': '{0:s}', 'attr': 'slices_repr'},
    'Mean':   {'fmt': '{0:.4g}', 'attr': 'mean'},
    'Std':    {'fmt': '{0:.4g}', 'attr': 'std'},
    'Min':    {'fmt': '{0:.4g}', 'attr': 'min'},
    'Max':    {'fmt': '{0:.4g}', 'attr': 'max'},
    'N':      {'fmt': '{0:d}', 'attr': 'n'},
    'Sum':    {'fmt': '{0:.4g}', 'attr': 'sum'}}
    
if API_NAME == 'PySide6' and hasattr(QtGui, "QAbstractItemView"):
    NOEDITTRIGGERS = QtGui.QAbstractItemView.NoEditTriggers
else:
    NOEDITTRIGGERS = QtWidgets.QTableWidget.NoEditTriggers


def sort_masks(masks):
    
    def location(mask):
        try:
            return PREFERED_MASK_ORDER.index(mask)        
            
        except ValueError:
            return -1
            
    return sorted(masks, key=location)

    
def get_last_active(chanstats):
    
    n = len(chanstats)
    
    for i, key in enumerate(chanstats.order[::-1]):    
        if chanstats[key].active:
            return (n - i - 1)
            
    return 0            
    

class StatisticsPanel(QtWidgets.QWidget):    
    
    maskSelected = Signal(str)
    activesChanged = Signal()
    showSelection = Signal(str)
    
    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()
        
    def initUi(self):        
        self.table = QtWidgets.QTableWidget()                
        
        headers = self.table.horizontalHeader()
        headers.setContextMenuPolicy(Qt.CustomContextMenu)
        headers.customContextMenuRequested.connect(self.handleHeaderMenu)        
        
        self.setActiveColumns(["Mean", "Std", "Min", "Max"])
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)               
        self.table.setEditTriggers(NOEDITTRIGGERS)
        
        self.table.horizontalHeader().setDefaultSectionSize(20)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.selectionModel().currentRowChanged.connect(self.rowSelected)
        self.table.selectionModel().selectionChanged.connect(self.selectionChanged)
        self.table.cellDoubleClicked.connect(self.showCurrentSelection)
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
        act = QtWidgets.QAction('Show Selection', self, triggered=self.showCurrentSelection)
        self.contextMenu.addAction(act)
        act = QtWidgets.QAction('Modify', self, triggered=self.modifyMask)
        self.contextMenu.addAction(act)        
        act = QtWidgets.QAction('Remove', self, triggered=self.removeSelectedStatistics)
        self.contextMenu.addAction(act)

        self.showInActives = True
        
        
    def setActiveColumns(self, columns=["Mean", "Std"]):
        self.columns = ["Name"] + columns
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        
    
    @property
    def imviewer(self):
        return self.parent().parent().parent().imviewer
        
        
    def rowSelected(self, index):
        row = index.row()
        selectedRow = self.table.item(row, 0)
        if selectedRow is None: return
        maskName = selectedRow.text()
        self.maskSelected.emit(maskName)
        
        
    def showCurrentSelection(self):
        selection = self.table.selectionModel().selectedRows()
        
        for index in selection:
            nameCell = self.table.item(index.row(), 0)
            roi_name = nameCell.text()
            self.showSelection.emit(roi_name)
            break
        
        
    def selectionChanged(self, selected, deselected):
        if selected.count() == 0:
            self.maskSelected.emit('')
            
            
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
        
        for i, name in enumerate(valid_stats_names):
            stats = chanstats[name]            
            item_name = QtWidgets.QTableWidgetItem(name)            
            R, G, B, A = stats.plot_color.toTuple()
            
            item_name.setBackground(QtGui.QColor(R, G, B, 128))
            item_name.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item_name.setCheckState(QtCore.Qt.Checked if stats.active else QtCore.Qt.Unchecked)
            
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
            
            
    def cellClicked(self, row, column):
        if column != 0: return
        
        selection = self.table.selectionModel().selectedRows()
        
        states = {}
        
        print(f'Selection lenght: {len(selection)}')
        
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
        self.roiSelectMenu.addAction(QtWidgets.QAction("All", self, triggered=lambda: self.selectRoi.emit('all'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'region_of_interest.png'))))
        self.roiSelectMenu.addAction(QtWidgets.QAction("Show Roi only",  self, triggered=lambda: self.selectRoi.emit('show roi only'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'region_of_interest.png'))))
        self.roiSelectMenu.addAction(QtWidgets.QAction("Hide ROI",   self, triggered=lambda: self.selectRoi.emit('hide roi'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'region_of_interest.png'))))        
        
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