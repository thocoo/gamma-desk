import collections
import importlib
import pprint
import logging
import pathlib

from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy import QtCore, QtGui, QtWidgets

from .. import gui, config
from .laystruct import LayoutStruct
from .dockwidgets import DockContainer, DockTab, DockTag

respath = pathlib.Path(config['respath'])
logger = logging.getLogger(__name__)

class HoverButton(QPushButton):
    icons = dict()
        
    def __init__(self, caption, parent):                
        if caption in HoverButton.icons.keys():
            super().__init__('', parent)
            self.setIcon(HoverButton.icons[caption])
        else:
            super().__init__(caption, parent)
        
        self.setAcceptDrops(True)
        
    @staticmethod
    def load_icons():
        HoverButton.icons['T'] = QtGui.QIcon(str(respath / 'icons' / 'dock_tab.png'))
        HoverButton.icons['L'] = QtGui.QIcon(str(respath / 'icons' / 'dock_left.png'))
        HoverButton.icons['R'] = QtGui.QIcon(str(respath / 'icons' / 'dock_right.png'))
        HoverButton.icons['U'] = QtGui.QIcon(str(respath / 'icons' / 'dock_up.png'))
        HoverButton.icons['B'] = QtGui.QIcon(str(respath / 'icons' / 'dock_bottom.png'))

    def enterEvent(self, event):
        self.startPreview()
        
    def leaveEvent(self, event):
        self.endPreview()        

    def dragEnterEvent(self, event):
        event.accept()
        self.startPreview()      
        
    def dragLeaveEvent(self, event):
        self.endPreview()

    def startPreview(self):
        self.parent().active_rect_index = self.rect_id        
        self.parent().repaint()
        
    def endPreview(self):
        self.parent().endPreview()      
        
    def dropEvent(self, event):
        position = event.pos()
        event.setDropAction(Qt.MoveAction)
        event.accept()  
        self.clicked.emit()


