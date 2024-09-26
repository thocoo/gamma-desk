from qtpy import QtCore, QtGui, QtWidgets

class StatisticsPanel(QtWidgets.QWidget):        
    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()
        
    def initUi(self):        
        self.table = QtWidgets.QTableWidget()        
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Means", "Std"])        
        self.table.horizontalHeader().setDefaultSectionSize(20)
        self.table.verticalHeader().hide()
        
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setContentsMargins(0,0,0,0)
        self.vbox.setSpacing(0)
        self.setLayout(self.vbox)                       
        self.vbox.addWidget(self.table)

    
    @property
    def imviewer(self):
        return self.parent().parent().parent().imviewer

        
    def updateStatistics(self):        
    
        chanstats = self.imviewer.imgdata.chanstats
        
        self.table.setRowCount(len(chanstats))
        
        for i, (name, stats) in  enumerate(chanstats.items()):
            if not stats.is_valid(): continue
            
            item_name = QtWidgets.QTableWidgetItem(name)            
            R, G, B, A = stats.plot_color.toTuple()
            item_name.setBackground(QtGui.QColor(R, G, B, 128))
            item_m = QtWidgets.QTableWidgetItem(f'{stats.mean():.4g}')
            item_s = QtWidgets.QTableWidgetItem(f'{stats.std():.4g}')
    
            self.table.setItem(i, 0, item_name)
            self.table.setItem(i, 1, item_m)
            self.table.setItem(i, 2, item_s)
            self.table.setRowHeight(i, 20)