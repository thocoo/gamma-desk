import sys
import ctypes
import ctypes.wintypes
from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets
    
from gdesk.utils.qt import using_pyside, using_pyqt    

LASTMAP = None

if sys.platform == 'win32':
    class LASTINPUTINFO(ctypes.Structure):
        
        _fields_ = [
          ('cbSize', ctypes.wintypes.UINT),
          ('dwTime', ctypes.wintypes.DWORD),
          ]

    PLASTINPUTINFO = ctypes.POINTER(LASTINPUTINFO)

    GetLastInputInfo = ctypes.windll.user32.GetLastInputInfo
    GetLastInputInfo.restype = ctypes.wintypes.BOOL
    GetLastInputInfo.argtypes = [PLASTINPUTINFO]

    def get_last_input_moment():
        liinfo = LASTINPUTINFO()
        liinfo.cbSize = ctypes.sizeof(liinfo)
        GetLastInputInfo(ctypes.byref(liinfo))
        return liinfo.dwTime

elif sys.platform in ('linux', 'darwin'):
    def get_last_input_moment():
        return -1

else:
    ImportError(f'Platform {sys.platform} not suported')


class ExecTimeout:
    def __init__(self, dialog, timeout=None):  
        self.dialog = dialog
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.check_user_input_and_close)
        self.timeout = timeout
        
        if not timeout is None:            
            self.timer.start(timeout)
        
    def exec_(self):
        self.exec_user_input_moment = get_last_input_moment()
        self.dialog.exec_()
        self.timer.stop()
        
    def check_user_input_and_close(self):
        last_user_input_moment = get_last_input_moment() 
        
        if self.exec_user_input_moment < last_user_input_moment:
            self.timer.stop()
            
        else:
            self.dialog.close()
           
        
def getFile(filter='*.*', title='open', defaultFile=None, hideFilterDetails=False):
    global LASTMAP

    if not defaultFile is None:
        defaultDir = defaultFile
    else:
        defaultDir = LASTMAP

    #The HideNameFilterDetails option seems to be crashy
    #if the filter doesn't have the detailed form
    #  Tagged Image Format (*.tif)
    #For example the filter *.* often crashes if the option is enabled
    #Maybe QT returns a buggy string as selectedFilter?

    if using_pyside():
        if not hideFilterDetails:
            fileName, selectedFilter = QtWidgets.QFileDialog.getOpenFileName(
                caption = title,
                dir=defaultDir,
                filter=filter)
        else:
            fileName, selectedFilter = QtWidgets.QFileDialog.getOpenFileName(
                caption = title,
                dir=defaultDir,
                filter=filter,
                options=QtWidgets.QFileDialog.HideNameFilterDetails)
                
    elif using_pyqt():
        if not hideFilterDetails:
            fileName, selectedFilter = QtWidgets.QFileDialog.getOpenFileNameAndFilter(
                caption = title,
                directory=defaultDir,
                filter=filter)
        else:
            fileName, selectedFilter = QtWidgets.QFileDialog.getOpenFileNameAndFilter(
                caption = title,
                directory=defaultDir,
                filter=filter,
                options=QtWidgets.QFileDialog.HideNameFilterDetails)

    LASTMAP = str(Path(fileName).parent)
    return fileName, selectedFilter

def getFiles(filter='*.*', title='open', defaultFile=None, hideFilterDetails=False):
    global LASTMAP

    if not defaultFile is None:
        defaultDir = defaultFile
    else:
        defaultDir = LASTMAP

    #The HideNameFilterDetails option seems to be crashy
    #if the filter doesn't have the detailed form
    #  Tagged Image Format (*.tif)
    #For example the filter *.* often crashes if the option is enabled
    #Maybe QT returns a buggy string as selectedFilter?

    if using_pyside():
        if not hideFilterDetails:
            fileNames, selectedFilter = QtWidgets.QFileDialog.getOpenFileNames(
                caption = title,
                dir=defaultDir,
                filter=filter)
        else:
            fileNames, selectedFilter = QtWidgets.QFileDialog.getOpenFileNames(
                caption = title,
                dir=defaultDir,
                filter=filter,
                options=QtWidgets.QFileDialog.HideNameFilterDetails)
    elif using_pyqt():
        if not hideFilterDetails:
            fileNames, selectedFilter = QtWidgets.QFileDialog.getOpenFileNamesAndFilter(
                caption = title,
                directory=defaultDir,
                filter=filter)
        else:
            fileNames, selectedFilter = QtWidgets.QFileDialog.getOpenFileNamesAndFilter(
                caption = title,
                directory=defaultDir,
                filter=filter,
                options=QtWidgets.QFileDialog.HideNameFilterDetails)

    LASTMAP = str(Path(fileNames[0]).parent)
    return fileNames, selectedFilter

