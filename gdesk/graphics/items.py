import numpy as np
from qtpy import QtCore, QtGui, QtWidgets
from .functions import arrayToQPath

QtSignal = QtCore.Signal

class ItemSignal(object):
    def __init__(self):
        self.func = None
    
    def connect(self, func):
        self.func = func
        
    def emit(self, *args):
        if not self.func is None:
            self.func(*args)            
            
class VectorCurve(QtWidgets.QGraphicsPathItem):
    
    def __init__(self, path, xvector, yvector):
        super().__init__(path)
        self.xvector = xvector
        self.yvector = yvector



def createCurve(x, y, color=None, z=0, fill=50, zero_ends=True):
    if color == None:
        pen = QtGui.QPen(QtCore.Qt.black, 0, QtCore.Qt.SolidLine)
        if not fill is None:
            brush = QtGui.QBrush(QtGui.QColor(0,0,0,100))
        
    else:
        pen = QtGui.QPen(color, 0, QtCore.Qt.SolidLine)
        R,G,B,A = QtGui.QColor(color).toTuple()
        if not fill is None:
            brush = QtGui.QBrush(QtGui.QColor(R,G,B,fill))        

    if zero_ends:
        path = arrayToQPath(np.r_[x[0], x, x[-1]], np.r_[0, y, 0])    
    else:
        path = arrayToQPath(x, y)    
            
    #transform the Path to a PathItem                                    
    #curve = QtWidgets.QGraphicsPathItem(path)
    curve = VectorCurve(path, np.array(x), np.array(y))
    if z != 0:
        curve.setZValue(z)
        
    curve.setPen(pen)
    
    if not fill is None:
        curve.setBrush(brush)
    
    return curve
    
    
class LabelItem(QtWidgets.QGraphicsPolygonItem):
    
    def __init__(self, text='', color=QtGui.QColor(0,0,0), parent=None, scene=None):
        super().__init__(parent=parent)
        if scene: scene.addItem(self)
        
        self.makePolygon(40)
        self.setPen(QtGui.QPen(color))
        self.setBrush(QtGui.QColor(240, 240, 240))
        
        self.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        #self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
        
        self.label = QtWidgets.QGraphicsTextItem('', self)
        self.label.setFont(QtGui.QFont('Arial', 8))
        self.label.setPos(-1, 0)
        self.updateText(text)            
        
    def makePolygon(self, box_width):
        polygon = QtGui.QPolygonF()        
        polygon.append(QtCore.QPointF(0, 0))
        polygon.append(QtCore.QPointF(box_width / 2, 5))
        polygon.append(QtCore.QPointF(box_width / 2, 20))
        polygon.append(QtCore.QPointF(-box_width / 2, 20))
        polygon.append(QtCore.QPointF(-box_width / 2, 5))
        polygon.append(QtCore.QPointF(0, 0))
        self.setPolygon(polygon)        
        
    def updateText(self, text):
        self.label.setPlainText(text)
        self.label.setPos(- self.label.boundingRect().width() / 2, 2)    
        self.makePolygon(self.label.boundingRect().width())
        
    def mouseMoveEvent(self, e):
        self.parentItem().mouseMoveEvent(e)
        
    def mouseReleaseEvent(self, event):
        self.parentItem().mouseReleaseEvent(event)
        super().mouseReleaseEvent(event)
        
        
class YLabelItem(QtWidgets.QGraphicsPolygonItem):
    
    def __init__(self, text='', color=QtGui.QColor(0,0,0), parent=None, scene=None):
        super().__init__(parent=parent)
        if scene: scene.addItem(self)
                
        self.setPen(QtGui.QPen(color))
        self.setBrush(QtGui.QColor(240, 240, 240))        
        self.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        
        self.label = QtWidgets.QGraphicsTextItem('', self)
        self.label.setFont(QtGui.QFont('Arial', 8))
                        
        self.offset = 0
        self.updateText(text)
        
    def update_offset(self, offset):
        self.offset = offset
        self.makePolygon()
        
    def makePolygon(self):
        box_width = self.text_width
        offset = self.offset
        polygon = QtGui.QPolygonF()        
        polygon.append(QtCore.QPointF(0, 0))
        polygon.append(QtCore.QPointF(5, -5 + offset))
        polygon.append(QtCore.QPointF(5, -20 + offset))
        polygon.append(QtCore.QPointF(5 + box_width, -20 + offset))
        polygon.append(QtCore.QPointF(5 + box_width, -5 + offset))
        polygon.append(QtCore.QPointF(5, -5+offset))
        polygon.append(QtCore.QPointF(0, 0))
        self.label.setPos(5, -23 + offset)
        self.setPolygon(polygon)        
        
    def updateText(self, text):        
        self.label.setPlainText(text) 
        self.text_width = self.label.boundingRect().width()
        self.makePolygon()
        
    def mouseMoveEvent(self, e):
        self.parentItem().mouseMoveEvent(e)      

    def sortkey(self):
        return self.pos().y()
    
    
