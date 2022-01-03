import math
import numpy as np

from qtpy import QtCore, QtGui, QtWidgets

from ...graphics.plotview import PlotView
from ...graphics.rulers import TickedRuler, Axis
from ...graphics.functions import arrayToQPath
from ...graphics.items import createCurve

from ...utils.ticks import tickValues

class ProfileGraphicView(PlotView):

    def __init__(self, parent=None):
        super().__init__(parent)                                    
           
                   
class ProfilerPanel(QtWidgets.QWidget):

    def __init__(self, parent, direction, imviewer):
        super().__init__(parent=parent)
        
        self.imagePanel = imviewer
        self.scene = QtWidgets.QGraphicsScene()
        self.view = ProfileGraphicView(self)
        self.view.setScene(self.scene)            
        
        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(0,0,0,0)
        vbox.addWidget(self.view)        
        self.setLayout(vbox)        
       
        if direction == 'x':
            self.direction = 0
            self.view.fixScaleX = True
            self.view.scale[1] = -self.view.scale[1]
            self.view.updateMatrix()
            self.setMinimumHeight(20)
        else:
            self.direction = 90
            self.view.fixScaleY = True
            self.view.scale[0] = -self.view.scale[0]
            self.view.updateMatrix()
            self.setMinimumWidth(20)
                                                       
        self.view.matrixUpdated.connect(self.redrawSlices)
        self.view.matrixUpdated.connect(self.repositionRuler)        
        self.view.matrixUpdated.connect(self.repositionYAxis)
        self.view.doubleClicked.connect(self.zoomFit)           
                
        self.meanProfileCurve = None
        self.roiProfileCurve = None
        self.pixProfileCurve = None
        self.grid = []
        self.ruler = None
        self.yAxis = None
        
    def zoomFull(self):
            
        top = bottom = left = right = None
        for curve in [self.pixProfileCurve, self.roiProfileCurve, self.meanProfileCurve]:
            if curve is None:
                continue
            r = curve.boundingRect()
            top = r.top() if top is None else min(r.top(), top)
            bottom = r.bottom() if bottom is None else max(r.bottom(), bottom)
            left = r.left() if left is None else min(r.left(), left)
            right = r.right()if right is None else max(r.right(), right)
            
        if top is None:
            return           
            
        height = bottom - top
        width = right - left
            
        if self.direction == 0:                          
            if height == 0:                
                self.view.setYCenter(top)
            else:
                scale = -(self.height() - 20) / max(height, 1e-9)
                self.view.setYPosScale(bottom, scale)
        elif self.direction == 90: 
            if width == 0:
                self.view.setXCenter(left)
            else:
                scale = -(self.width() - 20)/ max(width, 1e-9)
                self.view.setXPosScale(right, scale)
                
    def zoomFit(self):
        if self.meanProfileCurve is None:
            self.zoomFull()
            return
        
        xvec = self.meanProfileCurve.xvector
        yvec = self.meanProfileCurve.yvector
            
        if self.direction == 0:
            x0, x1 = self.view.getXLimits()
            x0 = max(round(x0), 0)
            x1 = min(round(x1), len(xvec))
            y0, y1 = yvec[x0:x1].min(), yvec[x0:x1].max()
            if y0 != y1:
                self.view.setYLimits(y0, y1, 20)
            else:
                self.view.setYLimits(y0-0.5, y1+0.5, 20)
                
        elif self.direction == 90:
            y0, y1 = self.view.getYLimits()
            y0 = max(round(y0), 0)
            y1 = min(round(y1), len(yvec))
            x0, x1 = xvec[y0:y1].min(), xvec[y0:y1].max()
            if x0 != x1:
                self.view.setXLimits(x1, x0, 20)
            else:
                self.view.setXLimits(x1+0.5, x0-0.5, 20)
                
    def refresh(self):
        self.removeAllItems()

        #self.createRuler()
        #self.createYAxis()
        #self.createGrid()                                
        
        if self.meanProfileCurve is not None:
            self.scene.addItem(self.meanProfileCurve)
            
        if self.pixProfileCurve is not None:
            self.scene.addItem(self.pixProfileCurve)
                    
        self.view.refresh()       
        self.redrawSlices()
        self.repositionRuler()
        self.repositionYAxis()               
        
        
    def removeAllItems(self):
        for i in self.scene.items():
            #only need to remove top level items
            if i.parentItem() == None:
                self.scene.removeItem(i)
                
        self.meanProfileCurve = None
        self.roiProfileCurve = None
        self.pixProfileCurve = None
        self.grid = []
        self.ruler = None
        self.yAxis = None
        
        
    def createYAxis(self):
        if not self.yAxisEnabled:
            self.yAxis = None
            return 0            
            
        if self.direction == 0:        
            scaleY = -self.view.scale[1]
            sceneTopLeft = self.view.mapToScene(0,0)
            sceneBotRight = self.view.mapToScene(self.width()-1, self.height()-1)            
            self.stopY = sceneTopLeft.y()
            self.startY = sceneBotRight.y()                        
            self.thicksY = tickValues(self.startY, self.stopY, scaleY)           
            self.yAxis = Axis(0, self.startY, self.stopY, self.thicksY)
        elif self.direction == 90:
            scaleY = -self.view.scale[0]
            sceneTopLeft = self.view.mapToScene(0,0)
            sceneBotRight = self.view.mapToScene(self.width()-1, self.height()-1)            
            self.stopY = sceneTopLeft.x()
            self.startY = sceneBotRight.x()                        
            self.thicksY = tickValues(self.startY, self.stopY, scaleY)
            self.yAxis = Axis(90, self.startY, self.stopY, self.thicksY)
            
        #self.yAxis.setZValue(-1)
        self.yAxis.setZValue(0.9)
        self.scene.addItem(self.yAxis)
        
    def createRuler(self):
        #self.ruler = Ruler(self.direction, self.startX, self.stopX, self.stepX)
        
        if self.direction == 0:
            scaleX = self.view.scale[0]
            
            if self.imagePanel.dispOffsetX < 0:
                self.startX = 0
                self.stopX = self.imagePanel.dispOffsetX + self.width() / scaleX
            else:
                self.startX = self.imagePanel.dispOffsetX
                self.stopX = math.ceil(self.startX + self.width() / scaleX)
                
            self.stopX = min(self.imagePanel.vd.width, self.stopX)                                                                      
            self.ruler = TickedRuler(0, self.startX, self.stopX, scaleX, noDecimals=True)        
            
        elif self.direction == 90:
            scaleX = self.view.scale[1]
            
            if self.imagePanel.dispOffsetY < 0:
                self.startX = 0
                self.stopX = self.imagePanel.dispOffsetY + self.height() / scaleX
            else:
                self.startX = self.imagePanel.dispOffsetY
                self.stopX = math.ceil(self.startX + self.height() / scaleX)
                
            self.stopX = min(self.imagePanel.vd.height, self.stopX)            
            self.ruler = TickedRuler(90, self.startX, self.stopX, scaleX, noDecimals=True)        
            
        self.ruler.setZValue(1)
        self.scene.addItem(self.ruler)
        
    def repositionRuler(self):
        tr = self.view.mapToScene(self.width()-20, self.height()-20)
        if self.direction == 0:
            self.ruler.setY(tr.y())
        elif self.direction == 90:
            self.ruler.setX(tr.x())
                  
    def repositionYAxis(self):
        if self.yAxis == None:
            return 0            
        tr = self.view.mapToScene(50, 10)
        if self.direction == 0:
            self.yAxis.setX(tr.x())
        elif self.direction == 90:
            self.yAxis.setY(tr.y())

    def zoomToImage(self):
        scale = self.imagePanel.zoomValue
        
        if self.direction == 0:
            x = self.imagePanel.dispOffsetX        
            self.view.setXPosScale(x, scale)
        elif self.direction == 90:
            y = self.imagePanel.dispOffsetY       
            self.view.setYPosScale(y, scale)

        
    def addPlot(self, x, y, color=None, z=0):
        curve = self.createCurve(x, y, color, z)
        self.curves.append(curve)
        
    def drawMeanProfile(self, x, y):
        if self.meanProfileCurve is not None:
            self.scene.removeItem(self.meanProfileCurve)
        
        self.meanProfileCurve = self.createCurve(x, y, color=QtCore.Qt.blue, z=0.5)
        self.scene.addItem(self.meanProfileCurve)               
        
    def drawRoiProfile(self, x, y):
        if self.roiProfileCurve is not None:
            self.scene.removeItem(self.roiProfileCurve)
        
        self.roiProfileCurve = self.createCurve(x, y, color=QtCore.Qt.darkGreen, z=0.25)
        self.scene.addItem(self.roiProfileCurve)          
        
    def drawPixelProfile(self, x, y):
        self.removePixelProfile()        
        self.pixProfileCurve = self.createCurve(x, y, color=QtCore.Qt.red, z=0)
        self.scene.addItem(self.pixProfileCurve)                

    def removeRoiProfile(self):
        if self.roiProfileCurve is not None:
            self.scene.removeItem(self.roiProfileCurve)
            self.roiProfileCurve = None
            
    def removePixelProfile(self):
        if self.pixProfileCurve is not None:
            self.scene.removeItem(self.pixProfileCurve)
            self.pixProfileCurve = None            
            
    def removeMeanProfile(self):
        if self.meanProfileCurve is not None:
            self.scene.removeItem(self.meanProfileCurve)
            self.meanProfileCurve = None            
            
        
    def createCurve(self, x, y, color=None, z=0):
        if color == None:
            color = QtCore.Qt.blue                    
                
        if isinstance(x, np.ndarray) and isinstance(y, np.ndarray):
            if self.direction == 0:
                curve = createCurve(x, y, color, z, None, zero_ends=False)
            elif self.direction == 90:
                curve = createCurve(y, x, color, z, None, zero_ends=False)
        else:
            #first create a Path        
            path = QtGui.QPainterPath()
        
            if self.direction == 0:
                path.moveTo(x[0], y[0])
                for i in range(1, len(y)):
                    path.lineTo(x[i], y[i])     
            elif self.direction == 90:
                path.moveTo(y[0], x[0])
                for i in range(1, len(y)):
                    path.lineTo(y[i], x[i])
                
            #transform the Path to a PathItem                                    
            curve = QtWidgets.QGraphicsPathItem(path)
            
            if z != 0:
                curve.setZValue(z)
                
            curve.setPen(pen)
        
        return curve
                        
    def clear(self):
        self.meanProfileCurve = None
        self.roiProfileCurve = None
        self.pixProfileCurve = None
        
    def showOnlyRuler(self):
        if self.direction == 0:
            self.setFixedHeight(20)
        elif self.direction == 90:
            self.setFixedWidth(20)          
        self.gridEnabled = False
        self.yAxisEnabled = False
        self.plotsEnabled = False
        self.refresh()
        
    def showAll(self):
        self.gridEnabled = True
        self.yAxisEnabled = True
        self.plotsEnabled = True
        self.refresh()
        
    def removelast(self):
        if len(self.curves) > 0:
            lastCurve = self.curves[-1]
            if lastCurve in self.scene.items():
                self.scene.removeItem(lastCurve)
            self.curves.pop()
        
    def createGrid(self):
        self.grid = []
        if not self.gridEnabled:
            return 0
            
        pens = []
        pens.append(QtGui.QPen(QtGui.QColor(159,159,159), 0, QtCore.Qt.SolidLine))
        pens.append(QtGui.QPen(QtGui.QColor(191,191,191), 0, QtCore.Qt.DashLine))
        pens.append(QtGui.QPen(QtGui.QColor(223,223,223), 0, QtCore.Qt.DotLine))
        pens.append(QtGui.QPen(QtGui.QColor(159,159,159), 0, QtCore.Qt.SolidLine))
        pens.append(QtGui.QPen(QtGui.QColor(191,191,191), 0, QtCore.Qt.DashLine))
        pens.append(QtGui.QPen(QtGui.QColor(223,223,223), 0, QtCore.Qt.DotLine))        
        paths = []
                
                           
        for thicklevel in range(3):
            paths.append(QtGui.QPainterPath())
            for i in self.ruler.thicks[thicklevel][1]:
                if self.direction == 0:
                    paths[-1].moveTo(i, self.startY)
                    paths[-1].lineTo(i, self.stopY)               
                else:
                    paths[-1].moveTo(self.startY, i)
                    paths[-1].lineTo(self.stopY, i) 
                               
        for thicklevel in range(3):        
            paths.append(QtGui.QPainterPath())  
            for i in self.thicksY[thicklevel][1]:
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
        
    def redrawSlices(self):   
        if not self.ruler is None:
            self.scene.removeItem(self.ruler)
            
        self.createRuler()        
        
        if not self.yAxis is None:
            self.scene.removeItem(self.yAxis)
            
        self.createYAxis()
        
        for items in self.grid:
            self.scene.removeItem(items) 
            
        self.createGrid()   

    def resizeEvent(self, ev):    
        self.redrawSlices()
        self.repositionRuler()
        self.repositionYAxis()

