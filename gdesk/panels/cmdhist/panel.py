from qtpy import QtCore, QtGui, QtWidgets

from ...dialogs.formlayout import fedit
from ...panels.base import BasePanel
from ... import gui

class CmdHistTableModel(QtCore.QAbstractTableModel):
    def __init__(self):
        super().__init__()
        
    def rowCount(self, index):
        for row in gui.qapp.history.execfetch('SELECT COUNT() FROM CMDHIST'):
            count = row[0]
        return count
        
    def columnCount(self, index):
        return 2            
            
    def data(self, index, role):    
        if role == QtCore.Qt.DisplayRole:
            rownr, colnr = index.row(), index.column()
            for row in gui.qapp.history.execfetch(f'SELECT TIME, CMD FROM CMDHIST LIMIT {rownr}, 1'):
                value = row[colnr]
            return str(value)


class CmdHistTableView(QtWidgets.QTableView):
    def __init__(self):
        super().__init__()        
        
    def getSelectedCommands(self):
        selmodel = self.selectionModel()        
        lines = []
        for index in selmodel.selectedIndexes():
            text = self.model().data(index, QtCore.Qt.DisplayRole)
            lines.append(text)
            
        return '\n'.join(lines)            
        
    def mouseDoubleClickEvent(self, event):
        text = self.getSelectedCommands()
        console = gui.qapp.panels.selected('console')
        if not text.endswith('\n'):
            text += '\n'
        console.stdio.stdInputPanel.addText(text)
        
        
class CmdHistPanel(BasePanel):
    panelCategory = 'cmdhist'
    panelShortName = 'basic'
    userVisible = True     

    def __init__(self, parent, panid):
        super().__init__(parent, panid, type(self).panelCategory)
        
        self.initMenu()
        
        self.model = CmdHistTableModel()
        self.cmdhistview = CmdHistTableView()
        self.cmdhistview.setModel(self.model)
        self.setCentralWidget(self.cmdhistview)  
        
        self.statusBar().hide()
        
    def initMenu(self):        
        self.fileMenu = self.menuBar().addMenu("&File")
        
        self.addMenuItem(self.fileMenu, 'Close', self.close_panel,
            statusTip="Close this levels panel",
            icon = 'cross.png')         

        self.viewMenu = self.menuBar().addMenu("&View")      
        
        self.addMenuItem(self.viewMenu, 'Reset', self.reset)
        self.addMenuItem(self.viewMenu, 'Refresh', self.refresh)
        self.addMenuItem(self.viewMenu, 'Paste stdin', self.pasteStdin)
        
        self.addBaseMenu()        
        
    def reset(self):
        self.model.reset()        
                
    def refresh(self):
        self.cmdhistview.repaint()    
        
    def pasteStdin(self):
        text = self.cmdhistview.getSelectedCommands()            
        console = gui.qapp.panels.selected('console')
        console.stdio.stdInputPanel.setPlainText(text)

