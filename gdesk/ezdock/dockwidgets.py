import collections
import importlib
import pprint
import logging
import pathlib
from functools import partial

from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy import QtCore, QtGui, QtWidgets

from .. import gui, config

from ..panels.base import BasePanel

from .laystruct import LayoutStruct
from .docks import DockBase
from .boxes import DockHBox, DockVBox, DockBox

respath = pathlib.Path(config['respath'])
logger = logging.getLogger(__name__)

DEBUG = {'Use_ScrollBox': True}


class DockTabBar(QTabBar):

    def __init__(self, *args, **kwargs):        
        super().__init__(*args, **kwargs)                
        self.setMovable(True) 

        fontmetric = QtGui.QFontMetrics(self.font())
        self.fontheight = fontmetric.height()       

        self.movingWindow = None
        self.movingWindowOffset = None
        self.drag_start_pos = None

    def add_tab_menu(self, index, leftWidget, rightWidget=None):                
        if index >= 0:
            if not leftWidget is None:
                self.setTabButton(index, QTabBar.LeftSide, leftWidget)            
            if not rightWidget is None:
                self.setTabButton(index, QTabBar.RightSide, rightWidget)

    def mouseDoubleClickEvent(self, event):
        widget = self.parent().currentWidget()
        container = widget.get_container()        
        globalpos = widget.mapToGlobal(self.pos())
        
        if event.modifiers() == 0:            
            window, node = self.detach()
            if not window is container.parent():
                window.move(globalpos)
            return                

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        widget = self.parent().currentWidget()        
        self.drag_start_pos = event.pos()
        
        if isinstance(widget, BasePanel): 
            if event.button() == Qt.LeftButton:   
                widget.select()  

    def mouseReleaseEvent(self, event):        
        widget = self.parent().currentWidget()
        
        if event.button() == Qt.RightButton:
            if not self.movingWindow is None:
                self.movingWindow.windowPlaced()
                self.movingWindow = None
                
            elif isinstance(widget, BasePanel):
                #Show the panel menu
                menu = QMenu('menu')
                for child in widget.menuBar().children():
                    #One of the QMenu children seems to be itself
                    if isinstance(child, QMenu) and child.title() != '':
                        menu.addMenu(child)                        
                menu.exec_(QCursor.pos())
        else:
            super().mouseReleaseEvent(event)    

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is None:
            self.drag_start_pos = event.pos()
            return

        movePoint = self.drag_start_pos - event.pos()
        moveDistance = movePoint.x() ** 2 + movePoint.y() ** 2
        if event.buttons() == Qt.RightButton and moveDistance > 32:
            if self.movingWindow is None:
                pos = self.mapToGlobal(QPoint(0, 0))
                self.movingWindowOffset = QtGui.QCursor.pos() - pos
                window, node = self.detach()
                window.startMoving()
                self.movingWindow = window
            else:
                self.movingWindow.move(QtGui.QCursor.pos() - self.movingWindowOffset)
        else:
            super().mouseMoveEvent(event)

    def detach(self):
        if isinstance(self.parent(), DockTag):
            widget = self.parent()
            
        elif isinstance(self.parent(), DockTab):
            widget = self.parent().currentWidget()
            
        if isinstance(widget, BasePanel):
            #It this case still used?
            logger.debug('Detaching BasePanel')            
            container = self.parent().get_container()
            geo = widget.geometry()
            window, node = container.detach('panel', widget.category, widget.panid, True, geo.width(), geo.height())
        else:
            logger.debug('Detaching Layout')
            window, node = widget.detach()
        
        return window, node        