def putFile(filter='*.*', title='save', defaultFile=None, defaultFilter=''):
    global LASTMAP

    if not defaultFile is None:
        defaultDir = defaultFile
    else:
        defaultDir = LASTMAP

    if using_pyside():
        fileName, selectedFilter = QtWidgets.QFileDialog.getSaveFileName(
            caption = title,
            filter = filter,
            dir = defaultDir,
            selectedFilter = defaultFilter)
    elif using_pyqt():
        fileName, selectedFilter = QtWidgets.QFileDialog.getSaveFileNameAndFilter(
            caption = title,
            filter = filter,
            directory = defaultDir,
            selectedFilter = defaultFilter)
    LASTMAP = str(Path(fileName).parent)
    return fileName, selectedFilter

def getMap(startPath=None, title='select a Directory'):
    global LASTMAP
    startPath = startPath or LASTMAP
    if using_pyside():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            caption=title,
            dir=startPath)
    elif using_pyqt():
            path = QtWidgets.QFileDialog.getExistingDirectory(
            caption=title,
            directory=startPath)
    LASTMAP = path
    return path

def getString(prompt, default='', title='Input', echo='Normal'):
    """
    Show a popup-window to ask the user some textual input.

    Makes use of QtWidgets.QInputDialog.getText; see
    https://srinikom.github.io/pyside-docs/PySide/QtGui/QInputDialog.html#PySide.QtGui.PySide.QtGui.QInputDialog.getText

    :param str prompt: The explanation that is visible just above the text input field.
    :param str default: The text that is already present in the editable input field.
    :param str title: The name of the pop-window (shown in its title bar).
    :param str echo: 'Normal' for normal text entry; 'Password' for password entry.  See
     http://doc.qt.io/qt-4.8/qlineedit.html#EchoMode-enum
    """
    
    echo_mode = getattr(QtWidgets.QLineEdit.EchoMode, echo)
    return QtWidgets.QInputDialog.getText(None, title, prompt, echo=echo_mode, text=default)[0]
        
               
def getStringTimeout(prompt, default='', title='Input', echo='Normal', timeout=10000):       
    
    echo_mode = getattr(QtWidgets.QLineEdit.EchoMode, echo)
    dialog = QtWidgets.QInputDialog()
    dialog.setWindowTitle(title)
    dialog.setLabelText(prompt)
    dialog.setTextValue(default)    
    
    retval = ExecTimeout(dialog, timeout).exec_()    
    
    if retval == 0:
        return default
        
    return dialog.textValue()
    
def selectFiles(filter='*.*', title='Select', defaultPath=None):
    filedialog = QtWidgets.QFileDialog()
    filedialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
    filedialog.setNameFilter(filter)
    
    if not defaultPath is None:
        defaultPath = Path(defaultPath)
        
        if defaultPath.is_file():
            defaultDir = defaultPath.parent
            defaultFile = defaultPath.name
            
        elif defaultPath.is_dir():
            defaultDir = defaultPath
            defaultFile = None
    else:
        defaultDir = None
        defaultFile = None                
    
    if not defaultDir is None:
        filedialog.setDirectory(str(defaultDir))
        
    if not defaultFile is None:
        filedialog.selectFile(str(defaultFile))
        
    filedialog.setWindowTitle(title)
    
    #filedialog.setAcceptMode(QtWidgets.QFileDialog.AcceptOpen)
    
    for btn in filedialog.findChildren(QtWidgets.QPushButton):
        if btn.text() == "&Open":
            btn.setText("Select")
        
    filedialog.exec_()
    return filedialog.selectedFiles()

def getMultiString(prompt, default, title='Input', timeout=None):
    dlg = MultiString(prompt, default, title)
    ExecTimeout(dlg, timeout).exec_()
    return dlg.lns

def messageBox(message, title='', icon='none'):
    icon = icon or 'none'        
    icon = icon.lower()
    if icon == 'help':
        icon = QtWidgets.QMessageBox.Question
    elif icon == 'info':
        icon = QtWidgets.QMessageBox.Information
    elif icon == 'warn':
        icon = QtWidgets.QMessageBox.Warning
    elif icon == 'error':
        icon = QtWidgets.QMessageBox.Critical	
    else:
        icon = QtWidgets.QMessageBox.NoIcon
        
    msgBox = QtWidgets.QMessageBox(icon, title, message)            
    #msgBox.setText(message)
    #msgBox.setIcon(icon)

    msgBox.exec_()
    
def questionBox(question, title=''):
    flags = QtWidgets.QMessageBox.question(None,  title, question, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
    if flags == 16384:
        return True
    else:
        return False        

class MultiString(QtWidgets.QDialog):

    def __init__(self, prompt = [], default = [], title="Input"):
        super().__init__(None)
        self.initui(prompt, default, title)

    def initui(self, prompt, default, title="Input"):
        self.setWindowTitle(title)
        layout = QtWidgets.QVBoxLayout()
        self.edits = []

        for [p,d] in zip(prompt, default):
            pw = QtWidgets.QLabel(p, self)
            dw = QtWidgets.QLineEdit(d, self)
            self.edits.append(dw)
            layout.addWidget(pw)
            layout.addWidget(dw)

        self.okbtn = QtWidgets.QPushButton('Ok')
        self.okbtn.clicked.connect(self.finish)

        layout.addWidget(self.okbtn)

        self.setLayout(layout)

    def finish(self):
        self.lns = []
        for e in self.edits:
            self.lns.append(e.text())
        self.close()


class TopMessageBox(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
