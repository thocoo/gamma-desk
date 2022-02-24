# -*- coding: latin-1 -*-
#-------------------------------------------------------------------------------
# Name:        imageport.roi
# Purpose:     Region of Interest
#
# Author:      Thomas Cools
#
# Created:     01/08/2014
# Copyright:   (c) Thomas Cools 2014
# Licence:     <your licence>
#-------------------------------------------------------------------------------

from qtpy import QtCore, QtGui, QtWidgets

from ... import config

AUTO_APPLY = False

class SelRoiWidget(QtWidgets.QWidget):
    
    """
    Selection widget of a region of interest.
    """
    
    roiChanged = QtCore.Signal()
    roiRemoved = QtCore.Signal()
    
    def __init__(self, parent=None):
        #width and height are the dimensions of the image (not the roi)
        super().__init__(parent=parent)

        self.phase = 0
        self.solidColor = QtCore.Qt.white        

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.newPhase)
        self.timer.setSingleShot(True)
        self.setMouseTracking(True)        
        #  is this timer also active when roi isn't visible ???

        self.initProps()
        self.initUI()
        self.hide()
        
        self.get_context_menu = lambda: None  

    def initUI(self):
        self.scaleCursor = QtGui.QCursor(QtCore.Qt.SizeAllCursor)
        self.fillColor = QtGui.QColor(*config['roi color'])
        self.dashColor = QtGui.QColor(*config['roi color'])
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, False)
        
    @property
    def vd(self):
        return self.parent().vd
        
    @property
    def selroi(self):
        return self.vd.selroi

    def initProps(self):
        self.dragSliceStartX = self.selroi.xr.start
        self.dragSliceStartY = self.selroi.yr.start
        self.dragStartX = 0
        self.dragStartY = 0
        self.mouseRightWasDown = False
        self.mouseMidWasDown = False
        self.mouseDoubleClicked = False

        self.overscan = 5
        self.createState = False

    def selectAll(self):
        self.selroi.reset()
        self.selroi.update_statistics()
        self.recalcGeometry()

    def newPhase(self):
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        
        self.phase = (self.phase + 1) % 8

        #self.parent().setUpdatesEnabled(False)
        #self.setUpdatesEnabled(True)                        
        
        #self.blockSignals(True)
        self.repaint(0,self.overscan,self.width(),1)
        self.repaint(self.overscan,0,1,self.height())
        self.repaint(0,self.height()-self.overscan-1,self.width(),1)
        self.repaint(self.width()-self.overscan-1,0,1,self.height())
        
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, False)
        #self.update()
        #self.parent().blockSignals(False)
        self.timer.start(100)
        #self.parent().setUpdatesEnabled(True)

    def setStartEndPoints(self, startX, startY, endX, endY):
    
        startX = int(round(startX))
        startY = int(round(startY))
        endX = int(round(endX))
        endY = int(round(endY))                

        if (startX > endX) and (startY > endY):
            pass

        else:
            if startY > endY:
                startY = endY
            if startX > endX:
                startX = endX

        self.selroi.xr.start = startX
        self.selroi.xr.stop = endX + 1
        self.selroi.yr.start = startY
        self.selroi.yr.stop = endY + 1

        self.clip()

    def clip(self):
        self.selroi.ensure_rising()
        self.selroi.clip()
        self.selroi.update_statistics()
        self.recalcGeometry()

    def asSliceTupple(self):
        return (slice(self.selroi.xr.start, self.selroi.xr.stop), \
            slice(self.selroi.yr.start, self.selroi.yr.stop))

    def recalcGeometry(self):
        x0 = round((self.selroi.xr.start - self.parent().dispOffsetX) * self.parent().zoomValue)
        y0 = round((self.selroi.yr.start - self.parent().dispOffsetY) * self.parent().zoomValue)
        x1 = round((self.selroi.xr.stop - self.parent().dispOffsetX) * self.parent().zoomValue)
        y1 = round((self.selroi.yr.stop - self.parent().dispOffsetY) * self.parent().zoomValue)
        width = max(abs(x1 - x0),1)
        height = max(abs(y1 - y0),1)

        self.setGeometry(min(x0,x1)-self.overscan, min(y0,y1)-self.overscan, width+2*self.overscan, height+2*self.overscan)

    def mousePressEvent(self, event):
        if (event.buttons() == QtCore.Qt.RightButton) and \
            not self.createState:
            #check if we are not doing setStartEndPoints
                self.createState = True

                self.edgePosition = self.checkNearEdge(event)
                self.setCursorShape(self.edgePosition)

                self.dragStartX  = event.globalX()
                self.dragStartY  = event.globalY()

                self.dragSliceStartX = self.selroi.xr.start
                self.dragSliceStartY = self.selroi.yr.start
                self.dragSliceEndX = self.selroi.xr.stop
                self.dragSliceEndY = self.selroi.yr.stop

                self.mouseRightWasDown = True
                self.repaint()
        elif (event.buttons() == QtCore.Qt.MidButton):
            self.dragStartX  = event.globalX()
            self.dragStartY  = event.globalY()
            self.mouseMidWasDown = True
            #propagated up the parent widget
            event.ignore()
        else:
            #propagated up the parent widget
             event.ignore()

    def checkNearEdge(self, event):
        x = event.pos().x()
        y = event.pos().y()
        (x0, y0, x1, y1) = self.getRelativeCoord()

        if abs(x0 - x1) <= 10:
            hori = 1
        elif abs(x0 - x) < 5:
            hori = 0
        elif abs(x1 - x) < 5:
            hori = 2
        else:
            hori = 1

        if abs(y0 - y1) <= 10:
            vert = 1
        elif abs(y0 - y) < 5:
            vert = 0
        elif abs(y1 - y) < 5:
            vert = 2
        else:
            vert = 1

        return vert * 3 + hori

    def setCursorShape(self, edgePosition):
        if edgePosition in (0, 8):
            self.setCursor(QtCore.Qt.SizeFDiagCursor)
        elif edgePosition in (1, 7):
            self.setCursor(QtCore.Qt.SizeVerCursor)
        elif edgePosition in (2, 6):
            self.setCursor(QtCore.Qt.SizeBDiagCursor)
        elif edgePosition in (3, 5):
            self.setCursor(QtCore.Qt.SizeHorCursor)
        elif edgePosition == 4:
            self.setCursor(QtCore.Qt.SizeAllCursor)

    def getMouseShifts(self, event, manhattan=False):
        if manhattan:
            if abs(self.dragStartX - event.globalX()) > abs(self.dragStartY  - event.globalY()):
                self.dragEndX = event.globalX()
                self.dragEndY = self.dragStartY
            else:
                self.dragEndX = self.dragStartX
                self.dragEndY = event.globalY()
        else:
            self.dragEndX = event.globalX()
            self.dragEndY = event.globalY()
        shiftX = round((self.dragEndX - self.dragStartX) / self.parent().zoomValue)
        shiftY = round((self.dragEndY - self.dragStartY) / self.parent().zoomValue)
        return (shiftX, shiftY)

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.RightButton:            
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                shiftX, shiftY = self.getMouseShifts(event, manhattan=True)
            else:
                shiftX, shiftY = self.getMouseShifts(event, manhattan=False)
                
            if self.edgePosition == 0:
                self.setStartEndPoints(self.dragSliceStartX  + shiftX, self.dragSliceStartY + shiftY,\
                    self.dragSliceEndX -1, self.dragSliceEndY -1)
            elif self.edgePosition == 1:
                self.setStartEndPoints(self.dragSliceStartX, self.dragSliceStartY + shiftY,\
                    self.dragSliceEndX -1, self.dragSliceEndY -1)
            elif self.edgePosition == 2:
                self.setStartEndPoints(self.dragSliceStartX, self.dragSliceStartY + shiftY,\
                    self.dragSliceEndX + shiftX - 1, self.dragSliceEndY -1)
            elif self.edgePosition == 3:
                self.setStartEndPoints(self.dragSliceStartX  + shiftX, self.dragSliceStartY,\
                    self.dragSliceEndX - 1, self.dragSliceEndY -1)
            elif self.edgePosition == 4:
                #moving
                #limiting the shift to the borders of the image
                if (self.dragSliceStartX  + shiftX) < 0:
                    shiftX = - self.dragSliceStartX
                if (self.dragSliceEndX + shiftX - 1) >= self.selroi.xr.maxstop:
                    shiftX = self.selroi.xr.maxstop - self.dragSliceEndX
                if (self.dragSliceStartY  + shiftY) < 0:
                    shiftY = - self.dragSliceStartY
                if (self.dragSliceEndY + shiftY - 1) >= self.selroi.yr.maxstop:
                    shiftY = self.selroi.yr.maxstop - self.dragSliceEndY                        
                self.setStartEndPoints(self.dragSliceStartX  + shiftX, self.dragSliceStartY + shiftY,\
                    self.dragSliceEndX + shiftX - 1, self.dragSliceEndY + shiftY - 1)
            elif self.edgePosition == 5:
                self.setStartEndPoints(self.dragSliceStartX, self.dragSliceStartY,\
                    self.dragSliceEndX + shiftX - 1, self.dragSliceEndY  -1)
            elif self.edgePosition == 6:
                self.setStartEndPoints(self.dragSliceStartX  + shiftX, self.dragSliceStartY,\
                    self.dragSliceEndX - 1, self.dragSliceEndY + shiftY - 1)
            elif self.edgePosition == 7:
                self.setStartEndPoints(self.dragSliceStartX, self.dragSliceStartY,\
                    self.dragSliceEndX - 1, self.dragSliceEndY + shiftY - 1)
            elif self.edgePosition == 8:
                self.setStartEndPoints(self.dragSliceStartX, self.dragSliceStartY,\
                    self.dragSliceEndX + shiftX - 1, self.dragSliceEndY + shiftY - 1)
            self.repaint()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        self.createState = False
        
        contextMenu = self.get_context_menu()

        if self.mouseRightWasDown:
            self.mouseRightWasDown = False
            shiftX, shiftY = self.getMouseShifts(event)
            if (shiftX == 0) and (shiftY == 0):   
                pos = QtGui.QCursor.pos()
                pos.setX(pos.x() - 10)
                pos.setY(pos.y() - 10)
                
                if not contextMenu is None:
                    contextMenu.exec_(pos)              
                    
                #return None
                #self.parent().myContextMenuEvent(event)
            else:
                self.clip()
                if AUTO_APPLY:
                    self.applyRoi()            
                self.roiChanged.emit()

        if self.mouseMidWasDown:
            self.mouseMidWasDown = False
            shiftX, shiftY = self.getMouseShifts(event)
            if (shiftX == 0) and (shiftY == 0):
                self.parent().zoomAuto()
        
        self.unsetCursor()
        self.repaint()
        event.ignore()
        
    def release_creation(self):
        self.createState = False        
        self.clip()
        if AUTO_APPLY:
            self.applyRoi()
        self.roiChanged.emit()
        self.repaint()                
        
    def hideRoi(self):
        self.selroi.reset()
        if AUTO_APPLY:
            self.applyRoi()
        self.hide()
        self.unsetCursor()
        self.roiRemoved.emit()
        self.repaint()   

    def applyRoi(self):
        self.parent().vd.applyroi()

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawRoi(qp)
        qp.end()        

    def getRelativeCoord(self):
        x0 = self.overscan
        y0 = self.overscan
        x1 = self.size().width()-1-self.overscan
        y1 = self.size().height()-1-self.overscan
        return (x0, y0, x1, y1)

    def drawRoi(self, qp):
        pensolid = QtGui.QPen(self.solidColor, 1, QtCore.Qt.SolidLine)
        pendash = QtGui.QPen(self.dashColor, 1, QtCore.Qt.CustomDashLine)
