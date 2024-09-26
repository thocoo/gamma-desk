from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal

class StatisticsPanel(QtWidgets.QWidget):    
    
    maskSelected = Signal(str)
    
    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()
        
    def initUi(self):        
        self.table = QtWidgets.QTableWidget()        
        
        self.setActiveColumns(["Mean", "Std", "Min", "Max"])
        
        self.table.horizontalHeader().setDefaultSectionSize(20)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.selectionModel().currentRowChanged.connect(self.rowSelected)
        
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setContentsMargins(0,0,0,0)
        self.vbox.setSpacing(0)
        self.setLayout(self.vbox)                       
        self.vbox.addWidget(self.table)
        
        
    def setActiveColumns(self, columns=["Mean", "Std"]):
        self.columns = ["Name"] + columns
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        
    
    @property
    def imviewer(self):
        return self.parent().parent().parent().imviewer
        
        
    def rowSelected(self, index):
        row = index.row()
        maskName = self.table.item(row, 0).text()
        self.maskSelected.emit(maskName)

        
    def updateStatistics(self):    

        funcmap = {
            'Mean': 'mean',
            'Std': 'std',
            'Min': 'min',
            'Max': 'max'}
    
        chanstats = self.imviewer.imgdata.chanstats
        
        valid_stats_names = [name for name, stats in chanstats.items() if stats.is_valid()]
        self.table.setRowCount(len(valid_stats_names))
        
        for i, name in  enumerate(valid_stats_names):
            stats = chanstats[name]
            
            item_name = QtWidgets.QTableWidgetItem(name)            
            R, G, B, A = stats.plot_color.toTuple()
            item_name.setBackground(QtGui.QColor(R, G, B, 128))
            self.table.setItem(i, 0, item_name)
            
            for j, column in enumerate(self.columns[1:]):
            
                value = getattr(stats, funcmap[column])()
                item = QtWidgets.QTableWidgetItem(f'{value:.4g}')                                        
                self.table.setItem(i, 1 + j, item)           
            
            self.table.setRowHeight(i, 20)