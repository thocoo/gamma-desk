import sys, io
import os
import threading
import time
from pathlib import Path
from collections import OrderedDict
import logging
import psutil
import pprint
import enum

from qtpy import QtCore, QtGui, QtWidgets

from qtpy.QtCore import (QFile, QFileInfo, QPoint, QSettings, QSignalMapper, QTimer,
        QSize, QTextStream, Qt, QObject, QMetaObject, Slot, QUrl, QByteArray)
from qtpy.QtGui import QIcon, QKeySequence, QPixmap
from qtpy.QtWidgets import (QAction, QApplication, QFileDialog, QMainWindow,  QShortcut, QDialog, QLabel,
        QMdiArea, QMessageBox, QTextEdit, QWidget, QStyle, QStyleFactory, QActionGroup, QButtonGroup)                
from qtpy.QtWidgets import QMenu, QDockWidget, QListWidget
from qtpy import QtWidgets

from .. import config, gui

from .base import CheckMenu
from ..ezdock import overlay
from ..gcore.utils import getMenuAction, relax_menu_trace, relax_menu_text
from ..dialogs.main import NewPanelMenu, ShowMenu, WindowMenu
from ..dialogs.formlayout import fedit
from ..dialogs.about import AboutScreen

respath = Path(config['respath'])
logger = logging.getLogger(__name__)         
        
def debug_print(message):
    sys.__stdout__.write(f'{message}\n')
    sys.__stdout__.flush()        
    
class DragState(enum.Enum):
    placed = enum.auto()
    titlePressed = enum.auto()
    dragging = enum.auto()
    
        
