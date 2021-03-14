from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Qt

from .docks import DockBase
       
class AreaSplitterHandle(QtWidgets.QSplitterHandle):

    def mouseDoubleClickEvent(self, event):
        self.parent().distributeWidgets()        

class DockBox(QtWidgets.QSplitter, DockBase):
    SplitArea = 0
    PinArea = 1
    ScrollArea = 2

    def __init__(self, orientation):
        QtWidgets.QSplitter.__init__(self, orientation)
        
        pal = self.palette()     
        if orientation == Qt.Horizontal:
            pal.setColor(QtGui.QPalette.Background, QtGui.QColor(192,224,192))
        elif orientation == Qt.Vertical:
            pal.setColor(QtGui.QPalette.Background, QtGui.QColor(192,192,224))
        self.setPalette(pal)          
        
        self.pinarea = PinnedBox(orientation)
        self.scrollarea = ScrollBox(orientation)        
        
        super().addWidget(self.pinarea)
        super().addWidget(self.scrollarea)        
        
        self.collapsed = False
        self.scrollarea.hide()
        
    def createHandle(self):
        return AreaSplitterHandle(self.orientation(), self)         

    def addWidget(self, widget, area=PinArea, title=None):
        if area == DockBox.PinArea:
            self.pinarea.addWidget(widget)
            
        elif area == DockBox.ScrollArea:
            if self.scrollarea.count() == 0:
                self.scrollarea.show()
                self.setSizes([4,1], DockBox.SplitArea)
            self.scrollarea.addWidget(widget)
            
    def count(self, area=PinArea):
        if area == DockBox.SplitArea:
            return super().count()
            
        elif area == DockBox.PinArea:
            return self.pinarea.count()
            
        elif area == DockBox.ScrollArea:
            return self.scrollarea.count()          
        

    def moveToOtherArea(self, widget, area=None):
        if area is None:
            area_widget = widget.parent()
            while not isinstance(area_widget, (PinnedBox, ScrollBox)):
                area_widget = area_widget.parent()
            if isinstance(area_widget, PinnedBox):
                area = DockBox.ScrollArea
            elif isinstance(area_widget, ScrollBox):
                area = DockBox.PinArea
            
        if area == DockBox.ScrollArea:            
            self.addWidget(widget, area=DockBox.ScrollArea)
            
        elif area == DockBox.PinArea:
            self.scrollarea.removeWidget(widget)
            self.addWidget(widget, area=DockBox.PinArea)

    def distributeWidgets(self):
        sizes = self.pinarea.sizes()
        newsize = sum(sizes) // self.pinarea.count()
        sizes = [newsize] * self.pinarea.count()
        self.pinarea.setSizes(sizes)
        
    def setSizes(self, sizes, area=PinArea):
        if area == DockBox.SplitArea:
            super().setSizes(sizes)
            
        elif area == DockBox.PinArea:
            self.pinarea.setSizes(sizes)
            
        elif area == DockBox.ScrollArea:
            self.scrollarea.growbox.setSizes(sizes)    

    def sizes(self, area=PinArea):
        if area == DockBox.SplitArea:
            return super().sizes()

        elif area == DockBox.PinArea:
            return self.pinarea.sizes()

        elif area == DockBox.ScrollArea:
            return self.scrollarea.growbox.sizes()
    
    def currentIndex(self):
        return self.pinarea.currentIndex()
        
    def widget(self, index, area=PinArea):
        if area == DockBox.PinArea:
            return self.pinarea.widget(index)
            
        elif area == DockBox.ScrollArea:
            return self.scrollarea.growbox.widget(index)
            
    def show(self):        
        self.pinarea.show()
        
        if self.scrollarea.count() > 0:
            self.scrollarea.show()            
        else:
            self.scrollarea.hide()
            
        self.scrollarea.growbox.show()
        
        for pos in range(self.count(DockBox.PinArea)):
            widget = self.widget(pos, DockBox.PinArea)
            widget.show()
            
        for pos in range(self.count(DockBox.ScrollArea)):
            widget = self.widget(pos, DockBox.ScrollArea)
            widget.show()                           
            
        super().show()
        
    def setCurrentIndex(self, index):
        self.pinarea.setCurrentIndex(index)
    

class DockVBox(DockBox):

    def __init__(self):
        super().__init__(Qt.Vertical)
        
        
class DockHBox(DockBox):

    def __init__(self):
        super().__init__(Qt.Horizontal)   