class DockTabBase(DockBase, QTabWidget):

    def __init__(self, parent=None, collapse=None):
        QTabWidget.__init__(self, parent=parent)                 
        
        if DEBUG['Use_ScrollBox']:
            self.toprightbtn = QtWidgets.QToolButton(self)
            self.toprightbtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'application_split.png')))
            #self.toprightbtn.setText('...')
            self.toprightbtn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
            self.setCornerWidget(self.toprightbtn, Qt.TopRightCorner)
            self.pinMenu = QtWidgets.QMenu('pin')            
            if config.get("scroll_area", False):
                self.pinMenu.addAction(QtWidgets.QAction('Move to Pinned/Scroll Area', self, triggered=self.moveToOtherArea))            
            self.pinMenu.addAction(QtWidgets.QAction('Duplicate', self, triggered=self.duplicate,
                icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'application_double.png'))))
            self.pinMenu.addAction(QtWidgets.QAction('Split Horizontal', self, triggered=self.splitHorizontal,
                icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'layouts_split.png'))))           
            self.pinMenu.addAction(QtWidgets.QAction('Split Vertical', self, triggered=self.splitVertical,
                icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'layouts_split_vertical.png'))))
            self.pinMenu.addSeparator()
            action = QtWidgets.QAction('Screenshot to Clipboard', self, triggered=self.screenShot)
            action.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'lcd_tv_image.png')))
            self.pinMenu.addAction(action)            
            self.pinMenu.addAction(QtWidgets.QAction('Toggle global Menu usage', self, triggered=self.toggleMenu,
                icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'menubar.png'))))
            self.pinMenu.addAction(QtWidgets.QAction('Show/Hide Status Bar', self, triggered=self.toggleStatusBar,
                icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'status_bar.png'))))
            self.toprightbtn.setMenu(self.pinMenu)
        
        if collapse == 'h':
            self.topleftbtn = QtWidgets.QToolButton(self)
            self.topleftbtn.setIcon(gui.qapp.resizeicon)
            self.topleftbtn.setCheckable(True)
            self.topleftbtn.setDisabled(True)
            #self.topleftbtn.clicked.connect(self.toggleHorizontalContent)
            self.setCornerWidget(self.topleftbtn, Qt.TopLeftCorner)
            
        elif collapse == 'v':
            self.topleftbtn = QtWidgets.QToolButton(self)
            self.topleftbtn.setIcon(gui.qapp.resizeicon)
            self.topleftbtn.setCheckable(True)
            self.topleftbtn.clicked.connect(lambda: self.parent().collapse(self))
            self.setCornerWidget(self.topleftbtn, Qt.TopLeftCorner)
            
        self.setTabBarAutoHide(False)  
        self.setTabBar(DockTabBar())        
        
        self.title = None   
        self.setAutoFillBackground(True)                
        
        self.collapsed = False
        
    def duplicate(self):
        panel = self.currentWidget()
        newpanel = panel.duplicate()
        newpanel.show_me()
        
    def splitHorizontal(self):
        panel = self.currentWidget()    
        container = panel.get_container()        
        newpanel = panel.duplicate(floating=True)        
        container.insert((newpanel.category, newpanel.panid), 'right', (panel.category, panel.panid))                
        return panel.panid
        
    def splitVertical(self):
        panel = self.currentWidget()
        container = panel.get_container()
        newpanel = panel.duplicate(floating=True)
        container.insert((newpanel.category, newpanel.panid), 'bottom', (panel.category, panel.panid))        
        return panel.panid
        
    def moveToOtherArea(self):
        self.get_dock_box().moveToOtherArea(self)
        
    def collapseVertical(self):
        if self.collapsed:
            for pos in range(self.count()):
                self.widget(pos).show()            
            self.setMinimumHeight(self.priorMinimumHeight)
            self.setMaximumHeight(self.priorMaximumHeight)
            try:
                self.parent().changeWidgetSize(self, self.priorHeight, fixed=False)
            except:
                pass
                
            self.collapsed = False
            self.topleftbtn.setChecked(False)
        else:
            for pos in range(self.count()):
                self.widget(pos).hide()
            self.priorMinimumHeight = self.minimumHeight()
            self.priorMaximumHeight = self.maximumHeight()
            self.priorHeight = self.height()
            tabbarheight = self.tabBar().height()
            try:
                self.parent().changeWidgetSize(self, tabbarheight, fixed=True)
                self.setFixedHeight(tabbarheight)
            except:
                self.setFixedHeight(tabbarheight)
            self.collapsed = True
            self.topleftbtn.setChecked(True)                     

    def refresh_bind_menu(self, bindButton, *args, **kwargs):
        # Trick: first enforce a refresh of the bind menu.
        # Then show it.
        # Previously, code was relying on showEvent() being called to do the refresh,
        # but recent PySide versions seem to have more agressive caching.
        bindButton.menu().refresh()
        bindButton.showMenu()

    def set_tab_header(self, widget, title):
        # Bind button is the 'chain links' button.
        # It comes with a pop-up menu which is the 'bind' menu.
        index = self.indexOf(widget)
        
        bindButton = QToolButton(widget)
        bindButton.setIcon(gui.qapp.bindicon)
        #bindButton.setFixedHeight(26)
        bindButton.setCheckable(True)
        
        if widget.isSelected():            
            bindButton.setChecked(True)
       
        bindButton.clicked.connect(widget.select)

        # Extra auto-refresh.
        refresh_bind_button_menu = partial(self.refresh_bind_menu, bindButton)
        bindButton.clicked.connect(refresh_bind_button_menu)

        bindButton.setPopupMode(QToolButton.MenuButtonPopup)
        bindButton.setMenu(widget.bindMenu)           
        bindButton.setFixedHeight(self.tabBar().fontheight + 4)
        
        gui.qapp.panels.ezm.add_button_to_bindgroup(widget.category, widget.panid, bindButton)
                
        self.tabBar().add_tab_menu(index, bindButton, None)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self.get_container().parent().panelMenu.exec_(QCursor.pos())
        super().mouseReleaseEvent(event)        
        
    def screenShot(self):      
        pixmap = self.currentWidget().grab()
        qimage = pixmap.toImage()
        clipboard = gui.qapp.clipboard()
        clipboard.setImage(qimage)        
        
    def toggleMenu(self):
        panel = self.currentWidget()
        panel.use_global_menu = not panel.use_global_menu
        panel.select()    

    def toggleStatusBar(self):
        panel = self.currentWidget()
        statusBar = panel.statusBar()
        if statusBar.isVisible():
            statusBar.hide()
        else:
            statusBar.show()           
        
        
