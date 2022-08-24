import pathlib
import random
import logging
from collections import OrderedDict

from qtpy import QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QKeySequence, QIcon, QPixmap, QCursor
from qtpy.QtWidgets import QApplication, QWidget, QAction, QMainWindow, QMenu

from .. import gui, config
from ..gcore.utils import getMenuTrace, relax_menu_text, relax_menu_trace

logger = logging.getLogger(__name__)
respath = pathlib.Path(config['respath'])

class FuncToPanel(object):
    def __init__(self, func, *args):
        self.func = func
        self.args = args
                        
    def __call__(self):
        self.func(*self.args)
        
class CheckMenu(QtWidgets.QMenu):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        if not parent is None:
            parent.addMenu(self)
        self.action_checked_calls = []
        self.action_enable_calls = []
        
    def showEvent(self, event):
        for action, checked_call in self.action_checked_calls:
            action.setChecked(checked_call())
            
        for action, enable_call in self.action_enable_calls:
            action.setEnabled(enable_call())            
            
    def addAction(self, *args, **kwargs):
        action = super().addAction(*args, **kwargs)
        if action is None: action = args[0]
        if not kwargs.get('checkcall', None) is None:
            action.setCheckable(True)
            self.action_checked_calls.append((action, kwargs.get('checkcall')))
        if not kwargs.get('enablecall', None) is None:
            self.action_enable_calls.append((action, kwargs.get('enablecall')))            
        return action        

class PanelsMenu(QMenu):

    def __init__(self, parent, name, categories, func):
        super().__init__(name, parent)
        qapp = QApplication.instance() 
        self.panels = qapp.panels
        self.categories = categories
        self.panel = func.__self__
        self.func = func
        
    def showEvent(self, event):
        self.initactions()        

    def initactions(self):
        self.clear()
        
        self.actions = []
       
        for category in self.categories:
            if not category in self.panels.keys(): continue
            panels = self.panels[category]
            keys = sorted(panels.keys())
            for panid in keys:                                            
                if category == self.parent().category and panid == self.parent().panid: continue
                panel = panels[panid]
                action = QAction(panel.windowTitle())
                action.setCheckable(True)
                action.setChecked((category, panel.panid) in self.panel.bindings)
                action.triggered.connect(FuncToPanel(self.func, category, panel.panid))
                self.addAction(action)
                self.actions.append(action)  
                
            self.addSeparator()

class MyStatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent) 
        hboxlayout = QtWidgets.QHBoxLayout()
        hboxlayout.setContentsMargins(0, 0, 0, 0)               
        self.setLayout(hboxlayout)
        self.setMinimumWidth(100)             
        
        fontmetric = QtGui.QFontMetrics(self.font())
        fontheight = fontmetric.height()
        self.setFixedHeight(fontheight + 2)        

        pal = self.palette()  
        pal.setColor(QtGui.QPalette.Background, QtGui.QColor(192,192,192))     
        self.setPalette(pal)        
        self.setAutoFillBackground(True)
        
    def addWidget(self, widget, stretch=0, alignment=None):
        widget.setParent(self)
        if not alignment is None:
            self.layout().addWidget(widget, stretch, alignment) 
        else:
            self.layout().addWidget(widget, stretch) 

    def removeWidget(self, widget):
        widget.setParent(None)
        self.layout().removeWidget(widget)             
            
        
def thisPanel(widget):
    while not (isinstance(widget, BasePanel) or widget is None):    
        if hasattr(widget, 'container'):        
            if len(widget.container.panelIds) < 1:
                return None
                
            else:
                cat, panid = widget.container.panelIds[0]
                return gui.qapp.panels[cat][panid]
        elif hasattr(widget, 'parentWidget'):
            #Used by matplotlib widgets
            parent_attr = widget.parentWidget
        else:
            parent_attr = widget.parent            
        widget = parent_attr()
    return widget

def selectThisPanel(widget):
    thisPanel(widget).select()
       

