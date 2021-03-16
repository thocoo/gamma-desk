from qtpy import QtCore, QtGui, QtWidgets

class GridSplitter(QtWidgets.QGridLayout):
    
    layoutChanged = QtCore.Signal()
    
    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setSpacing(0)
        self.setContentsMargins(0,0,0,0)
        self.splitters = []
        
    def addWidget(self, widget, row, col, rowspan=1, colspan=1):        
        super().addWidget(widget, row*2, col*2, rowspan*2-1, colspan*2-1)
        
        if (self.itemAtPosition(row*2-1, col*2) == None) and (row > 0):
            splitter = GridSeperator(self.parent(), QtCore.Qt.Vertical)
            splitter.attachGridSplitter(self, row-1, row)
            self.splitters.append(splitter)
            super().addWidget(splitter, row*2-1, col*2)
            
        if (self.itemAtPosition(row*2, col*2-1) == None) and (col > 0):
            splitter = GridSeperator(self.parent(), QtCore.Qt.Horizontal)
            splitter.attachGridSplitter(self, col-1, col)
            self.splitters.append(splitter)
            super().addWidget(splitter, row*2, col*2-1)
        
    def getRowStretches(self):
        """get the row streches from all rows, skip the row splitters"""
        stretches = []
        for i in range(0, self.rowCount(), 2):
            stretches.append(self.cellRect(i, 0).height())
        return stretches
        
    def setRowStretches(self, stretches):
        for (i, stretch) in zip(range(0, self.rowCount(), 2), stretches):            
            self.setRowStretch(i, stretch)
                
    def resetRowStretches(self):
        for i in range(0, self.rowCount()):
            self.setRowStretch(i, 0)
            
    def getColumnStretches(self):
        """get the columns streches from all columns, skip the column splitters"""
        stretches = []
        for i in range(0, self.columnCount(), 2):
            stretches.append(self.cellRect(0, i).width())
        return stretches
        
    def setColumnStretches(self, stretches):
        for (i, stretch) in zip(range(0, self.columnCount(), 2), stretches):            
            self.setColumnStretch(i, stretch)
                
    def resetColumnStretches(self):
        for i in range(0, self.rowCount()):
            self.setColumnStretch(i, 0)
            
    def setGeometry(self, arg):            
        self.layoutChanged.emit()
        super().setGeometry(arg)
        
        
class GridSeperator(QtWidgets.QWidget):
    
    def __init__(self, parent=None, orientation = QtCore.Qt.Vertical):
        super().__init__(parent=parent)
        
        self.orientation = orientation
        if orientation == QtCore.Qt.Vertical:
            self.setCursor(QtGui.QCursor(QtCore.Qt.SplitVCursor))
            self.setFixedHeight(5)
        else:
            self.setCursor(QtGui.QCursor(QtCore.Qt.SplitHCursor))
            self.setFixedWidth(5)                        
        self.dragStartX = 0
        self.dragStartY = 0
        
    def mousePressEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton:
            self.dragStartX = event.pos().x()
            self.dragStartY = event.pos().y()
            self.row_stretches = self.gridSplitter.getRowStretches()
            self.column_stretches = self.gridSplitter.getColumnStretches()
            
    def mouseMoveEvent(self, event):
        self.movedX = event.pos().x() - self.dragStartX
        self.movedY = event.pos().y() - self.dragStartY
        if self.orientation == QtCore.Qt.Vertical:
            if self.movedY != 0:
                self.restretchRows(self.movedY)

        if self.orientation == QtCore.Qt.Horizontal:
            if self.movedX != 0:
                self.restretchColumns(self.movedX)
            
    def restretchRows(self, moved):
        stretches = self.row_stretches
        stretches[self.lower] += moved
        stretches[self.current] -= moved
        self.gridSplitter.setRowStretches(stretches)
            
    def restretchColumns(self, moved):
        stretches = self.column_stretches
        stretches[self.lower] += moved
        stretches[self.current] -= moved
        self.gridSplitter.setColumnStretches(stretches)           
        
    def attachGridSplitter(self, gridSplitter, lower, current):
        self.gridSplitter = gridSplitter
        self.lower = lower
        self.current = current        
  