class DockTab(DockTabBase):
    category = 'tab'
    
    def __init__(self, parent=None, collapse=None):
        super().__init__(parent, collapse)  
        self.setStyleSheet("QTabBar::tab { height: " +  str(self.tabBar().fontheight + 6) + ";}")        
        
    def addWidget(self, widget, title=None):
        if isinstance(widget, BasePanel):
            self.addTab(widget, title)       
            self.set_tab_header(widget, title)
        else:
            self.addTab(widget, title)

class DockTag(DockTabBase):
    category = 'tag'
    def __init__(self, parent=None, collapse=None):
        super().__init__(parent, collapse)

    def addWidget(self, widget, title=None):
        self.addTab(widget, title)

        if title.startswith('vbox'):
            self.setTabPosition(QTabWidget.West) 
            pal = self.palette()     
            pal.setColor(QPalette.Base, QColor(192,192,224))
            self.setPalette(pal)

        elif title.startswith('hbox'):
            pal = self.palette()     
            pal.setColor(QPalette.Base, QColor(192,224,192))
            self.setPalette(pal)

        else:
            self.setStyleSheet("QTabBar::tab { height: " +  str(self.tabBar().fontheight + 6) + ";}")
            pal = self.palette()     
            pal.setColor(QPalette.Base, QColor(242,242,242))
            self.setPalette(pal)     

        if isinstance(widget, BasePanel):    
            self.addTab(widget, title)       
            self.set_tab_header(widget, title)
        else:
            self.addTab(widget, title)    


