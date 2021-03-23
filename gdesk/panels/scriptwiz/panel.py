import logging
from pathlib import Path
import json
from collections import OrderedDict

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

from jinja2 import Template

from ... import gui, config
from ...panels.base import BasePanel, CheckMenu
from ...dialogs.formlayout import fedit

logger = logging.getLogger(__name__)
respath = Path(config['respath'])

class FileLayout(QtWidgets.QWidget):
    """File-specialized QLineEdit layout"""
    def __init__(self, text='', loadCall=None, saveCall=None, save=False, edit=True):
        super().__init__()
        
        self.loadCall = loadCall         
        self.saveCall = saveCall
        self.save = save
        
        hbox = QtWidgets.QHBoxLayout()
        hbox.setMargin(0)
        hbox.setContentsMargins(0,0,0,0)
        self.setLayout(hbox)        
                
        self.fileExplBtn = QtWidgets.QToolButton()
        self.fileExplBtn.clicked.connect(self.fileExplore)
        self.fileExplBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'folders_explorer.png')))
        hbox.addWidget(self.fileExplBtn)
        
        self.lineedit = QtWidgets.QLineEdit(text)
        hbox.addWidget(self.lineedit)
        
        if self.loadCall is None:
            self.loadCall = lambda filepath: None 
            
        else:
            self.fileLoadbtn = QtWidgets.QToolButton()        
            self.fileLoadbtn.clicked.connect(self.loadFile)
            self.fileLoadbtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'folder.png')))
            hbox.addWidget(self.fileLoadbtn)
        
        if self.saveCall is None:
            self.saveCall = lambda filepath: None
            
        else:
            self.fileSavebtn = QtWidgets.QToolButton()        
            self.fileSavebtn.clicked.connect(self.savefile)
            self.fileSavebtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'diskette.png')))
            hbox.addWidget(self.fileSavebtn)
        
        if edit:
            self.editbtn = QtWidgets.QToolButton()
            self.editbtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'script_edit.png')))
            self.editbtn.clicked.connect(self.editfile)
            hbox.addWidget(self.editbtn)      

    def fileExplore(self):            
        selectedFile = gui.dialog.selectfile(default_path=self.text())
        
        if selectedFile is None: return        
            
        self.lineedit.setText(selectedFile)                        
            
        if not self.save:
            self.loadCall(Path(self.text()))
        
    def loadFile(self):
        self.loadCall(Path(self.lineedit.text()))

    def savefile(self):                  
        self.saveCall(Path(self.lineedit.text()))
            
    def editfile(self):
        from gdesk import shell
        shell.edit_file(self.lineedit.text())

    def text(self):
        return self.lineedit.text()  
        
    def setText(self, text):
        self.lineedit.setText(text)
        
