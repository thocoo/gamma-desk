from qtpy import API_NAME
    
def using_pyside():
    return API_NAME in ['PySide2', 'PySide6']
    
def using_pyqt():
    return API_NAME in ['PyQt5', 'PyQt6']