class MainWindow(QMainWindow):
    """
    The Main QT Window.    
    """
    
    moveQueued = QtCore.Signal(object)
    
    def __init__(self, qapp, name, parentWinName=None):
        super(MainWindow, self).__init__()
        
        self.qapp = qapp
        self.name = name
        
        self.panels = qapp.panels              
        self.dragState = DragState.placed
        self.qapp.panels.ezm
        
        if not parentWinName is None:        
            self.setParent(self.qapp.windows[parentWinName])
            self.setWindowFlags(self.windowFlags() | Qt.Tool)             
            #self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        self.container = self.qapp.panels.ezm.new_container(self, self.name)    
        self.setCentralWidget(self.container)
                
        self.setWindowTitle(f'[{self.name}]')
        
        self.createMenus()
        self.createStatusBar()       
        
        #Hiding panelsDialog will disable all shortcuts
        sc = QShortcut(QKeySequence("Ctrl+Shift+Alt+F12"), self, 
            lambda: self.qapp.panelsDialog.setVisible(not self.qapp.panelsDialog.isVisible()))
        sc.setContext(Qt.ApplicationShortcut)

        self.moveQueued.connect(self.moveWindow, Qt.QueuedConnection)                
        
        self.activeCategory = None
        self.activePanId = None
        self.priorHoverButton = None
        
    def moveWindow(self, pos):
        self.move(pos)
        
    def setPanelInfo(self, panel=None):
        if panel is None:
            self.setWindowTitle(f'[{self.name}]')
            self.panelName.setText('')        
            self.activeCategory = None
            self.activePanId = None
            return
            
        self.setWindowTitle(f'[{self.name}] {panel.long_title}')
        self.panelName.setText(panel.short_title)        
        self.activeCategory = panel.category
        self.activePanId = panel.panid
                        
    def keyPressEvent(self, event):
        pass        
                        
    def createMenus(self):      
        self.layoutMenu = QtWidgets.QMenu()        
        
        panDiaAct = QAction("Panels Dialog", self, triggered=self.qapp.showDialog)
        panDiaAct.setIcon(QIcon(str(respath / 'icons' / 'px16' / 'application_view_gallery.png')))
        self.layoutMenu.addAction(panDiaAct)
        self.newPanelMenu = NewPanelMenu(self, showIcon=True)
        self.layoutMenu.addMenu(self.newPanelMenu)  
        
        self.panelMenu = ShowMenu(self, showIcon=True)
        self.layoutMenu.addMenu(self.panelMenu)       
        self.layoutMenu.addMenu(WindowMenu(self, showIcon=True))
        
        def addWindowMenuItem(caption, function, icon=None):
            keySequence = self.qapp.menuCallShortCuts.get('window', {}).get((relax_menu_text(caption),), None)
            if not keySequence is None:
                caption = f'{caption}\t{keySequence}'
            if isinstance(icon, str):
                icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / icon))
            if not icon is None:
                action = QAction(caption, self.windowMenu, triggered=function, icon=icon)
            else:
                action = QAction(caption, self.windowMenu, triggered=function)
            self.windowMenu.addAction(action)
        
        self.windowMenu = CheckMenu("&Layout Edit")
        self.windowMenu.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'layout_edit.png')))
        self.layoutMenu.addMenu(self.windowMenu)                   
            
        self.toolWinAction = QAction(self.winActionLabel(), self, triggered=self.asToolWindow)
        self.windowMenu.addActionWithCallback(self.toolWinAction, checkcall=self.isToolWindow)
            
        addWindowMenuItem("Distribute", self.container.distribute, 'layouts_six_grid.png')        
        addWindowMenuItem("Drop In", lambda: self.qapp.panels.ezm.drop_in(self.container),
            'layouts_body_select.png')
        addWindowMenuItem("Screenshot to Clipboard", self.screenShot, 'lcd_tv_image.png')
        addWindowMenuItem("Cycle Tag Level", self.cycle_tag_level)
        addWindowMenuItem("Full Screen", self.fullScreen, 'view_fullscreen_view.png')
        addWindowMenuItem("Hide/Show Menu && Statusbar", self.toggleMenuStatusbar)                  
        addWindowMenuItem('Save Layout...', self.qapp.panelsDialog.layoutMenu.saveLayout)
        
        self.layoutMenu.addSeparator()
        self.qapp.panelsDialog.layoutMenu.addLayoutActions(self.layoutMenu)
        self.layoutMenu.addSeparator()

        act = QAction("E&xit", self, shortcut=QKeySequence.Quit,
            statusTip="Exit the application",
            triggered=QApplication.instance().quit)
        act.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'door_out.png')))
        self.layoutMenu.addAction(act)        
        
        self.panelsDialogBtn = QtWidgets.QToolButton(self)
        self.panelsDialogBtn.setIcon(QIcon(str(respath / 'icons' / 'px16' / 'application_view_gallery.png')))
        self.panelsDialogBtn.clicked.connect(self.qapp.showDialog)   
        self.panelsDialogBtn.setMenu(self.layoutMenu)
        self.panelsDialogBtn.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup) 
        self.menuBar().setCornerWidget(self.panelsDialogBtn, corner= Qt.TopLeftCorner)
        
        self.cycleTabBtn = QtWidgets.QToolButton(self)
        self.cycleTabBtn.setIcon(QIcon(str(respath / 'icons' / 'px16' / 'layout_content.png')))
        self.cycleTabBtn.clicked.connect(self.cycle_tag_level)
        self.cycleTabBtn.setMenu(self.windowMenu)
        self.cycleTabBtn.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)        
        self.menuBar().setCornerWidget(self.cycleTabBtn, corner= Qt.TopRightCorner)
        
    @property
    def windowName(self):
        return self.name        
        
    def cycle_tag_level(self):
        self.container.cycle_tag_level()
        
    def remove_panel_menu(self):
        main_childs = []
        for main_child in self.menuBar().children():
            main_childs.append(main_child)        
    
        self.menuBar().clear()

        for child in main_childs:
            if isinstance(child, QMenu):         
                self.menuBar().addMenu(child)  

    def screenShot(self):      
        pixmap = self.grab()
        qimage = pixmap.toImage()
        clipboard =  self.qapp.clipboard()
        clipboard.setImage(qimage)        
        
    def asToolWindow(self, windowName=None):
    
        if (not self.isToolWindow()) and windowName is None:
            winNames = [winname for winname, window in gui.qapp.windows.items()
                if not (window.isToolWindow() or winname == self.name)]
            winNames.append('None')
            winNameIndex = fedit([('Window', [1]+winNames)])[0]            
            winName = winNames[winNameIndex-1]            
        else:
            winName = windowName
            
        assert winName != self.name
        
        if winName in [None, 'None']:            
        
            self.setWindowFlags(self.windowFlags() & ~Qt.Tool)
            self.setParent(None)
            #setParent doc: Sets the parent of the widget to parent , and resets the window flags.
            self.toolWinAction.setText(self.winActionLabel())            
            
            #BUG
            # It seems that the window don't accept panel drops anymore
            # Only windows which had parent=None at __init__, seems to accept panel drops
            # Or windows with parent != None
            # But not windows are not reparent to None          
            # Removing the Tool flag before setting parent to None seems to solve it
            
            self.show()
            return
    
        self.setParent(self.qapp.windows[winName])
        self.toolWinAction.setText(self.winActionLabel())        
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        
        #It seems that the child behavior (on top of parent, minimize together with parent)
        #is lost as soon the parent is hidden and shown again
        #Toggling the stay on top flags restores the parent-child behavior
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.qapp.processEvents()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        
        self.show()
        
    def winActionLabel(self):    
        if self.parent() is None:
            return 'Tool of...'
        else:
            return f'Tool of {self.parent().name}'        
        
    def isToolWindow(self):
        return (self.windowFlags() & Qt.Tool) == Qt.Tool        
            
    def createStatusBar(self):        
        self.panelName = QLabel('')
        self.panelName.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.panelName.customContextMenuRequested.connect(self.showPanelMenu)                
        self.statusBar().addWidget(self.panelName,1)      
        
    def showPanelMenu(self, point=None):
        self.panelMenu.exec_(QtGui.QCursor().pos())
                                               
    def fullScreen(self):
        if not self.isFullScreen():
            self.showFullScreen()
        else:
            self.showNormal() 

    def toggleMenuStatusbar(self):
        if self.menuBar().isVisible():
            self.menuBar().hide()
            self.statusBar().hide()
        else:
            self.menuBar().show()
            self.statusBar().show()
        
    def unregister(self):        
        #Detach all tool windows of this window
        for window in self.qapp.windows.values():
            if window.parent() == self:
                window.asToolWindow(None)
                                    
        #Unregister this window
        self.qapp.windows.pop(self.name)
        self.qapp.panels.ezm.containers.pop(self.name)
        self.deleteLater()        
        self.qapp.hideWindow()

    def getWidgetUnderMouse(self):
        '''
        Get the widget outside this window under the current mouse position.        
        '''
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)        
        pos = QtGui.QCursor.pos()
        widget = gui.qapp.widgetAt(pos)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        if widget is None: return None, None
        locPos = widget.mapFromGlobal(pos)
        return widget, locPos
        
    def moveEvent(self, event):
        if self.dragState == DragState.placed: return
        
        elif self.dragState == DragState.titlePressed:
            self.dragState = DragState.dragging
            self.setWindowOpacity(0.5)
            self.qapp.panels.ezm.drop_in(self.container, hide=False, allWindows=self.dragToAllWindows)
            
        elif self.dragState == DragState.dragging:                                
            widget, locPos = self.getWidgetUnderMouse()        
            
            if widget is None: return
            
            if self.priorHoverButton == widget: return
            
            if not self.priorHoverButton is None:
                self.priorHoverButton.endPreview()
                # It seems that sometimes, the priorHoverButton is not valid?
                # Traceback (most recent call last):
                 # File "c:\tools\gh2\venv\lib\site-packages\gdesk\panels\window.py", line 320, in moveEvent
                 # self.priorHoverButton.endPreview()
                 # File "c:\tools\gh2\venv\lib\site-packages\gdesk\ezdock\overlay.py", line 59, in endPreview
                 # self.parent().endPreview() 
                # RuntimeError: Internal C++ object (HoverButton) already deleted.
                self.priorHoverButton = None                
            
            if isinstance(widget, overlay.HoverButton):
                widget.startPreview()
                self.priorHoverButton = widget            
    
    def event(self, event):                       
        if self.dragState == DragState.placed:
            if event.type() == QtCore.QEvent.NonClientAreaMouseButtonPress:
                if event.modifiers() & QtCore.Qt.ControlModifier:
                    if not self.isToolWindow() or (event.modifiers() & QtCore.Qt.ShiftModifier):                  
                        self.startMoving(True)
                    else:
                        self.startMoving(False)
                else:
                    return super().event(event)
                return True
            
        elif event.type() == QtCore.QEvent.NonClientAreaMouseButtonDblClick \
            or event.type() == QtCore.QEvent.Resize:
            self.windowPlaced(canceled=True)            
            
        elif event.type() == QtCore.QEvent.NonClientAreaMouseButtonRelease:            
            self.windowPlaced() 
            return True
            
        return super().event(event)
        
    def startMoving(self, allWindows=True):
        self.dragState = DragState.titlePressed          
        self.dragToAllWindows = allWindows 
        self.priorHoverButton = None
        
    def windowPlaced(self, canceled=False):            
        if not canceled:
            widget, locPos = self.getWidgetUnderMouse()
            
            if isinstance(widget, overlay.HoverButton):
                widget.clicked.emit()
                self.qapp.deleteEmptyWindows()
            else:
                canceled = True
                
        if canceled:
            self.qapp.panels.ezm.hide_overlays()                 
                
        self.setWindowOpacity(1.0)
        self.dragState = DragState.placed         
        self.priorHoverButton = None
        
    def closeEvent(self, event):
        self.qapp.hideWindow(self)
        event.accept()