class DirFileLayout(QtWidgets.QWidget):
    """File-specialized QLineEdit layout"""
    def __init__(self, fullFilePath='', loadCall=None, saveCall=None, save=False, edit=True):
        super().__init__()
        
        self.loadCall = loadCall         
        self.saveCall = saveCall
        
        hbox = QtWidgets.QHBoxLayout()
        hbox.setMargin(0)
        hbox.setContentsMargins(0,0,0,0)
        self.setLayout(hbox)        
                
        self.dirExplBtn = QtWidgets.QToolButton()
        self.dirExplBtn.clicked.connect(self.getMap)
        self.dirExplBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'folders_explorer.png')))
        hbox.addWidget(self.dirExplBtn)
        
        fullFilePath = Path(fullFilePath)
        
        self.dirEdit = QtWidgets.QLineEdit(str(fullFilePath.parent))
        hbox.addWidget(self.dirEdit, 2)
        
        self.fileNameEdit = QtWidgets.QLineEdit(fullFilePath.name)
        hbox.addWidget(self.fileNameEdit, 1)        
        
        if self.loadCall is None:
            self.loadCall = lambda filepath: None 
            
        else:
            self.fileLoadbtn = QtWidgets.QToolButton()        
            self.fileLoadbtn.clicked.connect(self.loadFile)
            self.fileLoadbtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'folder_vertical_document.png')))
            hbox.addWidget(self.fileLoadbtn)
        
        if self.saveCall is None:
            self.saveCall = lambda filepath: None
            
        else:
            self.fileSavebtn = QtWidgets.QToolButton()        
            self.fileSavebtn.clicked.connect(self.savefile)
            self.fileSavebtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'diskette.png')))
            hbox.addWidget(self.fileSavebtn)
        
        if edit:
            self.editbtn = QtWidgets.QToolButton()
            self.editbtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'script_edit.png')))
            self.editbtn.clicked.connect(self.editfile)
            hbox.addWidget(self.editbtn)

    @property
    def fullFileName(self):
        return Path(self.dirEdit.text()) / self.fileNameEdit.text()            

    def getMap(self):
        filepath = Path(gui.dialog.selectfile())     
        self.dirEdit.setText(str(filepath.parent))
        self.fileNameEdit.setText(filepath.name)
        
    def loadFile(self):
        fileName = self.fileNameEdit.text()
        
        if fileName.strip() == '':
            fullFileName = Path(gui.getfilename(file=self.dirEdit.text()))
            self.dirEdit.setText(str(fullFileName.parent))
            self.fileNameEdit.setText(str(fullFileName.name))
        
        self.loadCall(self.fullFileName)

    def savefile(self):
        fileName = self.fileNameEdit.text()
        
        if fileName.strip() == '':
            fullFileName = Path(gui.putfilename())
            self.dirEdit.setText(str(fullFileName.parent))
            self.fileNameEdit.setText(str(fullFileName.name))
            
        elif self.fullFileName.exists():
            if not gui.question('File exists. Do you want to overwrite?'):                
                fullFileName = Path(gui.putfilename())
                self.dirEdit.setText(str(fullFileName.parent))
                self.fileNameEdit.setText(str(fullFileName.name))                
            
        self.saveCall(self.fullFileName)
            
    def editfile(self):
        from gdesk import shell
        shell.edit_file(self.fullFileName)

    def text(self):
        return str(self.fullFileName)
        
    def setText(self, text):
        fullFileName = Path(text)
        self.dirEdit.setText(str(fullFileName.parent))
        self.fileNameEdit.setText(str(fullFileName.name))      

class MyTable(QtWidgets.QTableWidget):

    def __init__(self, headers):
        self.headers = headers
        colcount = len(headers)
        super().__init__(1, colcount)  
        self.setHorizontalHeaderLabels(self.headers)
        
class FormFile(FileLayout):

    def __init__(self, cfg):
        super().__init__(text=cfg.get('text', ''), edit=cfg.get('edit', False))

    def setContent(self, content):
        self.setText(content)
        
    def getContent(self):
        return self.text()
        
        
class FormLineEdit(QtWidgets.QLineEdit):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def setContent(self, content):
        self.setText(content)
        
    def getContent(self):
        return self.text()    
        

class FormTextEdit(QtWidgets.QPlainTextEdit):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)
        
    def setContent(self, content):
        self.setPlainText(content)
        
    def getContent(self):
        return self.toPlainText()            
        

