from qtpy import QtCore, QtGui, QtWidgets
from ..utils.ticks import tickValues, Ticks
      
FONTS = [
    QtGui.QFont('Arial', 8),
    QtGui.QFont('Arial', 7),
    QtGui.QFont('Arial', 5),
]

GRID_PENS = {
    "Light": [
        QtGui.QPen(QtGui.QColor(159,159,159), 0, QtCore.Qt.SolidLine),
        QtGui.QPen(QtGui.QColor(191,191,191), 0, QtCore.Qt.DashLine),
        QtGui.QPen(QtGui.QColor(223,223,223), 0, QtCore.Qt.DotLine),
    ],
    "Dark": [
        QtGui.QPen(QtGui.QColor(128, 128, 128), 0, QtCore.Qt.SolidLine),
        QtGui.QPen(QtGui.QColor(100, 100, 100), 0, QtCore.Qt.DashLine),
        QtGui.QPen(QtGui.QColor(90, 90, 90), 0, QtCore.Qt.DotLine),
    ],
}

LABEL_LAYOUT = {
    "Light": {
        "background": (QtGui.QPen(QtGui.QColor(200, 200, 200, 200)), QtGui.QBrush(QtGui.QColor(200, 200, 200, 200), QtCore.Qt.SolidPattern)),
        "text": QtGui.QColor(120, 120, 120),
    },
    "Dark": {
        "background": (QtGui.QPen(QtGui.QColor(0, 0, 0, 200)), QtGui.QBrush(QtGui.QColor(0, 0, 0, 200), QtCore.Qt.SolidPattern)),
        "text": QtGui.QColor(190, 190, 190),
    },
}


class LabelItem(QtWidgets.QGraphicsLineItem):
    
    def __init__(self, text='', level=0, grid=False, parent=None, scene=None):
        super().__init__(parent=parent)
        self.color_scheme = QtWidgets.QApplication.instance().color_scheme
        if scene: scene.addItem(self)                   
        self.setLine(0, 0, 0, 10)
        self.setFlags(QtWidgets.QGraphicsItem.ItemIgnoresTransformations)
        self.label = QtWidgets.QGraphicsTextItem(text, self)
        self.label.setFont(FONTS[level])
        self.label.setPos(-1, 2)
        
        if grid:
            self.gline = QtWidgets.QGraphicsLineItem(self)
            self.gline.setPen(GRID_PENS[self.color_scheme][level])
            self.gline.setLine(0, -1e6, 0, 0)
            #self.gline.setZValue(0)
        
    def setRightAlign(self):
        self.label.setPos(2 - self.label.boundingRect().width(), 2)
                
                
class GridItem(QtWidgets.QGraphicsLineItem):
    
    def __init__(self, level=0,  parent=None, scene=None):
        super().__init__(parent=parent)
        self.color_scheme = QtWidgets.QApplication.instance().color_scheme
        if scene: scene.addItem(self)
        self.setFlags(QtWidgets.QGraphicsItem.ItemIgnoresTransformations)
        self.gline = QtWidgets.QGraphicsLineItem(self)
        self.gline.setPen(GRID_PENS[self.color_scheme][level])
        self.gline.setLine(0, -1e6, 0, 0)    
        
        
class yAxisLabel(QtWidgets.QGraphicsLineItem):
    
    def __init__(self, text='', fontNumber=0, parent=None, scene=None):
        super().__init__(parent=parent)
        self.color_scheme = QtWidgets.QApplication.instance().color_scheme
        if scene: scene.addItem(self)
        self.setFlags(QtWidgets.QGraphicsItem.ItemIgnoresTransformations)
        
        self.bgrect = QtWidgets.QGraphicsRectItem(-40, -10, 40, 20, parent=self)
        self.bgrect.setPen(LABEL_LAYOUT[self.color_scheme]["background"][0])
        self.bgrect.setBrush(LABEL_LAYOUT[self.color_scheme]["background"][1])
        
        self.label = QtWidgets.QGraphicsTextItem(text, self)
        self.label.setDefaultTextColor(LABEL_LAYOUT[self.color_scheme]["text"])
        self.label.setFont(FONTS[fontNumber])
        self.label.setPos(-self.label.boundingRect().width(), -10)
        
    def setRightAlign(self):
        self.label.setPos(2 - self.label.boundingRect().width(), 2)        
        
        
