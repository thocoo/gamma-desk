from qtpy import QtCore, QtGui, QtWidgets

class yAxisLabel(QtWidgets.QGraphicsLineItem):
    
    def __init__(self, ticksX, ticksY, direction, parent=None, scene=None):
        super().__init__(parent=parent, scene=scene)
        self.direction = direction
        
    def createGrid(self):
        self.grid = []
            
        pens = []
        pens.append(QtGui.QPen(QtGui.QColor(159,159,159), 0, QtCore.Qt.SolidLine))
        pens.append(QtGui.QPen(QtGui.QColor(191,191,191), 0, QtCore.Qt.DashLine))
        pens.append(QtGui.QPen(QtGui.QColor(223,223,223), 0, QtCore.Qt.DotLine))
        pens.append(QtGui.QPen(QtGui.QColor(159,159,159), 0, QtCore.Qt.SolidLine))
        pens.append(QtGui.QPen(QtGui.QColor(191,191,191), 0, QtCore.Qt.DashLine))
        pens.append(QtGui.QPen(QtGui.QColor(223,223,223), 0, QtCore.Qt.DotLine))        
        paths = []

        for ticklevel in range(3):
            paths.append(QtGui.QPainterPath())
            for i in self.ticksX[ticklevel][1]:
                if self.direction == 0:
                    paths[-1].moveTo(i, self.startY)
                    paths[-1].lineTo(i, self.stopY)               
                else:
                    paths[-1].moveTo(self.startY, i)
                    paths[-1].lineTo(self.stopY, i) 
                               
        for ticklevel in range(3):        
            paths.append(QtGui.QPainterPath())  
            for i in self.ticksY[ticklevel][1]:
                if self.direction == 0:
                    paths[-1].moveTo(self.startX, i)
                    paths[-1].lineTo(self.stopX, i)
                else:
                    paths[-1].moveTo(i, self.startX)
                    paths[-1].lineTo(i, self.stopX)
                
        for i in range(len(paths)):
            self.grid.append(QtWidgets.QGraphicsPathItem(paths[i]))
            self.grid[-1].setPen(pens[i])
            self.grid[-1].setZValue(-2)
            self.scene.addItem(self.grid[-1])