class DockOverlay(QWidget):
    def __init__(self, parent, tool=False):            
        self.tool = tool
        
        if self.tool:
            super().__init__(parent=None)                       
            self.container = parent
            self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)        
            self.setAttribute(Qt.WA_NoSystemBackground)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setWindowOpacity(1)
        
        else:        
            super().__init__(parent=parent)
            self.container = parent
            palette = QPalette(self.palette())
            palette.setColor(palette.Background, Qt.transparent)
            self.setPalette(palette)        
        
        #self.setMouseTracking(True)                        
        #self.rects = []
        self.active_rect_index = None
     
        self.hide()
        
        #font = QtWidgets.QApplication.instance().font()
        fontmetric = QtGui.QFontMetrics(self.font())
        fontheight = fontmetric.height()
        
        btnsize = int(round(fontheight * 2.5)) // 2 * 2
        
        #Size parameters of the buttons
        self.btnw = btnsize 
        self.btnh = btnsize
        self.btnb = btnsize // 2 + 2
        self.btnc = btnsize + 2
        
    @property
    def ezm(self):
        return self.container.manager        
        
    def show_and_insert(self, window, insert_node):
        self.insert_window = window
        self.insert_node = insert_node  
        container = self.container
        self.match_geometry(container)
        self.get_dock_and_button_positions(container)
        self.show()
        
    def find_best_fit(self, lower_container, upper_container):
        self.match_geometry(lower_container)
        rects = self.get_dock_positions(lower_container)
        
        pos = self.mapFromGlobal(upper_container.mapToGlobal(upper_container.pos()))
        x, y = pos.x(), pos.y()
        w, h = upper_container.width(), upper_container.height()
        
        diffs = []
        for tags_rect in rects:
            tags, rect = tags_rect
            caption, panqualid, btnpos = tags            
            rx, ry, rw, rh = rect[0], rect[1], rect[2], rect[3]
            diff = sum(((rx - x)**2         , (ry - y)**2,
                       (rx + rw - x - w)**2, (ry - y)**2, 
                       (rx - x)**2         , (ry + rh - y - h)**2,
                       (rx + rw - x - w)**2, (ry + rh - y - h)**2))
            diffs.append((len(diffs), diff))
                
        diffs = sorted(diffs, key= lambda item: item[1])
        lowest = diffs[0][0]
        return rects[lowest]
        
    def get_dock_and_button_positions(self, container):
        self.rects = self.get_dock_positions(container)
    
        self.buttons = []
        
        w, h = self.btnw, self.btnh
        
        for index, tags_rect in enumerate(self.rects):
            tags, rect = tags_rect
            caption, panqualid, pos = tags
            button = HoverButton(caption, self)                                    
            button.setGeometry(pos[0]- w//2, pos[1]- h//2, w, h)                               
            button.clicked.connect(self.endOverlay)
            button.rect_id = index
            
            self.buttons.append(button)

    def get_dock_positions(self, container):        
        rects = []
        
        spaceb = self.btnb
        spacec = self.btnc
        
        geo = self.geometry() 
        w, h = geo.width(), geo.height()
        rects.append((('U', ('top', None),    (w/2, spaceb  )), (0, 0    , w,   h/3)))
        rects.append((('B', ('bottom', None), (w/2, h-spaceb)), (0, 2*h/3, w,   h/3)))
        rects.append((('L', ('left', None),   (spaceb,  h/2 )), (0, 0,     w/3, h  )))
        rects.append((('R', ('right', None),  (w-spaceb,h/2 )), (2*w/3, 0, w/3, h  )))   
        
        panelrects = DockOverlay.get_dock_global_positions_branch(container.laywidget)    

        for panel, rect in panelrects:
            panqualid = (panel.category, panel.panid)            
            pos = self.mapFromGlobal(QtCore.QPoint(rect[0], rect[1]))
            posx = pos.x()
            posy = pos.y()
            w, h = rect[2], rect[3]
            xc, yc = posx + w/2, posy + h/2
            rects.append((('T', ('tab', panqualid),    (xc, yc   )), (posx, posy, w, h)))
            rects.append((('U', ('top', panqualid),    (xc, yc-spacec)), (posx, posy, w, h/2)))
            rects.append((('B', ('bottom', panqualid), (xc, yc+spacec)), (posx, posy + h/2, w, h/2)))
            rects.append((('L', ('left', panqualid),   (xc-spacec, yc)), (posx, posy, w/2, h)))
            rects.append((('R', ('right', panqualid),  (xc+spacec, yc)), (posx  + w/2, posy, w/2, h)))     

        return rects
        
    @staticmethod
    def get_dock_global_positions_branch(layout_widget):
        rects = []   
        
        if not (isinstance(layout_widget, (QSplitter, QScrollArea)) or isinstance(layout_widget, (DockTab, DockTag))):
            pos = layout_widget.mapToGlobal(layout_widget.pos())            
            return [(layout_widget, (pos.x(), pos.y(), layout_widget.width(), layout_widget.height()))]
        
        if isinstance(layout_widget, (QSplitter, QScrollArea)):
            for index in range(layout_widget.count()):
                widget = layout_widget.widget(index)
                rects.extend(DockOverlay.get_dock_global_positions_branch(widget))
                
        elif isinstance(layout_widget, (DockTab, DockTag)):
            widget = layout_widget.currentWidget()
            if not widget is None:
                rects.extend(DockOverlay.get_dock_global_positions_branch(widget))
            
        return rects        
        
    def match_geometry(self, window):
        if self.tool:
            geo = window.geometry()                        
            pos = window.mapToGlobal(geo.topLeft())
            self.setGeometry(pos.x(), pos.y(), geo.width(), geo.height())
        else:
            geo = window.geometry()
            w, h = geo.width(), geo.height()
            self.setGeometry(0, 0, w, h)
        
    def endOverlay(self):
        if not self.active_rect_index is None:
            tags, rect = self.rects[self.active_rect_index]     
            caption, panqualid, pos = tags            
            
        self.ezm.hide_overlays()      
        self.place_node(*panqualid)  

    def endPreview(self):
        self.active_rect_index = None       
        self.repaint()         
        
    def mousePressEvent(self, event):
        self.ezm.hide_overlays()
        geo = self.insert_window.geometry()
        geo.moveTo(QCursor.pos())
        self.insert_window.setGeometry(geo)   
        self.insert_window.show()

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(event.rect(), QBrush(QColor(255, 255, 255, 127)))
        
        if not self.active_rect_index is None:
            position, rect = self.rects[self.active_rect_index]
            painter.fillRect(*rect, QBrush(QColor(0, 255, 0, 127)))          
            
        painter.setPen(QPen(Qt.NoPen))
        
    def place_node(self, relative_pos, refpanqualid):  
        ls = self.container.get_layout_struct()
        ls.compact()
        ls.insert_branch(self.insert_node, relative_pos, refpanqualid)   
        #ls.compact()
        self.insert_window.container.update_layout(LayoutStruct())
        self.container.update_layout(ls)