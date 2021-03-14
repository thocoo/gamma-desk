import threading
import sys, os
import ctypes
import logging
import textwrap
import pathlib
import mmap
import struct
import threading
import psutil

from multiprocessing.connection import Pipe
from multiprocessing.reduction import duplicate

from qtpy import QtGui, QtWidgets, QtCore
from qtpy.QtWidgets import QApplication, QShortcut, QDesktopWidget, QMenu, QWidget, QPlainTextEdit
from qtpy.QtGui import QIcon, QKeySequence
from qtpy.QtCore import QByteArray, Qt

from .. import gui, config

from ..core.history import History
from ..core.watcher import CommandServer

from ..utils import new_id_using_keys
from ..utils.namedmutex import NamedMutex

from .qgc import QGarbageCollector
from .threadcom import HandOver
from .utils import getMenuAction, relax_menu_text, relax_menu_trace

from ..panels.window import MainWindow
from ..panels.panels import Panels
from ..panels.base import thisPanel

from ..dialogs.main import MainDialog

here = pathlib.Path(__file__).parent
respath = pathlib.Path(config['respath'])
logger = logging.getLogger(__name__)

        
class WaitCursorContext(object):
    def __init__(self, qapp, message=None):
        self.qapp = qapp
        self.message = message
        self.window = self.qapp.activeWindow()
        if not self.window in self.qapp.windows.values():
            self.window = None
        
    def __enter__(self):
        self.qapp.setOverrideCursor(QtCore.Qt.WaitCursor)
        if not self.message is None:
            #TO DO, bring this to the relevant window status bar
            #self.qapp.panels['console'][0].addText(f'{self.message}\n')
            logger.info(self.message)
            
            if not self.window is None:
                self.window.statusBar().showMessage(self.message)
            
        self.qapp.processEvents()
        
    def __exit__(self, exc_type, exc, exc_tb):
        self.qapp.restoreOverrideCursor()
        self.qapp.processEvents()
        
        if not self.window is None:
            self.window.statusBar().clearMessage()                       

      