class BasePanel(QMainWindow):
    panelCategory = None
    panelShortName = None
    userVisible = True
        
    def __init__(self, parent, panid=None, category='console'):
        super().__init__()        
        self.baseWindowName = None               
        
        self.category = category                
        #Also creates the category if not exists
        id_exists = self.qapp.panels.id_exists(self.category, panid)        
        if panid is None: panid = self.qapp.panels.new_id(self.category)
        self.panid = panid            
        self.qapp.panels[self.category][self.panid] = self                
        
        self.bindings = []
        
        self.long_title = self.short_title        
        self.setWindowTitle(self.short_title)
        
        self.setFocusPolicy(Qt.StrongFocus)
        #self.setAttribute(Qt.WA_DeleteOnClose, True)        
        
        self.use_global_menu = True
        #self.myMainWidget = MyMainWidget()
        #super().setCentralWidget(self.myMainWidget)
        
        selIcon = QIcon()
        selIcon.addFile(str(respath / 'icons' / 'mark_16px.png'), state=QIcon.On)
        selIcon.addFile(str(respath / 'icons' / 'unmark_16px.png'), state=QIcon.Off)        
        
        self.setAutoFillBackground(True)
        
        self.statusBar().setSizeGripEnabled(False)

    @property
    def qapp(self):
        return QApplication.instance() 

    @property
    def short_title(self):
        return f'{self.category}#{self.panid}'
    
    @property
    def baseWindow(self):
        #return self.qapp.windows.get(self.baseWindowName, None)        
        container = self.get_container()
        if not container is None:
            return container.parent()
        else:
            return None
            
    def duplicate(self, floating=False):             
        newpanel = gui.qapp.panels.new_panel(type(self), None, None, floating=floating)        
        return newpanel

    def addMenuItem(self, menu, text, triggered, checkcall=None, enabled=True, statusTip=None, icon=None, enablecall=None):
    
        menuTrace = getMenuTrace(menu)
        menuTrace.append(text)
        catMenyShortCuts = self.qapp.menuCallShortCuts.get(self.category, {})
        keySequence = catMenyShortCuts.get(relax_menu_trace(menuTrace), None)
        
        # if not keySequence is None:
            # Note that the \t will place the keySequence in a nice second column
            # Like a real shortcut
            # text = f'{text}\t[{keySequence}]'            
        
        action = QAction(text, self, enabled=enabled, statusTip=statusTip)
        #action = TriggerlessShortcutAction(text, self, enabled=enabled, statusTip=statusTip)
        action.triggered.connect(triggered)
        
        if not keySequence is None:
            action.setShortcut(QtGui.QKeySequence(keySequence))
            #Disable the shortcut,
            #it is handled by the qapp.panelsDialog window
            #Shortcuts are send to the correct selected panel
            action.setShortcutContext(Qt.WidgetShortcut)
        
        if isinstance(icon, str):
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / icon))
        
        if not icon is None:
            action.setIcon(icon)
            
        menu.addAction(action, checkcall=checkcall, enablecall=enablecall)      
        return action
    
    def addBaseMenu(self, bindCategories=[]):        
        self.bindMenu = PanelsMenu(self, 'bind to', bindCategories, self.toggleBindingTo)        
        self.menuBar().hide()        

    def toggleBindingTo(self, category, panid):
        added = self.addBindingTo(category, panid)
        if added is None:
            self.removeBindingTo(category, panid)        

    def addBindingTo(self, category, panid):        
        try:
            index = self.bindings.index((category, panid))            
            return None
        except ValueError:
            pass
            
        targetPanel = self.qapp.panels[category][panid]
        self.bindings.append((category, panid))
        
        return targetPanel

    def removeBindingTo(self, category, panid):
        try:
            index = self.bindings.index((category, panid))
        except ValueError:
            logger.debug(f'{category, panid} not in to the bindings')
            return None
            
        targetPanel = self.qapp.panels[category][panid]
        self.bindings.pop(index)       
        
        return targetPanel

    def panIdsOfBounded(self, category):
        return [bindpanid for bindcat, bindpanid in self.bindings if bindcat == category]
        
    def bindedPanel(self, category, pos=0):
        panids = self.panIdsOfBounded(category)
        if len(panids) == 0:
            return None
        return self.qapp.panels[category][panids[pos]]   

    def targetPanels(self, category):    
        panids = self.panIdsOfBounded(category)
        
        if len(panids) == 0:
            panel = gui.qapp.panels.selected(category)
            if not panel is None: return [panel]           

        else:
            return [self.qapp.panels[category][panid] for panid in panids]        
        
    def select(self):
        thisWasSelected = self.isSelected()
        self.qapp.panels.move_to_end(self)               
        
        if self.category in self.qapp.panels.ezm.bindGroups.keys():
            bindButton = self.qapp.panels.ezm.bindGroups[self.category].button(self.panid)
            if not bindButton is None:
                bindButton.setChecked(True)        

        if not self.use_global_menu:
            self.menuBar().show()            
        else:
            self.push_menu_to_main()           

        baseWindow = self.baseWindow
        if not baseWindow is None:
            baseWindow.setPanelInfo(self)      

        return thisWasSelected
        
    def isSelected(self):
        return self.qapp.panels.selected(self.category).panid == self.panid

    def push_menu_to_main(self):
        mainWindow = self.baseWindow 
        if mainWindow is None: return
        mainWindow.remove_panel_menu()                     
        
        for child in self.menuBar().children():            
            if isinstance(child, QMenu) and child.title() != '':  
                mainWindow.menuBar().addMenu(child)
                        
        self.menuBar().hide()

    def pull_menu_from_main(self):
        mainWindow = self.baseWindow
        if mainWindow is None: return
        menubar = self.menuBar()        
        mainWindow.remove_panel_menu()
        menubar.show()            

    def toggleMenu(self):
        self.use_global_menu = not self.use_global_menu
        self.select()
        
    def toggleStatusBar(self):
        statusBar = self.statusBar()
        if statusBar.isVisible():
            statusBar.hide()
        else:
            statusBar.show()        

    def detach(self):
        statusBar = self.statusBar()            
        self.setParent(None)          
        
        if self.use_global_menu:
            self.pull_menu_from_main()                                  

    def show_me(self):        
        container = self.get_container()
        if not container is None:
            window = container.parent()
            if window.isMinimized():
                window.showNormal()
            else:
                window.show()
            window.raise_()
            gui.qapp.setActiveWindow(window)            
        else:
            self.show()

    def unregister(self):
        self.qapp.panels[self.category].pop(self.panid)

    @classmethod
    def userPanelClasses(cls):
        l = []
        for SubClass in cls.__subclasses__():
            l.extend(SubClass.userPanelClasses())
            l.append((SubClass.panelCategory, SubClass))
            
        if cls is BasePanel:
            result = dict()
            
            for category, Cls in l:
                if not category in result.keys():
                    result[category] = []
                result[category].append(Cls)
            return result
        else:
            return l      

    def get_container(self):                
        from ..ezdock.ezdock import DockContainer
        
        candidate = self        
        while not (candidate is None or isinstance(candidate, DockContainer)):
            candidate = candidate.parent()
        return candidate        
        
    def mousePressEvent(self, event):
        self.select()

    def close_panel(self):
        container = self.get_container()
        window, laystruct = container.detach('panel', self.category, self.panid, False)
        self.qapp.processEvents()
        self.qapp.panels.removeBindingsTo(self.category, self.panid)
        self.unregister()
        window.unregister()       
        self.deleteLater()
        window.deleteLater()