class SubDivisionX(QtWidgets.QGraphicsLineItem):
    
    def __init__(self,  parent=None, scene=None):
        super().__init__(parent=parent)
        if scene: scene.addItem(self)
        self.setLine(0, 0, 0, 3)
        self.setFlags(QtWidgets.QGraphicsItem.ItemIgnoresTransformations)


class SubDivisionY(QtWidgets.QGraphicsLineItem):
    
    def __init__(self,  parent=None, scene=None):
        super().__init__(parent=parent)
        if scene: scene.addItem(self)
        self.setLine(0, 0, 3, 0)
        self.setFlags(QtWidgets.QGraphicsItem.ItemIgnoresTransformations)
               


#I think QGraphicsItemGroup is better, but i prevents moving the indicators
#I don't know why?
#class TickedRuler(QtWidgets.QGraphicsItemGroup):
class TickedRuler(QtWidgets.QGraphicsPolygonItem):
    
    def __init__(self, orientation, start, stop, scale, bg_color, noDecimals=True, parent=None, scene=None):
        super().__init__(parent=parent)           
        
        self.orientation = orientation
        self.noDecimals = noDecimals        
        self.logscale = False
        self.create_ticks(start, stop, scale)         
        self.init_bg(bg_color=bg_color)
        self.labelItems = dict()
        self.make_labels(self.ticks.push_values)

    def create_ticks(self, start, stop, scale):
        self.start = start
        self.stop = stop
        self.scale = scale    
        #self.thicks = tickValues(self.start, self.stop,  self.scale, 40, self.noDecimals)          
        self.ticks = Ticks(self.start, self.stop,  self.scale, 60, self.noDecimals)          
        
    @property
    def thicks(self):
        return self.ticks.values

    def update_labels(self, start, stop, scale, grid=False):
        self.start = start
        self.stop = stop
        self.scale = scale 
        
        self.ticks.update(start, stop, scale)                         
        self.remove_labels(self.ticks.pop_values)        
        self.make_labels(self.ticks.push_values, grid)
        
        if self.orientation == 0:
            self.axline.setLine(start, 0, stop, 0)
        else:
            self.axline.setLine(0, start, 0, stop)
        
    def init_bg(self, bg_color):
        if self.orientation == 0:
            self.bgrect = QtWidgets.QGraphicsRectItem(-1e6, 0, 2e6, 22, parent=self)
            self.axline = QtWidgets.QGraphicsLineItem(self.start, 0, self.stop, 0, parent=self)
                
        if self.orientation == 90:
            self.bgrect = QtWidgets.QGraphicsRectItem(0, -1e6, 22, 2e6, parent=self)
            self.axline = QtWidgets.QGraphicsLineItem(0, self.start, 0, self.stop, parent=self)
            
        if self.orientation == -90:
            self.bgrect = QtWidgets.QGraphicsRectItem(-22, -1e6, 22, 2e6, parent=self)
            self.axline = QtWidgets.QGraphicsLineItem(0, self.start, 0, self.stop, parent=self)
            
        self.bgrect.setFlags(QtWidgets.QGraphicsItem.ItemIgnoresTransformations)
        self.bgrect.setPen(QtGui.QPen(bg_color, 0))
        self.bgrect.setBrush(QtGui.QBrush(bg_color, QtCore.Qt.SolidPattern))
        
        self.axline.setPen(QtGui.QPen(QtGui.QColor(0,0,0), 0))
        

    def remove_labels(self, pop_values):
        if len(pop_values) == 0: 
            return
        for k in pop_values[0]:
            self.labelItems[k].setParentItem(None)
            self.labelItems.pop(k)        
        for k in pop_values[1]:
            self.labelItems[k].setParentItem(None)
            self.labelItems.pop(k)                    
        for k in pop_values[2]:
            self.labelItems[k].setParentItem(None)
            self.labelItems.pop(k)                    
                
    def make_labels(self, push_values, grid=False):
        if self.noDecimals:
            fmt = "%d"
        else:
            fmt = "%0.5g"                    
        
        if self.orientation == 0:
        
            for i in push_values[0]:
                i0 = LabelItem(fmt % i, 0, grid, self)
                i0.setPos(i, 0)
                self.labelItems[i] = i0
            
            for i in push_values[1]:
                i0 = LabelItem(fmt % i, 1, grid, self)
                i0.setPos(i, 0)
                self.labelItems[i] = i0
            
            for i in push_values[2]:        
                line = SubDivisionX(parent=self)
                line.setPos(i, 0)
                self.labelItems[i] = line
            
        if abs(self.orientation) == 90:
            for i in push_values[0]:
                if self.logscale:
                    v = 10**(i-1)
                else:
                    v = i
                i0 = LabelItem(fmt % v, 0, grid, self)            
                
                i0.setRightAlign()
                i0.setPos(0, i)
                i0.setRotation(-self.orientation)
                self.labelItems[i] = i0

            for i in push_values[1]:
                if self.logscale:
                    v = 10**(i-1)
                else:
                    v = i            
                i0 = LabelItem(fmt % v, 1, grid, self)            
                
                i0.setRightAlign()
                i0.setPos(0, i)
                i0.setRotation(-self.orientation)
                self.labelItems[i] = i0
                
            for i in push_values[2]:        
                line = SubDivisionY(parent=self)
                line.setPos(0, i)
                self.labelItems[i] = line