class GuiApplication(QApplication):
    lastWindowId = 0

    def __init__(self, shell, argv):
        self.shell = shell
        
        super().__init__(argv)                
        
        self.windows = dict()
        self.panels = Panels(self)  
        #self.panelsDialog = PanelsDialog(self.panels)
        self.panelsDialog = MainDialog(self.panels)
        self.appIcon = QIcon(str(respath / 'logo' / 'bench_eye_32px.png'))
        self.setWindowIcon(self.appIcon)        
        self.handover = HandOver(self)
                
        self.history = History(self.shell.logdir.logpath)

        self.setFont(QtGui.QFont('MS Shell Dlg 2', pointSize=config['console']['fontsize']))

        if os.name == 'nt':
            # This is needed to display the app icon on the taskbar on Windows 7
            myappid = 'OnSemi.Gamma.Hawk.Dusky' # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)    
            
        self.gc = QGarbageCollector(self)
        self.gc.enable()                

        self.selected_group = dict()
        self.radio_group = dict()
        
        self.bindicon = QtGui.QIcon()
        self.bindicon.addFile(str(respath / 'icons' / 'bind_12px.png'), state=QIcon.On)
        self.bindicon.addFile(str(respath / 'icons' / 'broken_12px.png'), state=QIcon.Off)  
        
        self.resizeicon = QtGui.QIcon()
        self.resizeicon.addFile(str(respath / 'icons' / 'arrow_down_8px.png'), state=QIcon.Off)
        self.resizeicon.addFile(str(respath / 'icons' / 'arrow_right_8px.png'), state=QIcon.On)
        
        self.panelsDialog.showMinimized()
        self.focusChanged.connect(self.checkPanelActive)
        
        self.menuCallShortCuts = dict()

    def setShortCuts(self):        
        for layid in range(1,10):
            self.setShortCut(f"{config['shortcuts']['layout']['prefix']}{layid}",
                lambda layid=layid: self.panels.restore_state_from_config(layid))
            
        self.setPanelsDialogShortCut(config['shortcuts']['help'], ['Help', 'Help'])
        self.setPanelsDialogShortCut(config['shortcuts']['instance info'], ['Help', 'Instance Info'])
        self.setPanelsDialogShortCut(config['shortcuts']['panel preview'], ['Panel', 'Previews...'])
        self.setPanelsDialogShortCut(config['shortcuts']['window preview'], ['Window', 'Previews...'])
        
        self.setShortCut(config['shortcuts']['new panel'], lambda : self.showNewPanelDialog())
        
        for keySequence, menuCallParams in config["shortcutmenu"].items():
            for category, action_names in menuCallParams.items():
                if not category in self.menuCallShortCuts.keys():
                    self.menuCallShortCuts[category] = dict()
                self.menuCallShortCuts[category][relax_menu_trace(action_names)] = keySequence
                
            self.setShortCut(keySequence, lambda keySequence=keySequence: self.menuShortCutCall(keySequence))
        
    def setShortCut(self, keySequence, func):
        sc = QShortcut(QKeySequence(keySequence), self.panelsDialog, func)
        sc.setContext(Qt.ApplicationShortcut)
        
    def setPanelsDialogShortCut(self, keySequence, menuTrace):
        menuTrace = relax_menu_trace(menuTrace)
        
        def caller():
            action = getMenuAction(self.panelsDialog.menuBar(), menuTrace)
            action.trigger()
            
        action = getMenuAction(self.panelsDialog.menuBar(), menuTrace)
        action.setText(f'{action.text()}\t{keySequence}')
        self.setShortCut(keySequence, caller)
        
    def menuShortCutCall(self, keySequence):
        shortCutParams = config["shortcutmenu"][keySequence]

        if len(shortCutParams) == 1:
            category, action_names = next(iter(shortCutParams.items()))
            
        else:
            for category in reversed(self.panels.keys()):
                if category in shortCutParams.keys():
                    action_names = shortCutParams[category]
                    break
            else:
                category, action_names = None, []
                
        #logger.info(f'menuShortCutCall: {category} {action_names}')
                
        if category is None:
            return
            
        elif category == 'window':
            window = self.activeWindow()
            action = getMenuAction(window.windowMenu, action_names)
            action.trigger()
        else:
            action = self.panels.get_menu_action(category, None, action_names)
            action.trigger()
        
    def checkPanelActive(self, old, new):        
        #This function is probably more called then needed !
        if new is None: return
        try:
            panel = thisPanel(new)        
            if panel is None: return
            panel.select()
        except Exception as ex:
            #Do not print any error message in the gui
            #It would emit focusChanged and lead to infinite loop
            sys.__stdout__.write(str(ex))
            sys.__stdout__.flush()            
        
    @property 
    def mainWindow(self):
        return self.windows['main']
        
    def showDialog(self):
        self.panelsDialog.refresh()
        self.panelsDialog.exec_(self.activeWindow())    
        
    def showNewPanelDialog(self):
        self.panelsDialog.newMenu.exec_(QtGui.QCursor.pos())    

    def closePanel(self):
        window = self.activeWindow()
        panel = self.panels[window.activeCategory][window.activePanId]
        panel.close_panel()       
        
    def newWindow(self, name=None, parentName=None):
        if name is None:
            keys = [eval(k.split(' ')[1]) for k in self.windows.keys() if k.startswith('window ')]            
            key = new_id_using_keys(keys)
            name = f'window {key}'
        self.windows[name] = window = MainWindow(self, name, parentName)        
        return window  
        
    def getActiveWindow(self):
        for winname, window in self.windows.items():
            if window.isActiveWindow():
                return window           
                
    def cycleTagLevel(self):
        self.getActiveWindow().cycle_tag_level()                            
                
    def toggleFullScreen(self):
        self.getActiveWindow().fullScreen()            
        
    def toggleMenuStatusbar(self):
        self.getActiveWindow().toggleMenuStatusbar()            
        
    def toggleShortCuts(self):    
        self.panelsDialog.setVisible(not self.panelsDialog.isVisible())
        
    def deleteWindow(self, window):
        if isinstance(window, str):
            winname = window
        else:
            winname = window.name        
        window = self.windows.pop(winname)        
        container = self.panels.ezm.containers.pop(winname)
        window.deleteLater()
        
    def deleteEmptyWindows(self, check=False):
        for winname in list(self.windows.keys()):
            if winname == 'main':
                continue            
            window = self.windows[winname]
            
            if window.container.is_empty(check):                
                self.deleteWindow(winname)
             
    def start_image_path_receiver(self):
        threading.Thread(target=self.receive_image_paths, daemon=True).start()
                
    def receive_image_paths(self):
        channel_lock = NamedMutex('ghawk2 channel lock')                
        buf = mmap.mmap(-1, 16, 'Gamma Hawk 2.0 Channel')
        
        with channel_lock:
            struct.pack_into('llll', buf, 0, 0, 0, 0, 0)            
        
        def open_image(image_path):
            gui.img.open(image_path)
            
        while True:
            with channel_lock:
                reader, writer = Pipe(duplex=False)
            
                read_handle = reader._handle
                write_handle = writer._handle

                pid = os.getpid()
                rh = duplicate(read_handle)
                wh = duplicate(write_handle)            
            
                struct.pack_into('llll', buf, 0, 1, pid, rh, wh)
            
            while True:
                close_pipe, image_path = reader.recv()                
                if close_pipe: break
                self.handover.send(True, open_image, image_path)
                
    def waitCursor(self, message=None):
        return WaitCursorContext(self, message)
                
    def hideWindow(self, window=None):
        if not window is None:
            window.hide()
        
        #Close if no window visible
        visibles = [win.isVisible() for win in self.windows.values()]
        
        if sum(visibles) == 0:
            self.panelsDialog.showNormal()                   
        

