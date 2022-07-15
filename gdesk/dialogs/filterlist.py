import re
import fnmatch

from qtpy import QtCore, QtGui, QtWidgets


class SelectionList(QtWidgets.QListWidget):

    def __init__(self, parent):
        super().__init__(parent=parent)


class FilterList(QtWidgets.QDialog):

    def __init__(self, items, multiple=True, filter='*', title='Items'):
        super().__init__(None)
        self.initgui(items, multiple, filter)
        self.setWindowTitle(title)
        
    def initgui(self, items, multiple, filter):
        self.selectionlist = SelectionList(self)
        self.items = items
        
        self.changeSelectStateAllBtn = QtWidgets.QPushButton('Check none', self)
        self.changeSelectStateAllBtn.clicked.connect(self.toggleCheckStateAll)

        self.filter = QtWidgets.QLineEdit(filter, self)
        
        self.useregexpr = QtWidgets.QCheckBox('RegExp', self)
        
        self.addSelectByFilterBtn = QtWidgets.QPushButton('Add', self)
        self.addSelectByFilterBtn.clicked.connect(self.addSelectByFilter)  
        
        self.removeSelectByFilterBtn = QtWidgets.QPushButton('Remove', self)
        self.removeSelectByFilterBtn.clicked.connect(self.removeSelectByFilter)
        
        if not multiple:
            self.changeSelectStateAllBtn.hide()
            self.filter.hide()
            self.useregexpr.hide()            
            self.addSelectByFilterBtn.hide()            
            self.removeSelectByFilterBtn.hide()            
            
        
        self.okBtn = QtWidgets.QPushButton('Ok', self)
        self.okBtn.clicked.connect(self.ok)
        
        self.cancelBtn = QtWidgets.QPushButton('Cancel', self)
        self.cancelBtn.clicked.connect(self.cancel)
        
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.changeSelectStateAllBtn)
        layout.addWidget(self.filter)
        
        hlayout = QtWidgets.QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(self.useregexpr)        
        hlayout.addWidget(self.addSelectByFilterBtn)        
        hlayout.addWidget(self.removeSelectByFilterBtn)        
        
        layout.addWidget(self.selectionlist)
        
        hlayout = QtWidgets.QHBoxLayout()
        layout.addLayout(hlayout)        
        hlayout.addWidget(self.okBtn)
        hlayout.addWidget(self.cancelBtn)
            
        self.setLayout(layout)
        
        for item in self.items:
            list_item = QtWidgets.QListWidgetItem(str(item))
            if multiple:
                list_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            else:
                list_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.selectionlist.addItem(list_item)            
            
    def checkedItems(self):
        selection = []
        for i in range(self.selectionlist.count()):
            uiitem = self.selectionlist.item(i)
            if uiitem.checkState() == QtCore.Qt.Checked:
                selection.append(self.items[i])
        return selection
        
    def selectedItem(self):
        for i in range(self.selectionlist.count()):
            uiitem = self.selectionlist.item(i)
            if uiitem.isSelected():
                return self.items[i]
        return None
        
    def selectItem(self, item):
        for i in range(self.selectionlist.count()):         
            selection_item = self.selectionlist.item(i)
            if self.items[i] == item:
                selection_item.setSelected(True)
                self.selectionlist.scrollToItem(selection_item)
                return            
        
    def toggleCheckStateAll(self):
        if self.changeSelectStateAllBtn.text() == 'Check all':
            state = True
            self.changeSelectStateAllBtn.setText('Check none')
            self.checkAll(state)
        elif self.changeSelectStateAllBtn.text() == 'Check none':
            state = False
            self.changeSelectStateAllBtn.setText('Check all')
            self.checkAll(state)         

    def addSelectByFilter(self):
        use_regexp = self.useregexpr.isChecked()
        self.checkItemsFilterMatch(self.filter.text(), append=True, remove=False, use_regexp=use_regexp)
            
    def removeSelectByFilter(self):
        use_regexp = self.useregexpr.isChecked()
        self.checkItemsFilterMatch(self.filter.text(), append=False, remove=True, use_regexp=use_regexp)          
            
    def checkItems(self, items_to_select):
        for i in range(self.selectionlist.count()):         
            selection_item = self.selectionlist.item(i)
            if self.items[i] in items_to_select:                            
                selection_item.setCheckState(QtCore.Qt.Checked)                
            else:
                selection_item.setCheckState(QtCore.Qt.Unchecked)
                
    def checkItemsRe(self, pattern, append=True, remove=True):
        self.checkItemsFilterMatch(pattern, append, remove, use_regexp=True)                      
                
    def checkItemsFilterMatch(self, pattern, append=True, remove=True, use_regexp=False):
    
        def matches_fn(item):
            return fnmatch.fnmatch(item, pattern)
            
        def matches_regexp(item):
            return not re.match(pattern, str(item)) is None
    
        if use_regexp:
            matchfunc = matches_regexp
        else:
            matchfunc = matches_fn
            
        for i in range(self.selectionlist.count()):         
            selection_item = self.selectionlist.item(i)
            item = self.items[i]
            
            matches = matchfunc(item)
            #checked = selection_item.getChecked()
            
            if append and remove:
                if matches:
                    selection_item.setCheckState(QtCore.Qt.Checked)
                else:
                    selection_item.setCheckState(QtCore.Qt.Unchecked)
            elif append:
                if matches:
                    selection_item.setCheckState(QtCore.Qt.Checked)
                
            elif remove:
                if matches:
                    selection_item.setCheckState(QtCore.Qt.Unchecked)
            
        
    def checkAll(self, state=True):
        if state:
            newstate = QtCore.Qt.Checked
        else:
            newstate = QtCore.Qt.Unchecked
            
        for i in range(self.selectionlist.count()):
            item = self.selectionlist.item(i)
            item.setCheckState(newstate)
            
    def ok(self):
        self.done(QtWidgets.QDialog.DialogCode.Accepted)
        
    def cancel(self):
        self.done(QtWidgets.QDialog.DialogCode.Rejected)