##        pendash.setDashPattern([3, 3, 1, 5, 3, 3, 5, 1])
        pendash.setDashPattern([4,4])

        x0 = self.overscan
        y0 = self.overscan        
        #max-> keep is visible even if it is smaller then 1x1
        x1 = max(self.size().width() - 1 - self.overscan, x0 + 1)
        y1 = max(self.size().height() - 1 - self.overscan, y0 + 1)

        pendash.setDashOffset(8-self.phase)

        polygonRect = QtGui.QPolygon()
        polygonNe = QtGui.QPolygon()
        polygonSw = QtGui.QPolygon()

        polygonRect << QtCore.QPoint(x0, y0) << QtCore.QPoint(x1, y0)\
            << QtCore.QPoint(x1, y1) << QtCore.QPoint(x0, y1)
        polygonNe << QtCore.QPoint(x0, y0) << QtCore.QPoint(x1, y0)\
            << QtCore.QPoint(x1, y1)
        polygonSw << QtCore.QPoint(x0, y0)  << QtCore.QPoint(x0, y1)\
            << QtCore.QPoint(x1, y1)


        if self.createState:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, False)
            qp.setOpacity(0.25)
            qp.fillRect(x0, y0, x1-x0+1, y1-y0+1, self.fillColor)
            qp.setOpacity(0.5)
        else:
            qp.setOpacity(1.0)
            self.timer.start(100)
            

        qp.setPen(pensolid)
        qp.drawPolygon(polygonRect)
        qp.setPen(pendash)
        qp.drawPolyline(polygonNe)
        qp.drawPolyline(polygonSw)
        
        #self.parent().blockSignals(False)