def eventloop(shell, init_code=None, init_file=None, console_id=0, pictures=None):
    """
    The GUI Process and Thread running the eventloop
    """            
    shell.logdir.find_log_path()
    
    qapp = GuiApplication(shell, sys.argv)           
    qapp.setShortCuts()
    qapp.newWindow('main')
            
    #To run in a new thread but on the same gui process
    #panid = qapp.mainWindow.newThread()
    qapp.mainWindow.show()
            
    desktopGeometry = QDesktopWidget().availableGeometry()
    qapp.mainWindow.resize(int(desktopGeometry.width()*3/5), int(desktopGeometry.height()*3/5))
    
    qtRectangle = qapp.mainWindow.frameGeometry()    
    centerPoint = desktopGeometry.center()
    qtRectangle.moveCenter(centerPoint)
    qapp.mainWindow.move(qtRectangle.topLeft())
    
    # Make sure the gui proxy for the main thread is created
    # qapp.panels.restore_state_from_config('base')
       
    # if not config['debug']['skip_restore_perspective']:
        # if config['default_perspective'] != 'base':
            # qapp.panels.restore_state_from_config(config['default_perspective'])
    
    qapp.processEvents()    
    qapp.cmdserver = CommandServer(shell)
    
    if not init_file is None:
        cmd = {'cmd': 'execute_file', 'args': (init_file, console_id)}
        qapp.cmdserver.cmd_queue.put(cmd)
        
    if not init_code is None:
        cmd = {'cmd': 'execute_code', 'args': (init_code, console_id)}
        qapp.cmdserver.cmd_queue.put(cmd)        
        
    if not pictures is None:
        cmd = {'cmd': 'open_images', 'args': pictures}
        qapp.cmdserver.cmd_queue.put(cmd)            
        
    cmd = config.get('init_command')       
    qapp.cmdserver.cmd_queue.put(cmd)
    
    qapp.cmdserver.start_queue_loop(qapp)
    qapp.cmdserver.start(qapp)    
    exit_code = qapp.exec_()
    
    #Kill all the children    
    parent = psutil.Process(os.getpid())
    for child in parent.children(recursive=True):
        child.kill()
    
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    print('Exiting Gamma Hawk Dusky. Releasing lock.')   
    shell.logdir.release_lock_file()    
    
            