class PinnedSplitterHandle(QtWidgets.QSplitterHandle):

    def mouseDoubleClickEvent(self, event):
        self.parent().distributeWidgets(self)
        

class PinnedBox(QtWidgets.QSplitter):

    def __init__(self, orientation):
        QtWidgets.QSplitter.__init__(self, orientation)

        pal = self.palette()     
        pal.setColor(QtGui.QPalette.Background, QtGui.QColor(192,192,192))
        self.setPalette(pal)
        
        self.atLeastOnePanel = True
        
    def collapse(self, widget):
        if self.atLeastOnePanel:        
            not_collapsed_widgets = [self.widget(pos) for pos in range(self.count()) if not self.widget(pos).collapsed]
            
            if not widget.collapsed and len(not_collapsed_widgets) == 1:
                widget.topleftbtn.setChecked(False)
                return        
            
        widget.collapseVertical()  
        
    def moveToOtherArea(self, widget):
        self.parent().moveToOtherArea(widget, DockBox.ScrollArea)
        
    def createHandle(self):
        return PinnedSplitterHandle(self.orientation(), self)   

    def distributeWidgets(self, handle):
        pos = self.indexOf(handle)
        
        sizes = self.sizes()
                        
        newsize = sum(sizes[pos-1:pos+1]) // 2
        sizes[pos-1] = newsize
        sizes[pos] = newsize        
        self.setSizes(sizes)           
        
        
class SplitterHandle(QtWidgets.QWidget):

    def __init__(self, orientation, space=5):
        super().__init__()
        self._orientation = orientation

        if orientation == Qt.Vertical:
            self.setCursor(QtGui.QCursor(QtCore.Qt.SplitVCursor))
            self.setFixedHeight(space)
            
        elif orientation == Qt.Horizontal:
            self.setCursor(QtGui.QCursor(QtCore.Qt.SplitHCursor))
            self.setFixedWidth(space)
            
    def orientation(self):
        return self._orientation
        
    def mouseDoubleClickEvent(self, event):
        self.parent().distributeWidgets(self)         
            
    def mouseMoveEvent(self, event):
        pos = self.parent().indexOf(self) - 1
            
        if self.orientation() == Qt.Vertical:
            delta = event.pos().y()
            self.parent().changeWidgetSize(pos, delta, delta=True)
            
        elif self.orientation() == Qt.Horizontal:
            delta = event.pos().x()
            self.parent().changeWidgetSize(pos, delta, delta=True)
        
        