class DockContainer(QWidget):
    def __init__(self, manager, parent=None, name='main'):
        super().__init__(parent=parent)        
        
        #QWidget needs a top level QLayout object
        #Note that a QSplitter is not a QLayout object
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.taglevel = None
        
        self.setLayout(layout)   
        
        self.manager = manager
        self.name = name
        self.laywidget = None
        
        self.panelIds = []
        
        self.tabindex = 0
        self.vboxindex = 0
        self.hboxindex = 0 

    @property
    def all_panels(self):
        return self.manager.panels

    def is_empty(self, check=False):
        if check:
            return self.get_layout_struct().is_empty()
        else:
            return len(self.panelIds) == 0
            
    def panel_count(self):
        return len(self.panelIds)

    def update_layout(self, layout_struct):    
        if not self.laywidget is None:
            self.detach_panels()
            self.layout().removeWidget(self.laywidget)               
            
        self.tabindex = 0
        self.vboxindex = 0
        self.hboxindex = 0
        parentnode = {'type': 'layout', 'category': 'root'}                        
        
        if self.taglevel is None:
            if layout_struct.root.get('type', None) == 'panel' and config.get("hide_solo_panel", False):
                self.taglevel = 0
            else:
                self.taglevel = 1
            
        self.laywidget = self.make_layout_widget_branch(layout_struct.root, parentnode)
        self.laywidget.show()        
        #self.show_all(self.laywidget)
        
        self.layout().addWidget(self.laywidget)        

    def detach_panels(self):        
        for cat, panid in self.panelIds:
            try:
                panel = self.all_panels[cat][panid]
                panel.detach()                
            except KeyError:
                print(f'Could not find panel {cat}#{panid}')                
        self.panelIds.clear()  

    def detach_top(self):
        l = self.get_layout_struct()
        return self.detach(l.root['type'], l.root['category'], l.root['id'], False)

    def detach(self, nodetype, category, nodeid, to_new_window=True, width=640, height=480):                
        drop_layout = self.get_layout_struct()         
        place_layout = drop_layout.pop_node(nodetype, category, nodeid)  #tag or tab?
        
        drop_layout.compact()    
        place_layout.compact()
        
        if drop_layout.is_empty():
            return self.parent(), place_layout        
        
        self.update_layout(drop_layout)                           
        window = self.manager.new_window_using_layout(place_layout, width, height, self.parent().name)
        
        return window, place_layout

    def compact(self):
        ls = self.get_layout_struct()
        ls.compact()
        self.update_layout(ls)

    def distribute(self):
        ls = self.get_layout_struct()
        ls.compact()
        ls.distribute()
        self.update_layout(ls)
        
    def insert(self, panel, relative_pos, to_panel):
        """
        :param dict insert_node: (category, panid)
        :param str relative_pos: 'tab', 'top', 'bottom', 'left' or 'right'
        :param refpanqualid: (category, panid)
        """        
        ls = self.get_layout_struct()
        ls.compact()
        ls.insert_panel(panel, relative_pos, to_panel)   
        self.update_layout(LayoutStruct())
        self.update_layout(ls)        

    def make_layout_widget_branch(self, node, parentnode=None, ind=None):
        if len(node.keys()) == 0:
            lay = DockTab()
            return lay
            
        elif node['type'] == 'panel': 
            #No layout required at all
            cat = node['category']
            panid = node['id']
            panel = self.all_panels[cat][panid]
            panel.title = panel.short_title            
            self.panelIds.append((cat, panid))
            lay = panel
            
        elif node['type'] == 'layout':
            if node['category'] == 'hbox':
                self.hboxindex += 1
                lay = DockHBox()
                lay.title = f'hbox#{self.hboxindex}'
                
            elif node['category'] == 'vbox':
                self.vboxindex += 1
                lay = DockVBox()
                lay.title = f'vbox#{self.vboxindex}'

            elif node['category'] == 'tab':            
                self.tabindex += 1
                if parentnode['category'] == 'hbox':
                    lay = DockTab(None, 'h')
                elif parentnode['category'] == 'vbox':
                    lay = DockTab(None, 'v')
                else:
                    lay = DockTab()
                lay.title = f'tab#{self.tabindex}'                         
                
            else:
                raise TypeError(f'Unknown node category {node}')
        else:
            raise TypeError(f'Unknown node type {node}')
            
        lay.nodeinfo = {'parent': parentnode, 'index': ind}

        if isinstance(lay, DockBox):
            items = node.get('items', [])
            pin_sizes = node.get('sizes', [])
            scroll_sizes = node.get('scroll', [])
            areas = len(pin_sizes) * [DockBox.PinArea] + len(scroll_sizes) * [DockBox.ScrollArea]
            for ind, (item, area) in enumerate(zip(items, areas)):
                branch = self.make_layout_widget_branch(item, node, ind)
                lay.addWidget(branch, area=area, title=branch.title)            
        else:
            for ind, item in enumerate(node.get('items', [])):
                branch = self.make_layout_widget_branch(item, node, ind)
                lay.addWidget(branch, title=branch.title)

        if node['type'] == 'layout':
            if 'sizes' in node.keys():
                lay.setSizes(node['sizes'])
                
            if 'scroll' in node.keys():
                lay.setSizes(node['scroll'], area=DockBox.ScrollArea)    

            if 'pinscroll' in node.keys():
                lay.setSizes(node['pinscroll'], area=DockBox.SplitArea)                
                
            if 'active' in node.keys():               
                lay.setCurrentIndex(node['active'])
            
        if parentnode['category'] == 'tab':
            return lay
            
        if (node['type'] == 'panel' and self.taglevel in [0,1]) or self.taglevel == 2:
            if parentnode['category'] == 'hbox':
                tag = DockTag(None, 'h')
            elif parentnode['category'] == 'vbox':
                tag = DockTag(None, 'v')
            else:
                tag = DockTag()
                
            if self.taglevel == 0:
                tag.setTabBarAutoHide(True)
                
            tag.title = lay.title
            tag.addWidget(lay, title=lay.title)
            lay = tag
                
        return lay    

    def get_layout_struct(self):
        layout_widget = self.laywidget
        
        if not layout_widget is None and layout_widget.parent() == self:
            root = DockContainer.from_layout_widget_branch(layout_widget)
            ls = LayoutStruct()
            ls.root = root            
        else:
            ls = LayoutStruct()
        return ls                   
    
    @staticmethod
    def from_layout_widget_branch(layout_widget):
        node = {}
        
        if isinstance(layout_widget, (DockHBox, DockVBox)):
            if layout_widget.orientation() == Qt.Orientation.Horizontal:
                node['type'] = 'layout'
                node['category'] = 'hbox'
                node['id'] = layout_widget.title
            else:
                node['type'] = 'layout'
                node['category'] = 'vbox'
                node['id'] = layout_widget.title
                
            node['sizes'] = layout_widget.sizes()
            
            try:
                node['pinscroll'] = layout_widget.sizes(DockBox.SplitArea)
                node['scroll'] = layout_widget.sizes(DockBox.ScrollArea)
            except:
                pass
                
        elif isinstance(layout_widget, DockTab):
            node['type'] = 'layout'
            node['category'] = 'tab'
            node['id'] = layout_widget.title
            node['active'] = layout_widget.currentIndex()
                
        elif isinstance(layout_widget, DockTag):
            node['type'] = 'layout'
            node['category'] = 'tag'
            node['id'] = layout_widget.title            
                
        else:
            panel = layout_widget
            node = {'type': 'panel', 'category': panel.category, 'id': panel.panid}
            return node
            
        node['items'] = []
        
        if isinstance(layout_widget, DockBox):        
            for index in range(layout_widget.count(DockBox.PinArea)):
                widget = layout_widget.widget(index, DockBox.PinArea)
                subnode = DockContainer.from_layout_widget_branch(widget)
                node['items'].append(subnode)     

            for index in range(layout_widget.count(DockBox.ScrollArea)):
                widget = layout_widget.widget(index, DockBox.ScrollArea)
                subnode = DockContainer.from_layout_widget_branch(widget)
                node['items'].append(subnode) 

        else:
            for index in range(layout_widget.count()):
                widget = layout_widget.widget(index)
                subnode = DockContainer.from_layout_widget_branch(widget)
                node['items'].append(subnode)                 
            
        return node     

    def show_all(self, layout_widget):
        if not (isinstance(layout_widget, QSplitter) or isinstance(layout_widget, (DockTab, DockTag))):
            layout_widget.show()
            
        else:        
            for index in range(layout_widget.count()):
                widget = layout_widget.widget(index)
                self.show_all(widget)
                
    def cycle_tag_level(self):
        if len(self.panelIds) < 2:
            self.taglevel = (self.taglevel + 1) % 2
        else:
            self.taglevel = (self.taglevel + 1) % 3
        self.compact()        
