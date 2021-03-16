from qtpy import QtCore, QtGui, QtWidgets

class FileDialog(QtWidgets.QDialog):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        hbox = QtWidgets.QHBoxLayout()
        vbox.addLayout(hbox)
        
        self.treeView = QtWidgets.QTreeView(self)
        hbox.addWidget(self.treeView)       
        
        #self.treeView.setGeometry(0,0, 600, 800)
        self.dirModel = QtWidgets.QFileSystemModel()
        self.path = "C:\\"
        self.dirModel.setRootPath(self.path)
        self.dirModel.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.Dirs | QtCore.QDir.NoDotAndDotDot | QtCore.QDir.Hidden)
        self.treeView.setModel(self.dirModel)
        #self.treeView.setRootIndex(self.dirModel.index(self.path))
        #self.treeView.expandAll()
        self.treeView.clicked.connect(self.on_treeView_clicked)

        #self.listView = QtWidgets.QListView(self)
        #self.listView = QtWidgets.QTreeView(self)
        self.listView = QtWidgets.QTableView(self)
        hbox.addWidget(self.listView)
        
        self.fileModel = QtWidgets.QFileSystemModel()
        #self.fileModel.setFilter(QtCore.QDir.Files | QtCore.QDir.Dirs | QtCore.QDir.Hidden)
        self.fileModel.setFilter(QtCore.QDir.Files | QtCore.QDir.Hidden)
        self.listView.setModel(self.fileModel)

        #self.setGeometry(300, 300, 600, 800)
        self.setWindowTitle('Select File')        
        
    def on_treeView_clicked(self, index):
        # // TreeView clicked
        # // 1. We need to extract path
        # // 2. Set that path into our ListView

        # Get the full path of the item that's user clicked on
        path = self.dirModel.fileInfo(index).absoluteFilePath()
        index = self.fileModel.setRootPath(path)
        self.listView.setRootIndex(index)
        
    def ok(self):
        self.updatePaths()
        self.done(QtWidgets.QDialog.DialogCode.Accepted)
        
    def cancel(self):
        self.done(QtWidgets.QDialog.DialogCode.Rejected)        
        
    