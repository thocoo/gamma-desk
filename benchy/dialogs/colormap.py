from qtpy import QtGui, QtWidgets, QtCore

from ..widgets.thumbs import Thumbs
from ..utils import imconvert

class ColorMapDialog(QtWidgets.QDialog):

    def __init__(self):
        super().__init__()
        colormaps = imconvert.colormaps   
        self.thumbs = Thumbs(self)
        
        for cm_name in colormaps:        
            qimg = imconvert.color_table_preview_qimg(cm_name)
            self.thumbs.addQImage(qimg, cm_name)
            
        self.vbox = QtWidgets.QVBoxLayout(self)
        self.setLayout(self.vbox)
        self.vbox.addWidget(self.thumbs)
        
        self.okBtn = QtWidgets.QPushButton('Ok')
        self.okBtn.clicked.connect(self.ok)
        self.vbox.addWidget(self.okBtn)
        
        self.cm_name = None
        
    def ok(self):
        items = self.thumbs.selectedItems()
        if len(items) > 0:
            self.cm_name = items[0].text()
        else:
            self.cm_name = None
        self.accept()
        
        