class FormTable(QtWidgets.QWidget):

    def __init__(self, cfg):
        super().__init__()
        vbox = QtWidgets.QVBoxLayout()
        vbox.setContentsMargins(0,0,0,0)
        vbox.setMargin(0)
        self.setLayout(vbox)
        
        hbox = QtWidgets.QHBoxLayout()
        vbox.addLayout(hbox)                      
        
        self.addBtn = QtWidgets.QToolButton()
        self.addBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'table_row_insert.png')))
        self.addBtn.clicked.connect(self.addItem)
        hbox.addWidget(self.addBtn)
        
        self.deleteBtn = QtWidgets.QToolButton()
        self.deleteBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'table_row_delete.png')))
        self.deleteBtn.clicked.connect(self.deleteItem)
        hbox.addWidget(self.deleteBtn)
        
        self.moveUpBtn = QtWidgets.QToolButton()
        self.moveUpBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'table_rows_insert_above_word.png')))
        self.moveUpBtn.clicked.connect(self.moveUp)
        hbox.addWidget(self.moveUpBtn)
        
        self.moveDownBtn = QtWidgets.QToolButton()
        self.moveDownBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'table_rows_insert_below_word.png')))
        self.moveDownBtn.clicked.connect(self.moveDown)
        hbox.addWidget(self.moveDownBtn)        
        
        # self.lineEdit = QtWidgets.QLineEdit()
        # hbox.addWidget(self.lineEdit)
        hbox.addStretch()
                
        self.table = MyTable(cfg.get('headers', ['None']))
        vbox.addWidget(self.table)
        
    def addItem(self):
        self.table.setRowCount(self.table.rowCount() + 1)
        
    def deleteItem(self):
        self.table.setRowCount(self.table.rowCount() - 1) 

    def moveUp(self):
        rownr = self.table.selectedIndexes()[0].row()
        if rownr > 0:
            self.swapRow(rownr, rownr-1) 
            self.table.selectRow(rownr-1)
        
    def moveDown(self):
        rownr = self.table.selectedIndexes()[0].row()
        if rownr < (self.table.rowCount() - 1):
            self.swapRow(rownr, rownr+1)
            self.table.selectRow(rownr+1)
        
    def swapRow(self, rowNr0, rowNr1):
        row0 = self.takeRow(rowNr0)
        row1 = self.takeRow(rowNr1)
        self.setRow(rowNr0, row1)
        self.setRow(rowNr1, row0)
        
    def takeRow(self, rownr):
        row = []
        for colnr in range(self.table.columnCount()):
            row.append(self.table.takeItem(rownr, colnr))
        return row
        
    def setRow(self, rownr, row):
        for colnr, item in enumerate(row):
            self.table.setItem(rownr, colnr, item)
        return row        
        
    def getContent(self):
        content = []
        table = self.table
        for r in range(table.rowCount()):
            item = dict()
            for c in range(table.columnCount()):
                header = table.horizontalHeaderItem(c).text()
                cell = table.item(r, c)
                if not cell is None:
                    text = cell.text()
                    item[header] = text
                else:
                    item[header] = None
            content.append(item)
        return content
        
    def setContent(self, content):
        table = self.table
        table.setRowCount(len(content))
        
        for r, item in enumerate(content):
            for key, val in item.items():
                c = table.headers.index(key)
                table.setItem(r, c, QtWidgets.QTableWidgetItem(val))
      
        table.resizeColumnsToContents()


class CustomForm(QtWidgets.QWidget):
    def __init__(self, cfg):
        super().__init__()
        
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)       
        
        self.flay = flay = QtWidgets.QFormLayout()
        flay.setVerticalSpacing(5)
        self.setLayout(flay)

        self.widgets = OrderedDict()
        self.widgetsMeta = dict()                
        
        self.setWidgets(cfg)        
        
    def setWidgets(self, cfg):        
        for item in cfg:
            self.addFormItem(item['key'], item['caption'], '', item['widget_type'],
                item.get('description', None),
                item.get('widget_config', {}))
        
    def getWidgetsConfig(self):
        widgetsConfig = list()
        
        for key, widget in self.widgets.items():
            meta = self.widgetsMeta[key]
            item = {'key': key, 'caption': meta['caption'], 'widget_type': meta['widget_type']}
            widgetsConfig.append(item)
            
        return widgetsConfig
        
    def addFormItem(self, key, caption, content=None, widgetType='FormLineEdit', description=None, widget_cfg=None):
        if widgetType == 'FormLineEdit':
            widget = FormLineEdit()
            widget.setContent(content)
            
        elif widgetType == 'FormTextEdit':
            widget = FormTextEdit()
            widget.setContent(content)
            
        elif widgetType == 'FormTable':
            widget = FormTable(widget_cfg)  

        elif widgetType == 'FormFile':
            widget = FormFile(widget_cfg)     
            
        self.widgets[key] = widget
        self.widgetsMeta[key] = {'caption': caption, 'widget_type': widgetType}
        captionLabel = QtWidgets.QLabel(caption)
        if not description is None:
            captionLabel.setToolTip(description)
        self.flay.addRow(captionLabel, widget)        
                
    def setContent(self, cfg):
        for key, widget in self.widgets.items():
            if not key in cfg.keys():
                logger.warn(f'{key} not found')
                continue
            widget.setContent(cfg[key])
        
    def getContent(self):                
        cfg = dict()        
        
        for key, widget in self.widgets.items():
            cfg[key] = widget.getContent()                                
        
        return cfg  

