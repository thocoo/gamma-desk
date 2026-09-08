from pathlib import Path

import numpy as np

from qtpy import QtCore, QtGui, QtWidgets, API_NAME

from qtpy.QtCore import Qt
from qtpy.QtGui import QWindow
from qtpy.QtCore import Qt, Signal

from gdesk import gui
from ..base import BasePanel, CheckMenu
from ... import config
from ...dialogs.formlayout import fedit

RESPATH = Path(config['respath'])

if API_NAME == 'PySide6' and hasattr(QtGui, "QAbstractItemView"):
    NOEDITTRIGGERS = QtGui.QAbstractItemView.NoEditTriggers
else:
    NOEDITTRIGGERS = QtWidgets.QTableWidget.NoEditTriggers
    
    
class ImageItem(QtWidgets.QTableWidgetItem):
    
    def __init__(self, panid=0):
        super().__init__()
        self.panid = panid
        self.setText(f'image#{self.panid}')
    

class Statistics(QtWidgets.QWidget):    
    
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
        table_font = self.table.font()
        table_font.setFamily('Consolas')
        self.table.setFont(table_font)
        self.table.viewport().installEventFilter(self)
        
        headers = self.table.horizontalHeader()
        headers.setContextMenuPolicy(Qt.CustomContextMenu)
        headers.customContextMenuRequested.connect(self.handleHeaderMenu)        
        headers.setMinimumSectionSize(20)        
        headers.setSectionsMovable(True)        
        
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

        if obj is self.table.viewport() and event.type() == QtCore.QEvent.Wheel:
            if event.modifiers() & Qt.ControlModifier:
                font = self.table.font()
                delta = event.angleDelta().y()
                point_size = max(1, font.pointSize() + (1 if delta > 0 else -1))
                font.setPointSize(point_size)
                self.table.setFont(font)
                self.updateRowHeights()
                return True

        return super().eventFilter(obj, event)


    def updateRowHeights(self):
        row_height = QtGui.QFontMetrics(self.table.font()).lineSpacing() + 4
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, row_height)
        
        
    def setActiveColumns(self, columns=["Mean", "Std"]):
        self.columns = ["Name"] + columns
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)        
        self.formatTable()
        self.updateStatistics()        


    def copyTableToClipboard(self):
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            selection = [self.table.model().index(row, 0) for row in range(self.table.rowCount())]
        
        header = self.table.horizontalHeader()
        columnOrder = [header.logicalIndex(visual) for visual in range(self.table.columnCount())]
        
        text = '\t'.join(self.columns[col] for col in columnOrder) + '\n'
        
        for index in selection:
            row = index.row()
            rowText = []
            for col in columnOrder:
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
        panel = self.parent().bindedPanel('image')        
        return panel.imviewer
        
        
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
        
        if len(valid_stats_names) > 1: 
            valid_stats_names = valid_stats_names + ['avg']
        
        self.table.setRowCount(len(valid_stats_names))
        
        for i, name in enumerate(valid_stats_names):
            item_label = QtWidgets.QTableWidgetItem(name)
            
            if name == 'avg':
                pass
                
            else:
                stats = chanstats[name]                               
                R, G, B, A = stats.plot_color.getRgb()            
                item_label.setBackground(QtGui.QColor(R, G, B, 128))            
                
            self.table.setItem(i, 0, item_label)            
                        
            for j, column in enumerate(self.columns[1:]):
                props = stats.report_items[column]
                
                if props.get('rtype') == np.ndarray and not name == 'avg':
                    panid = gui.img.new()
                    
                    fmt = props.get('fmt', {})
                    
                    if 'colormap' in fmt:
                        gui.qapp.panels['image'][panid].colormap = fmt['colormap']
                    
                    item = ImageItem(panid)
                    self.table.setItem(i, 1 + j, item)    
                
                else:
                    item = QtWidgets.QTableWidgetItem('')
                    
                self.table.setItem(i, 1 + j, item)
            
        self.updateRowHeights()
        self.table.resizeColumnsToContents()
        
        
    def clearStatistics(self):    
    
        chanstats = self.imviewer.imgdata.chanstats        
       
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)                
            name = item.text()                                
                
            if name == 'avg':
                continue
                
            if not name in chanstats: continue
                
            stats = chanstats[name]          
            stats.agg.clear_buffs()
            
            for j, column in enumerate(self.columns[1:]):
                item = self.table.item(i, j+1)
                if not isinstance(item, ImageItem):
                    item.setText('')

        
    def updateStatistics(self):    
    
        chanstats = self.imviewer.imgdata.chanstats        
        
        for j, column in enumerate(self.columns[1:]):
                     
            values = []
            
            for i in range(self.table.rowCount()):
                item = self.table.item(i, 0)                
                name = item.text()                                
                
                if name == 'avg':
                    value = np.mean(values)
                    text = f'{value:.3g}'
                    item = self.table.item(i, j+1)
                    item.setText(text)
                    continue
                
                if not name in chanstats: continue
                if not chanstats[name].is_valid(): continue
                
                stats = chanstats[name]                                     
            
                if stats.active and column in stats.report_items:
                    item = self.table.item(i, j+1)                    
                    value = stats.report_items[column]['func']()                    
                    
                    fmt = stats.report_items[column]['fmt']
                    
                    if isinstance(item, ImageItem):                        
                        panid = item.panid
                        
                        current = gui.img.selected()
                        gui.show(value, select=[panid])
                        
                        gain = fmt.get('gain')
                       
                        if gain is None:
                            pass
                        
                        elif gain == 'min-max':
                            gui.qapp.panels['image'][panid].gainToMinMax()
                            
                        elif gain.startswith('sigma'):
                            factor = int(gain[5:])
                            gui.qapp.panels['image'][panid].gainToSigma(factor)
                        
                        gui.img.select(current)
                        continue
                        
                    else:         
                        if value is None:
                            values.append(np.nan)
                            continue
                    
                        else:
                            values.append(value)                                        

                    if isinstance(value, str):
                        text = value
                    else:
                        text = fmt.format(value)                        
                        
                else:
                    text = ''
                    
                item = self.table.item(i, j+1)
                item.setText(text)
            
            
    def handleHeaderMenu(self, pos):
        self.chooseStatistics()        
        
        
    def chooseStatistics(self):
        chanstats = self.imviewer.imgdata.chanstats  
        
        all_items = set()
        
        for channel_name, imgstat in chanstats.items():
            all_items = all_items.union(set(imgstat.report_items.keys()))        
    
        form = []
        
        for stat in sorted(all_items):
            form.append((stat, stat in self.columns))
            
        r = fedit(form, title='Choose Items')
        if r is None: return
        
        actives = [form[i][0] for i in range(len(form)) if r[i]]        
        self.setActiveColumns(actives)
        
        
    def handleContextMenu(self, pos):      
        self.contextMenu.exec_(QtGui.QCursor().pos())


