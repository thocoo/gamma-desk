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
    

class StatisticsItemDialog(QtWidgets.QDialog):

    def __init__(self, items, active_items=None, parent=None):
        super().__init__(parent)
        self.items = items
        self.active_items = active_items or []
        self.initUi()

    def initUi(self):
        self.setWindowTitle('Choose Statistics')
        self.resize(700, 420)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['', 'Name', 'Label', 'Doc', 'Type'])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 20)

        for row, (name, props) in enumerate(self.items):
            self.table.insertRow(row)

            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(name in self.active_items)
            self.table.setCellWidget(row, 0, checkbox)

            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(name)))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(props.get('label', name))))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(props.get('doc', ''))))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(str(props.get('rtype', ''))))

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 20)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.button_box)

    def selected_items(self):
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox is not None and checkbox.isChecked():
                name_item = self.table.item(row, 1)
                if name_item is not None:
                    selected.append(name_item.text())
              
        # keep the previous order, additional items to the end
        selected = sorted(selected, key= lambda item: self.active_items.index(item) if item in self.active_items else 1000)
        
        return selected


class Statistics(QtWidgets.QWidget):    
    
    maskSelected = Signal(str)
    activesChanged = Signal()
    
    setSelection = Signal(str)
    showBmask = Signal(str)
    hideMask = Signal(str)

    
    def __init__(self, imviewer=None):
        self._imviewer = imviewer
        super().__init__() 
        
        self.initUi()
        self.feed_rate = 1
        self.feed_counter = 0        
        self.ref_metric = None
        self.columns = ["Name"]

        
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
        if self._imviewer is not None:
            return self._imviewer
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


    def fitContent(self):
        self.table.resizeColumnsToContents()            


    def formatTable(self):    
    
        chanstats = self.imviewer.imgdata.chanstats        
        valid_stats_names = [name for name, stats in chanstats.items() if stats.is_valid() and stats.active] 
        
        if len(valid_stats_names) > 1: 
            valid_stats_names = valid_stats_names + ['avg']
            
        if not self.ref_metric is None:
            valid_stats_names = valid_stats_names + [f'{self.ref_metric}/xx']            
        
        self.table.setRowCount(len(valid_stats_names))
        
        for i, name in enumerate(valid_stats_names):
            item_label = QtWidgets.QTableWidgetItem(name)
            
            if name in ['avg', f'{self.ref_metric}/xx']:
                pass
                
            else:
                stats = chanstats[name]                               
                R, G, B, A = stats.plot_color.getRgb()            
                item_label.setBackground(QtGui.QColor(R, G, B, 128))                                        
                
            self.table.setItem(i, 0, item_label)
                        
            for j, column in enumerate(self.columns[1:]):
                props = stats.report_items[column]
                
                if props.get('rtype') == np.ndarray and not name in ['avg', f'{self.ref_metric}/xx']:
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
            
            for agg in stats.aggs:
                agg.clear_buffs()
            
            for j, column in enumerate(self.columns[1:]):
                item = self.table.item(i, j+1)
                if not isinstance(item, ImageItem):
                    item.setText('')

        
    def updateStatistics(self):
        
        if not self.isVisible(): return
        
        self.feed_counter += 1
        
        if self.feed_counter >= self.feed_rate:
            self.feed_counter = 0
            
        else:
            return
            
    
        chanstats = self.imviewer.imgdata.chanstats 

        colindnames = list(enumerate(self.columns[1:]))
        
        if not self.ref_metric is None:
            # Make sure the reference metric is calculated first
            for i, (col, name) in enumerate(colindnames):
                if name == self.ref_metric:                     
                    poped = colindnames.pop(i)
                    colindnames = [poped] + colindnames
                    break

        ref_value = None
        
        for j, column in colindnames:
                     
            values = []
            
            for i in range(self.table.rowCount()):
                item = self.table.item(i, 0)                
                name = item.text()                                
                
                if name == 'avg':
                    value = np.mean(values)
                    text = f'{value:.3g}'
                    item = self.table.item(i, j+1)
                    item.setText(text)
                    
                    if column == self.ref_metric:
                        ref_value = value
                    
                    continue
                    
                elif name == f'{self.ref_metric}/xx':
                    if not ref_value is None and not value is None:
                        item = self.table.item(i, j+1)
                        
                        if value == 0:
                            item.setText('inf')
                            
                        else:
                            ratio = ref_value / value                        
                            text = f'{ratio:.3g}'
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
                        value = None
                        
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

                    if column == self.ref_metric:
                        ref_value = value                                

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
        if not chanstats:
            return

        report_items = {}
        for imgstat in chanstats.values():
            for name, props in imgstat.report_items.items():
                if name not in report_items:
                    report_items[name] = props

        active_items = self.columns[1:]
        items = sorted(report_items.items(), key=lambda pair: str(pair[0]).upper())

        dialog = StatisticsItemDialog(items, active_items, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        selected = dialog.selected_items()
        self.setActiveColumns(selected)
        self.clearStatistics()
        
        
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
        self.toolbar.connectButtons(self.statistics)                
        self.toolbar.configureRois.connect(self.configureRois)
        
        self.addToolBar(self.toolbar)
        
        self.fileMenu = CheckMenu("File", self.menuBar())
        self.addMenuItem(self.fileMenu, "Close", self.close_panel,
            statusTip = "Close this panel",
            icon = 'cross.png')                
            
        self.editMenu = CheckMenu("Edit", self.menuBar())
        
        self.addMenuItem(self.editMenu, "Copy", self.statistics.copyTableToClipboard,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'page_copy.png')))
        
        self.addMenuItem(self.editMenu, "Fit Content", self.statistics.fitContent,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'page_width.png')))
        
        self.statsMenu = CheckMenu("Statistics", self.menuBar())
        
        self.addMenuItem(self.statsMenu, "Clear", self.statistics.clearStatistics,
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cell_clear.png')))            
            
        self.addMenuItem(self.statsMenu, "Choose Statistics", self.statistics.chooseStatistics,            
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'calculator.png')))
                        
        self.addMenuItem(self.statsMenu, "Image Feed Rate", self.setImageFeedRate)            
            
        self.addBaseMenu(['image'])
        self.statusBar().hide()                
        
        
    def configureRois(self):
        self.bindedPanel('image').imgprof.selectRoi('custom visibility')
        
        
    def updateStatistics(self):
        self.statistics.updateStatistics()
        
        
    def setActiveColumns(self, actives):
        self.statistics.setActiveColumns(actives)
        
        
    def setImageFeedRate(self):
        rate = int(gui.dialog.getstring('Set Image Feed Rate'))
        self.statistics.feed_rate = rate        
        
        
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
    refresh = Signal()
    fitContent = Signal()
    clearStats = Signal()
    configureRois = Signal()
    chooseStatistics = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.addAction(
            QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'update.png')),
            'Refresh',
            self.refresh.emit)        
        
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


    def connectButtons(self, statistics):
        self.refresh.connect(statistics.updateStatistics)
        self.copy.connect(statistics.copyTableToClipboard)
        self.fitContent.connect(statistics.fitContent)
        self.clearStats.connect(statistics.clearStatistics)
        self.chooseStatistics.connect(statistics.chooseStatistics)  