class TemplateScrollForm(QtWidgets.QScrollArea):        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWidgetResizable(True)        
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)            
        
    def setWidgets(self, cfg):
        self.form = CustomForm(cfg)
        self.setWidget(self.form)        
        
    # def setContent(self, cfg):
        # self.form.setContent(cfg)
        
    # def getContent(self):
        # return self.form.getContent()                    

        
class TemplateWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        vbox = QtWidgets.QVBoxLayout()
        vbox.setContentsMargins(5,5,5,5)
        vbox.setMargin(5)
        self.setLayout(vbox)

        flay = QtWidgets.QFormLayout()
        vbox.addLayout(flay)        

        self.formConfig = QtWidgets.QLineEdit()
        self.formConfig.setReadOnly(True)
        flay.addRow('Form', self.formConfig)        

        self.settingsFileName = DirFileLayout('',
            loadCall=self.loadValues, saveCall=self.saveValues)
        flay.addRow('Settings', self.settingsFileName)

        self.templateForm = TemplateScrollForm(self)
        vbox.addWidget(self.templateForm)

        flay = QtWidgets.QFormLayout()
        vbox.addLayout(flay)

        self.codeTemplate = QtWidgets.QLineEdit()
        self.codeTemplate.setReadOnly(True)
        flay.addRow('Script Template', self.codeTemplate)

        self.scriptFileName = FileLayout('', save=True)
        flay.addRow('Script', self.scriptFileName)      

        hbox = QtWidgets.QHBoxLayout()
        hbox.setMargin(0)
        vbox.addLayout(hbox)

        self.makeBtn = QtWidgets.QPushButton('Make')
        self.makeBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'script_lightning.png')))
        self.makeBtn.clicked.connect(self.make)            

        hbox.addWidget(self.makeBtn)
        
    @property
    def form(self):
        return self.templateForm.widget()
        
    def loadValues(self, filepath):
        if filepath.suffix.lower() in ['.toml']:
        
            import toml        
            cfg = toml.load(str(filepath))
            
        elif filepath.suffix.lower() in ['.json']: 
        
            with open(filepath, 'r') as fp:
                cfg = json.load(fp)
            
        self.form.setContent(cfg['params'])
        
        for call in cfg['calls']:
            self.runTab.setFormWidgets(call['call'], updateCombo=True)        
            self.runTab.form.setContent(call['kwargs'])        
            self.runTab.returnRef.setText(call['retref'])        
        
    def saveValues(self, filepath):
        cfg = dict()
        cfg['params'] = self.form.getContent()
        cfg['calls'] = [{'call': self.runTab.funcName.currentText(), 'retref': self.runTab.returnRef.text(), 'kwargs': self.runTab.form.getContent()}]
        
        if filepath.suffix.lower() in ['.toml']:
        
            import toml           
            with open(filepath, 'w') as fp:
                toml.dump(cfg, fp)
                
        elif filepath.suffix.lower() in ['.json']:  
            
            with open(filepath, 'w') as fp:
                json.dump(cfg, fp,  indent='    ')
            
    @property    
    def runTab(self):
        return self.parent().parent().runTab
                
    def make(self):                
        templateFileName = self.codeTemplate.text()                
        
        cfg = self.form.getContent()        
        scriptFileName = self.scriptFileName.text()                               
        
        templ_grab = Template(open(templateFileName, 'r').read())                        
        pycode = templ_grab.render(**cfg)
    
        with open(scriptFileName, 'w') as fp:
            fp.write(f'# Created by ninja2 from template {templateFileName}\n')
            fp.write(pycode)
            
        self.runTab.scriptFileWidget.setText(scriptFileName)
            
            
class RunScrollForm(QtWidgets.QScrollArea):        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWidgetResizable(True)        
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)            
        
    def setWidgets(self, cfg):
        self.form = CustomForm(cfg)
        self.setWidget(self.form)        
        
    def setContent(self, cfg):
        self.form.setContent(cfg)
        
    def getContent(self):
        return self.form.getContent()              
            
        
class RunWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)        
        
        vbox = QtWidgets.QVBoxLayout()
        vbox.setContentsMargins(5, 5, 5, 5)
        vbox.setMargin(5)
        self.setLayout(vbox)
        
        flay = QtWidgets.QFormLayout()
        vbox.addLayout(flay)         
        
        self.scriptFileWidget = FileLayout('')
        flay.addRow('Script', self.scriptFileWidget)        
        
        hbox = QtWidgets.QHBoxLayout()
        self.funcName = QtWidgets.QComboBox()
        self.funcName.setEditable(False)
        self.funcName.currentIndexChanged.connect(self.funcNameIndexChanged)
        hbox.addWidget(self.funcName)
        self.locateBtn = QtWidgets.QPushButton('Locate')
        self.locateBtn.clicked.connect(self.locate)
        hbox.addWidget(self.locateBtn)                
        
        flay.addRow('Function', hbox)        
        
        self.callerEdit = QtWidgets.QLineEdit('')
        flay.addRow('Caller', self.callerEdit)
        
        self.settingsFileName = FileLayout('',
            loadCall=self.loadValues, saveCall=self.saveValues)
        flay.addRow('Settings', self.settingsFileName)        
        
        self.runScrollForm = RunScrollForm()
        vbox.addWidget(self.runScrollForm)
        
        flay = QtWidgets.QFormLayout()
        vbox.addLayout(flay)         
        
        self.returnRef = QtWidgets.QLineEdit()
        flay.addRow('Return Reference', self.returnRef)        
        
        hbox = QtWidgets.QHBoxLayout()
        vbox.addLayout(hbox)                                    
        
        self.runBtn = QtWidgets.QPushButton('Run')
        self.runBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'script_go.png')))
        self.runBtn.clicked.connect(self.run)
        hbox.addWidget(self.runBtn)   

        self.widgetConfigs = dict()

    @property
    def form(self):
        return self.runScrollForm.widget()

    def addFormWidgetsConfig(self, funcName, cfg):
        self.widgetConfigs[funcName] = cfg
        self.funcName.addItem(funcName)
        
    def setFormWidgets(self, funcName, updateCombo=False):
        cfg = self.widgetConfigs[funcName]
        self.runScrollForm.setWidgets(cfg)  
        if updateCombo:
            index = self.funcName.findText(funcName)        
            self.funcName.setCurrentIndex(index)
        
    def clearFormWidgets(self):        
        while self.funcName.count() > 0:
            self.funcName.removeItem(0)
        self.widgetConfigs.clear()

    @property
    def scriptFileName(self):        
        return self.scriptFileWidget.text()
        
    def funcNameIndexChanged(self, *args):
        funcName = self.funcName.currentText()
        if funcName == '': return
        self.setFormWidgets(funcName)
        
    def locate(self):
        from gdesk import shell, use
        
        scriptFileName = Path(self.scriptFileName).resolve()
        funcName = self.funcName.currentText()
        console = gui.qapp.panels.selected('console')
        
        for path in use.__script_manager__.path:
            try:
                use_path = scriptFileName.relative_to(Path(path).resolve())
                break
            except:
                pass    
        else:
            logger.warn('Could not locate script')

        self.callerEdit.setText(f'{use_path.stem}.{funcName}')


    def loadValues(self, filepath):
        if filepath.suffix.lower() in ['.toml']:
        
            import toml        
            cfg = toml.load(str(filepath))
            
        elif filepath.suffix.lower() in ['.json']: 
        
            with open(filepath, 'r') as fp:
                cfg = json.load(fp)
            
        self.form.setContent(cfg)
        
    def saveValues(self, filepath):
        cfg = self.form.getContent()
        
        if filepath.suffix.lower() in ['.toml']:
            import toml           
            with open(filepath, 'w') as fp:
                toml.dump(cfg, fp)
                
        elif filepath.suffix.lower() in ['.json']:            
            with open(filepath, 'w') as fp:
                json.dump(cfg, fp,  indent='    ')
        
        
    def run(self):
        from gdesk import shell, use
        
        cfg = self.form.getContent()
        
        console = gui.qapp.panels.selected('console')        
        self.locate()                 
            
        module_func = self.callerEdit.text()
        parts = module_func.split('.')
        module, func = '.'.join(parts[:-1]), parts[-1]            

        retref = self.returnRef.text().strip()
        
        console.exec_cmd('use.__script_manager__.update_now()')

        if not retref == '':
            console.exec_cmd(f'{retref} = use("{module}").{func}(**{cfg})')
        else:
            console.exec_cmd(f'use("{module}").{func}(**{cfg})')
        
        