class StatisticsPanel(BasePanel):
    
    panelCategory = 'statistics'
    panelShortName = 'basic'
    classIconFile = str(RESPATH / 'icons' / 'px16' / 'table_sum.png')

    def __init__(self, parent, panid):
        super().__init__(parent, panid, type(self).panelCategory)

        self.statistics = Statistics()                
        self.setCentralWidget(self.statistics)        

        self.toolbar = StatisticsToolBar(self)
        self.toolbar.copy.connect(self.copyContent)
        self.toolbar.fitContent.connect(self.fitContent)
        self.toolbar.clearStats.connect(self.clearStatistics)
        self.toolbar.chooseStatistics.connect(self.chooseStatistics)
        self.toolbar.configureRois.connect(self.configureRois)
        
        self.addToolBar(self.toolbar)
        
        self.fileMenu = CheckMenu("File", self.menuBar())
        self.addMenuItem(self.fileMenu, "Close", self.close_panel,
            statusTip = "Close this panel",
            icon = 'cross.png')                
            
        self.editMenu = CheckMenu("Edit", self.menuBar())
        
        self.addMenuItem(self.editMenu, "Copy", self.copyContent,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'page_copy.png')))
        
        self.addMenuItem(self.editMenu, "Fit Content", self.fitContent,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'page_width.png')))
        
        self.statsMenu = CheckMenu("Statistics", self.menuBar())
        
        self.addMenuItem(self.statsMenu, "Clear", self.clearStatistics,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cell_clear.png')))            
            
        self.addMenuItem(self.statsMenu, "Choose Statistics", self.chooseStatistics,            
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'calculator.png')))
            
        self.addBaseMenu(['image'])
        self.statusBar().hide()
        
    
    def copyContent(self):    
        self.statistics.copyTableToClipboard()
        
        
    def fitContent(self):
        self.statistics.table.resizeColumnsToContents()
        
        
    def clearStatistics(self):
        self.statistics.clearStatistics()
        
        
    def chooseStatistics(self):
        self.statistics.chooseStatistics()
        
        
    def configureRois(self):
        self.bindedPanel('image').imgprof.selectRoi('custom visibility')
        
        
    def updateStatistics(self):
        self.statistics.updateStatistics()
        
        
    def setActiveColumns(self, actives):
        self.statistics.setActiveColumns(actives)
        
        
    # def addBindingTo(self, category, panid):
        # targetPanel = super().addBindingTo(category, panid)
        # if targetPanel is None: return None
        # return targetPanel
        
        
    # def removeBindingTo(self, category, panid):
        # targetPanel = super().removeBindingTo(category, panid)
        # if targetPanel is None: return None
        # return targetPanel           


class StatisticsToolBar(QtWidgets.QToolBar):

    copy = Signal()
    fitContent = Signal()
    clearStats = Signal()
    configureRois = Signal()
    chooseStatistics = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layers_map.png')),
            "Configure Roi's",
            self.configureRois.emit,
        )  
        
        self.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'page_copy.png')),
            'Copy',
            self.copy.emit,
        )

        self.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'page_width.png')),
            'Fit Content',
            self.fitContent.emit,
        )
        
        self.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cell_clear.png')),
            'Clear',
            self.clearStats.emit,
        )             

        self.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'calculator.png')),
            "Choose Statstics",
            self.chooseStatistics.emit,
        )         