class Grid(QtWidgets.QGraphicsItemGroup):
    def __init__(self, ruler=None, parent=None, scene=None):
        super().__init__(parent=parent)      
        
        self.ruler = ruler      
        self.labelItems = dict()
        self.make_labels(self.ticks.push_values)                
        
    @property
    def ticks(self):
        return self.ruler.ticks

    @property        
    def orientation(self):
        return self.ruler.orientation

    def update_labels(self, grid=True):                        
        self.remove_labels(self.ticks.pop_values)        
        self.make_labels(self.ticks.push_values, grid)
          

    def remove_labels(self, pop_values):
        if len(pop_values) == 0: 
            return
        for k in pop_values[0]:
            self.labelItems[k].setParentItem(None)
            self.labelItems.pop(k)        
        for k in pop_values[1]:
            self.labelItems[k].setParentItem(None)
            self.labelItems.pop(k)                    
        for k in pop_values[2]:
            self.labelItems[k].setParentItem(None)
            self.labelItems.pop(k)                    
                
    def make_labels(self, push_values, grid=False):                         
        if self.orientation == 0:        
            for i in push_values[0]:
                i0 = GridItem(0, self)
                i0.setPos(i, 0)
                self.labelItems[i] = i0
            
            for i in push_values[1]:
                i0 = GridItem(1, self)
                i0.setPos(i, 0)
                self.labelItems[i] = i0
            
            for i in push_values[2]:        
                line = GridItem(2, self)
                line.setPos(i, 0)
                self.labelItems[i] = line
            
        if abs(self.orientation) == 90:
            for i in push_values[0]:
                i0 = GridItem(0, self)            
                i0.setPos(0, i)
                i0.setRotation(-self.orientation)
                self.labelItems[i] = i0

            for i in push_values[1]:
                i0 = GridItem(1, self)           
                i0.setPos(0, i)
                i0.setRotation(-self.orientation)
                self.labelItems[i] = i0
                
            for i in push_values[2]:        
                line = GridItem(2, self)
                line.setPos(0, i)
                line.setRotation(-self.orientation)
                self.labelItems[i] = line                  
               
            
class Axis(QtWidgets.QGraphicsLineItem):
    def __init__(self, plotAngle, start, stop, thicks, parent=None, scene=None):
        super().__init__(parent=parent)   
        if scene: scene.addItem(self)
        
        self.setLine(0, 0, 0, 0)
        
        self.start = start
        self.stop = stop
        self.thicks = thicks
        self.plotAngle = plotAngle        
        
        self.createAxis()
            
    def createAxis(self):   
        if self.plotAngle == 0:
            
            for thickLevel in range(len(self.thicks)):
                if self.thicks[thickLevel][0] > 15:
                    for i in self.thicks[thickLevel][1]:
                        label = yAxisLabel('%0.5g' % i, thickLevel, self)
                        label.setPos(0, i)
            
        else:
            
            for thickLevel in range(len(self.thicks)):
                if self.thicks[thickLevel][0] > 15:
                    for i in self.thicks[thickLevel][1]:
                        label = yAxisLabel('%0.5g' % i, thickLevel, self)
                        label.setPos(i, 0)
                        label.setRotation(-90)