class ScriptTabs(QtWidgets.QTabWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)      

        self.templateTab = TemplateWidget()
        self.runTab = RunWidget()
        
        self.addTab(self.templateTab, 'Template')
        self.addTab(self.runTab, 'Run')
        
    @property
    def scriptFileName(self):
        return self.templateTab.scriptFileName.text()
        
class WrapCaller(object):
    def __init__(self, caller, *args, **kwargs):
        self.caller = caller
        self.args = args
        self.kwargs = kwargs
                
    def __call__(self):
        self.caller(*self.args, **self.kwargs)
        
class RecentMenu(QtWidgets.QMenu):
    def __init__(self, parent=None):
        super().__init__('Recent', parent)
        self.scriptPanel = self.parent()
        #self.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'images.png')))
        
    def showEvent(self, event):
        self.initactions()        

    def initactions(self):
        self.clear()        
        self.actions = []

        for rowid, timestamp, path in gui.qapp.history.yield_recent_paths(category='scriptwiz'):                                
            action = QtWidgets.QAction(path, self)
            action.triggered.connect(WrapCaller(self.scriptPanel.openTemplate, path))
            self.addAction(action)
            self.actions.append(action)         

class ScriptWizardPanel(BasePanel):
    panelCategory = 'scriptwiz'
    panelShortName = 'basic'
    userVisible = True
    
    classIconFile = str(respath / 'icons' / 'px16' / 'script_bricks.png')

    def __init__(self, parent, panid):
        super().__init__(parent, panid, type(self).panelCategory)
        
        self.fileMenu = CheckMenu("&File", self.menuBar())
        
        self.addMenuItem(self.fileMenu, 'Open Template', self.openTemplateDialog, 
            statusTip="Open a script template")
            
        self.fileMenu.addMenu(RecentMenu(self))  
            
        self.addMenuItem(self.fileMenu, 'Load Values', self.loadValues, 
            statusTip="Load Values")     

        self.addMenuItem(self.fileMenu, 'Save Values', self.saveValues, 
            statusTip="Save Values")             
        
        self.addMenuItem(self.fileMenu, 'Close', self.close_panel, 
            statusTip="Close this levels panel",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'cross.png')))        
        
        self.tabs = ScriptTabs()
        self.setCentralWidget(self.tabs)
        
        self.addBaseMenu()
        self.statusBar().hide()
        
    @property
    def templateTab(self):
        return self.tabs.templateTab
        
    @property
    def runTab(self):
        return self.tabs.runTab
        
    def openTemplateDialog(self):
        filename = gui.getfilename('*.json', 'Open Script Template')
        self.openTemplate(filename)
    
    def openTemplate(self, filename):    
        from gdesk import shell, use
        
        scm = use.__script_manager__
        filename = Path(filename)              
        
        cfg = json.load(open(filename, 'r'))
        
        gui.qapp.history.storepath(str(filename), category='scriptwiz')
        
        self.templateTab.formConfig.setText(str(filename))        
        self.templateTab.templateForm.setWidgets(cfg.get('form', {}))           
        
        self.templateTab.settingsFileName.setText(str(filename.parent / cfg.get('settings_file', '')))
        self.templateTab.codeTemplate.setText(str(filename.parent / cfg['code_template']))        
        self.templateTab.scriptFileName.setText(str(Path(scm.path[0]) / cfg.get('script', '')))
        
        self.runTab.clearFormWidgets()
        
        calls = cfg.get('calls', [])        
        
        for call in calls:       
            funcName = call.get('call')            
            self.runTab.addFormWidgetsConfig(funcName, call.get('form', {}))
            
        default_call = cfg.get('default_call', None)
        index = self.runTab.funcName.findText(default_call)
        self.runTab.funcName.setCurrentIndex(index)
        
    def loadValues(self):
        import toml
        valuesFile = gui.getfilename('*.toml')
        cfg = toml.load(valuesFile)
        self.templateTab.form.setContent(cfg)
        
    def saveValues(self):
        import toml
        valuesFile = gui.putfilename('*.toml')
        cfg = self.templateTab.form.getContent()
        with open(valuesFile, 'w') as fp:
            toml.dump(cfg, fp)