class SplitBox(QtWidgets.QWidget):        

    def __init__(self, orientation):
        super().__init__()        
        self._orientation = orientation
        self.widgets = []
        self.handles = [None]
        self.space = 5
        
        if orientation == Qt.Vertical:
            layout = QtWidgets.QVBoxLayout()
            self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            
        elif orientation == Qt.Horizontal:
            layout = QtWidgets.QHBoxLayout()                    
            self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)

        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)            
        self.setLayout(layout)
        self.atLeastOnePanel = False
        
    def orientation(self):
        return self._orientation
        
    def addWidget(self, widget):
        if self.orientation() == Qt.Vertical:
            sizes = self.sizes() + [widget.height()]
            
        elif self.orientation() == Qt.Horizontal:
            sizes = self.sizes() + [widget.width()]        
            
        self.widgets.append(widget)    
        self.layout().addWidget(widget)
        handle = SplitterHandle(self.orientation(), self.space)
        self.handles.append(handle)
        self.layout().addWidget(handle)
        self.layout().setStretch(self.layout().count()-1, self.space)
        
        self.setSizes(sizes)
        
    def insertWidget(self, pos, widget):
        if self.orientation() == Qt.Vertical:
            prefered_height = widget.height()
            sizes = self.sizes()
            sizes.insert(pos, prefered_height)
            
        elif self.orientation() == Qt.Horizontal:  
            prefered_width = widget.width()
            sizes = self.sizes()
            sizes.insert(pos, prefered_width)
            
        self.widgets.insert(pos, widget)
        self.layout().insertWidget(pos*2, widget)  
        handle = SplitterHandle(self.orientation(), self.space)
        self.handles.insert(pos+1, handle)
        self.layout().insertWidget(pos*2+1, handle)
        self.layout().setStretch(pos*2+1, self.space)
        
        self.setSizes(sizes)             

    def resizeWidget(self, widget, size):
        if isinstance(widget, int):
            pos = widget
        else:
            pos = self.indexOf(widget)
            
        sizes = self.sizes()                             
        sizes[pos] = size        
        self.setSizes(sizes)       

    def removeWidget(self, widget):
        if isinstance(widget, int):
            pos = widget
        else:
            pos = self.indexOf(widget)
            
        sizes = self.sizes()
        sizes.pop(pos)            
            
        widget = self.widgets.pop(pos)
        self.layout().removeWidget(widget)
        handle = self.handles.pop(pos+1)        
        self.layout().removeWidget(handle)        
        widget.setParent(None)
        handle.setParent(None)
        
        self.setSizes(sizes)
            
        return widget

    def count(self):
        return len(self.widgets)
        
    def widget(self, index):
        return self.widgets[index]
        
    def indexOf(self, widget):
        try:
            return self.widgets.index(widget)
        except ValueError:
            pass
            
        try:
            return self.handles.index(widget)
        except ValueError:
            pass            
            
        return None

    def distributeWidgets(self, handle):
        pos = self.indexOf(handle)
        sizes = self.sizes()
        
        cmo = self.count()
        
        if pos == cmo:
            sizes = [sum(sizes[:cmo]) // cmo] * cmo
        else:                    
            newsize = sum(sizes[pos-1:pos+1]) // 2
            sizes[pos-1] = newsize
            sizes[pos] = newsize   
            
        self.setSizes(sizes) 
        
    def collapse(self, widget):
        if self.atLeastOnePanel:        
            not_collapsed_widgets = [self.widget(pos) for pos in range(self.count()) if not self.widget(pos).collapsed]
            
            if not widget.collapsed and len(not_collapsed_widgets) == 1:
                widget.topleftbtn.setChecked(False)
                return
                
        widget.collapseVertical()

    def sizes(self):
        if self.orientation() == Qt.Vertical:
            return [widget.height() for widget in self.widgets]
        elif self.orientation() == Qt.Horizontal:
            return [widget.width() for widget in self.widgets]
        #return self.stretches()
            
    def stretches(self):
        return [self.layout().stretch(index) for index in range(self.count()*2)]
        
    def setSizes(self, sizes):
        total_size = sum(sizes) + self.space * self.count()
        # print(f'Sizes:    Stretches: {self.stretches()}')
        # print(f'    Old: {self.sizes()}')
        # print(f'    New: {sizes}   Total: {total_size}')
        
        if self.orientation() == Qt.Vertical:
            self.setFixedHeight(total_size)
        elif self.orientation() == Qt.Horizontal:
            self.setFixedWidth(total_size)            
        for (i, stretch) in zip(range(self.count()), sizes):            
            self.layout().setStretch(i*2, stretch)
            
        # QtWidgets.QApplication.instance().processEvents()            
        # print(f'    Eff: {self.sizes()}')
        # QtWidgets.QApplication.instance().processEvents()
        
    def changeWidgetSize(self, pos_or_widget, size, delta=False, fixed=False):
        """
        Set the widget at pos to size.
        Adapt the size of the splitbox so no other widgets resizes
        """
        sizes = self.sizes()
        
        if isinstance(pos_or_widget, int):
            pos = pos_or_widget
            widget = self.widget(pos)
        else:
            pos = self.indexOf(pos_or_widget)
            widget = pos_or_widget      
            
        if self.orientation() == Qt.Vertical:                     
            widget_height = sizes[pos]
            if delta: size = widget_height + size
            new_widget_height = max(size, widget.minimumHeight()) 
            sizes[pos] = new_widget_height                       
            if fixed:
                widget.setFixedHeight(size)
            
        elif self.orientation() == Qt.Horizontal:                 
            widget_width = sizes[pos]            
            if delta: size = widget_width + size
            new_widget_width = max(size, widget.minimumWidth())            
            sizes[pos] = new_widget_width                       
            if fixed:
                widget.setFixedWidth(size)        

        self.setSizes(sizes)  
        
        

class ScrollBox(QtWidgets.QScrollArea):

    def __init__(self, orientation):
        QtWidgets.QScrollArea.__init__(self)
        
        self.setWidgetResizable(True)
        
        if orientation == Qt.Vertical:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            
        elif orientation == Qt.Horizontal:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        pal = self.palette()     
        pal.setColor(QtGui.QPalette.Background, QtGui.QColor(160,200,224))
        self.setPalette(pal)           
        
        self.growbox = SplitBox(orientation)
        self.setWidget(self.growbox)        

    def addWidget(self, widget):
        self.growbox.addWidget(widget)
        
    def removeWidget(self, widget):
        self.growbox.removeWidget(widget)
            
    def count(self):
        return self.growbox.count()
    
        
