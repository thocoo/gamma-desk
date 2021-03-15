from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

class Thumbs(QtWidgets.QListWidget):

    def __init__(self, parent):
        super().__init__(parent=parent)
        #self.setViewMode(QtWidgets.QListWidget.IconMode)
        self.setViewMode(QtWidgets.QListWidget.ListMode)
        self.setIconSize(QtCore.QSize(256, 256))
        self.setResizeMode(QtWidgets.QListWidget.Adjust)

    def addQImage(self, qimg, title):
        pixmap = QtGui.QPixmap(qimg)
        self.addItem(QtWidgets.QListWidgetItem(QtGui.QIcon(pixmap), title))