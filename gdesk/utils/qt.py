try:
    from qtpy import PYSIDE, PYQT4
except:
    PYSIDE, PYQT4 = False, False
    
from qtpy import PYSIDE2, PYQT4, PYQT5
    
def using_pyside():
    return PYSIDE or PYSIDE2
    
def using_pyqt():
    return PYQT4 or PYQT5