class Indicator(QtWidgets.QGraphicsPolygonItem):
    
    def __init__(self, color = QtCore.Qt.blue, text = None, parent=None, scene=None):
        super().__init__(parent=parent)
        if scene: scene.addItem(self)
        self.mouse_released = ItemSignal()
        
        self.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)        
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
        
        self.setPen(QtGui.QPen(color))
                
        polygon = QtGui.QPolygonF()
        
        self.text = text
        
        if text is None:            
            self.setBrush(color)
            polygon.append(QtCore.QPointF(0, 0))
            polygon.append(QtCore.QPointF(7, 10))
            polygon.append(QtCore.QPointF(-7, 10))
            polygon.append(QtCore.QPointF(0, 0))
            polygon.append(QtCore.QPointF(0, -2160))
            self.setPolygon(polygon)
            self.label = None
        else:
            polygon.append(QtCore.QPointF(0, 0))
            polygon.append(QtCore.QPointF(0, -2160))
            polygon.append(QtCore.QPointF(0, 0))
            self.setPolygon(polygon)
            self.label = LabelItem(self.text, color, self, scene)
            #self.addItem(self.label)
            
        self.ylabels = []
        
    def attach_curves(self, curves):
        self.curves = curves
        
    def set_ylabel_count(self, count):
        for i in range(len(self.ylabels) - count):
            ylabel = self.ylabels.pop(0)
            self.scene().removeItem(ylabel)
        
        for i in range(count - len(self.ylabels)):
            ylabel = YLabelItem('test', parent = self)
            self.ylabels.append(ylabel)                                
        
    def updates_ylabels(self, x=None):        
        x = self.scenePos().x() if x is None else x
        view = self.scene().views()[0]
        self.set_ylabel_count(len(self.curves))
        for curve, ylabel in zip(self.curves.values(), self.ylabels):
            yval = np.interp(x, curve.xvector, curve.yvector,0,0)                                
            yscale = view.scale[1]
            ypos = (yval - self.scenePos().y()) * yscale
            if ypos > 0:
                ypos = 0
            elif ypos < (-view.height()+23):
                ypos = -view.height()+23
            ylabel.setPos(0, ypos)
            ylabel.updateText("%0.4g" % yval)                    
            ylabel.setPen(curve.pen())
        self.declutter_ylabels(-view.height()+22)

    def declutter_ylabels(self, ymin=-4000, ymax=0):
        self.ylabels = sorted(self.ylabels, key = YLabelItem.sortkey)
        prior_bottom = ymin
        for ylabel in self.ylabels:
            ypos = ylabel.pos().y()
            if (ypos - prior_bottom) < 21:
                offset = abs(21 - (ypos - prior_bottom))
            else:
                offset = 0
            ylabel.update_offset(offset)
            prior_bottom = ypos -5 + offset
        
    def mouseReleaseEvent(self, event):        
        self.mouse_released.emit(self.pos().x())
        super().mouseReleaseEvent(event)        
                
    def mouseMoveEvent(self, event):        
        x = event.scenePos().x()
        if (not self.label is None) and ('%' in self.text):            
            self.label.updateText(self.text % x)
        
        self.setPos(x, 0)            
        self.updates_ylabels(x)
        
        self.scene().moving_indicators = True


class Grid(QtWidgets.QGraphicsItem):

    def __init__(self, direction, parent=None, scene=None):
        super().__init__(parent=parent)
        if scene: scene.addItem(self)
        pens = []   
        pens.append(QtGui.QPen(QtGui.QColor(159,159,159), 0, QtCore.Qt.SolidLine))
        pens.append(QtGui.QPen(QtGui.QColor(191,191,191), 0, QtCore.Qt.DashLine))
        pens.append(QtGui.QPen(QtGui.QColor(223,223,223), 0, QtCore.Qt.DotLine))
        pens.append(QtGui.QPen(QtGui.QColor(159,159,159), 0, QtCore.Qt.SolidLine))
        pens.append(QtGui.QPen(QtGui.QColor(191,191,191), 0, QtCore.Qt.DashLine))
        pens.append(QtGui.QPen(QtGui.QColor(223,223,223), 0, QtCore.Qt.DotLine))        
        
        self.pens = pens
        self.grid_items = []       
        self.direction = direction
        
    def boundingRect(self):
        return QtCore.QRectF(-2, -2, 4, 4)

    def paint(self, painter, option, widget):
        pass
        #painter.drawRoundedRect(-10, -10, 20, 20, 5, 5)        
               
    def attach_rulers(self, x_ruler, y_ruler):
        self.x_ruler = x_ruler
        self.y_ruler = y_ruler
        self.update_grid()        
        
    def update_grid(self):
        for path_item in self.grid_items:
            self.scene().removeItem(path_item)
            
        self.grid_items = []            
            
        pens = self.pens             
        paths = []      
        view = self.scene().views()[0]                
                           
        for thicklevel in range(3):
            paths.append(QtGui.QPainterPath())
            for i in self.x_ruler.thicks[thicklevel][1]:
                if self.direction == 0:
                    paths[-1].moveTo(i, self.y_ruler.start)
                    paths[-1].lineTo(i, self.y_ruler.stop)               
                else:
                    paths[-1].moveTo(self.x_ruler.start, i)
                    paths[-1].lineTo(self.x_ruler.stop, i) 
                               
        for thicklevel in range(3):        
            paths.append(QtGui.QPainterPath())  
            for i in self.y_ruler.thicks[thicklevel][1]:
                if self.direction == 0:
                    paths[-1].moveTo(self.x_ruler.start, i)
                    paths[-1].lineTo(self.x_ruler.stop, i)
                else:
                    paths[-1].moveTo(i, self.y_ruler.start)
                    paths[-1].lineTo(i, self.y_ruler.stop)
                
        for i in range(len(paths)):
            path_item = QtWidgets.QGraphicsPathItem(paths[i], parent=self)
            path_item.setPen(pens[i])
            path_item.setZValue(-2)
            self.grid_items.append(path_item)         
        