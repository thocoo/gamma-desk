import re
import fnmatch
import pathlib

from qtpy import QtCore, QtGui, QtWidgets

from .base import getMap

class PathList(QtWidgets.QListWidget):

    def __init__(self, parent, paths):
        super().__init__(parent=parent)
        
        for item in paths:
            list_item = QtWidgets.QListWidgetItem(str(item))
            list_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.addItem(list_item)           

class EditPaths(QtWidgets.QDialog):

    def __init__(self, paths, title='Edit Search Paths'):
        super().__init__(None)
        self.initgui(paths, title)
        
        
    def initgui(self, paths, title):
        self.paths = paths
        
        self.setWindowTitle(title)
        
        self.selectionlist = PathList(self, paths)                
        
        self.addPathBtn = QtWidgets.QPushButton('Add', self)
        self.addPathBtn.clicked.connect(self.add)
        self.editPathBtn = QtWidgets.QPushButton('Edit', self)
        self.editPathBtn.clicked.connect(self.edit)
        self.delPathBtn = QtWidgets.QPushButton('Delete', self)
        self.delPathBtn.clicked.connect(self.delete)
        
        self.okBtn = QtWidgets.QPushButton('Ok', self)
        self.okBtn.clicked.connect(self.ok)
        self.cancelBtn = QtWidgets.QPushButton('Cancel', self)                       
        self.cancelBtn.clicked.connect(self.cancel)

        layout = QtWidgets.QVBoxLayout()
        
        hlayout = QtWidgets.QHBoxLayout()        
        hlayout.addWidget(self.addPathBtn)
        hlayout.addWidget(self.editPathBtn)
        hlayout.addWidget(self.delPathBtn)
        layout.addLayout(hlayout)            
        
        hlayout = QtWidgets.QHBoxLayout()
        layout.addLayout(hlayout)        
        layout.addWidget(self.selectionlist)
        
        hlayout = QtWidgets.QHBoxLayout()        
        hlayout.addWidget(self.okBtn)
        hlayout.addWidget(self.cancelBtn)
        layout.addLayout(hlayout)    
            
        self.setLayout(layout)         
        
    def add(self):
        path = pathlib.Path(getMap())
        item = QtWidgets.QListWidgetItem(str(path))
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        self.selectionlist.addItem(item)     
        
    def edit(self):
        for item in self.selectionlist.selectedItems():            
            path = item.text()
            path = pathlib.Path(getMap(path))
            item.setText(path)

    def delete(self):
        for item in self.selectionlist.selectedItems():        
            self.selectionlist.takeItem(self.selectionlist.row(item))
            
    def ok(self):
        self.updatePaths()
        self.done(QtWidgets.QDialog.DialogCode.Accepted)
        
    def cancel(self):
        self.done(QtWidgets.QDialog.DialogCode.Rejected)
        
    def updatePaths(self):
        self.paths.clear()
        for index in range(self.selectionlist.count()):        
            item = self.selectionlist.item(index)
            self.paths.append(item.text())

