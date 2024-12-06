import pathlib
from functools import wraps
from ... import config

if config.get('qapp', False):
    #Do not import anything from Qt if not needed !!!
    #Causes crach in Canvas !
    from qtpy import QtWidgets
    from ...dialogs import formlayout    
    from ...dialogs.filterlist import FilterList    
    from ...dialogs import base as dialogs
    from ...dicttree.widgets import DictionaryTreeDialog
    from ...dialogs.textbrowser import TextBrowser
    
from ...core.gui_proxy import gui, GuiProxyBase, StaticGuiCall
      
class DialogGuiProxy(GuiProxyBase):    
    category = 'values'
    
    def __init__(self):
        pass
        
    def attach(self, gui):
        gui.dialog = self
        gui.question = self.question
        gui.msgbox = self.msgbox
        gui.inputdlg = self.inputdlg
        gui.getstring = self.getstring
        gui.getfile = self.getfile
        gui.getfiles = self.getfiles
        gui.getfilename = self.getfilename        
        gui.getfilenames = self.getfilenames
        gui.getpath = self.getpath
        gui.getdir = self.getdir
        gui.putdir = self.putdir
        gui.putfile = self.putfile
        gui.putfilename = self.putfilename
        gui.filterlist = self.filterlist       
        gui.fedit = self.fedit       
        gui.dedit = self.dedit       
                
    @StaticGuiCall
    def msgbox(message, title = '', icon = 'none'):
        """
        Creates a message box
        
        :param message: the message
        :type message: str
        :param title: the title
        :type title: str
        :param icon: 'none', 'help, 'info', 'warn', 'error'
        :type icon: str
        """
        dialogs.messageBox(message, title, icon)         
        
    @StaticGuiCall
    def question(question='Do you press the No Button?', title='Question'):
        """Yes/No question"""
        return dialogs.questionBox(question, title)         
     
    @StaticGuiCall
    def inputdlg(prompt='', default='', title='Input', masked=False, timeout=None):
        """
        Open a input dialog. The user can enter a string.
        
        :param str prompt: The prompt
        :param str default: The default string
        :param str title: The title of the dialog
        :param bool masked: Mask the string as stars `******`
        :param timeout: After time, continue the flow. Expressed in miliseconds
        :type timeout: None or float
        :returns: The user string
        :rtype: str
        
        Timeout can not be combined with mask.        
        """
        if isinstance(prompt, str):
            if masked :
                return dialogs.getString(prompt, default, title, 'Password')
            else:
                return dialogs.getStringTimeout(prompt, default, title, timeout=timeout)
        else:
            return dialogs.getMultiString(prompt, default, title, timeout=timeout)       
                        
    @StaticGuiCall
    def getstring(prompt='', default='', title='Input', echo='Normal', timeout=None):
        """
        Show a popup-window to ask the user some textual input.

        Makes use of QtWidgets.QInputDialog.getText; see
        https://srinikom.github.io/pyside-docs/PySide/QtGui/QInputDialog.html#PySide.QtGui.PySide.QtGui.QInputDialog.getText

        :param str prompt: The explanation that is visible just above the text input field.
        :param str default: The text that is already present in the editable input field.
        :param str title: The name of the pop-window (shown in its title bar).
        :param str echo: 'Normal' for normal text entry; 'Password' for password entry. See
          http://doc.qt.io/qt-4.8/qlineedit.html#EchoMode-enum
        """                
        if timeout is None:
            return dialogs.getString(prompt, default, title, echo=echo)
            
        else:
            return dialogs.getStringTimeout(prompt, default, title, echo=echo, timeout=timeout)    

    @StaticGuiCall
    def getfile(filter='*.*', title='open', file=None):
        r"""
        Show a file dialog to open a file.
        Return a string tuple of  file path and choosen filter
        
        :param str filter: a filter of the form \\*.tif
        :param str title: the window title
        :param str file: default file path
        :return: The file path and choosen filter
        :rtype: tuple(str, str)
        """
        return dialogs.getFile(filter, title, file)    
    
    @staticmethod
    def getfilename(filter='*.*', title='open', file=None):    
        return DialogGuiProxy.getfile(filter, title, file)[0]
        
    @StaticGuiCall
    def getfiles(filter='*.*', title='open', file=None):
        """
        Multi file selection version of getfile
        """
        return dialogs.getFiles(filter, title, file)  
    
    @staticmethod    
    def getfilenames(filter='*.*', title='open', file=None):
        """
        Multi file selection version of getfilename
        """
        return DialogGuiProxy.getfiles(filter, title, file)[0]
        
    @StaticGuiCall
    def selectfile(filter='*.*', title='Select', default_path=None):
        selected_files = dialogs.selectFiles(filter, title, default_path)
        if len(selected_files) == 0: return None
        return selected_files[0]        
    
    @staticmethod    
    def getpath(startpath=None, title='Select a Directory'):
        """
        Show a directory dialog to choose a dir
        :return: The directory
        :rtype: pathlib.Path
        """        
        return pathlib.Path(DialogGuiProxy.getdir(startpath, title))   
        
    @StaticGuiCall
    def getdir(startpath=None, title='Select a Directory'):
        """
        Show a directory dialog to choose a dir
        
        :returns: The directory
        :rtype: str
        """
        return dialogs.getMap(startpath, title)    

        
    @StaticGuiCall
    def putdir(startpath='.', title='Create a New Directory'):
        """
        Show a directory dialog to choose a new dir
        
        :returns: The directory
        :rtype: str
        """
        return dialogs.getNewMap(startpath, title)        

    @StaticGuiCall
    def putfile(filter='*.*', title='save', file=None, defaultfilter=""):
        r"""
        Open a save file dialog and return a file name selected by the user.
        The file does not have to exist.
                        
        :param str filter: File type filter, filters are seperated by ``;;``
            e.g.: \\*.tif, Image (\\*.tif \\*.png), Text(\\*.txt);;Image (\\*.tif \\*.png)
        :param str title: Title of the dialog
        :param file: Propose of file name
        :type file: str or None
        :param str defaultfilter: Default filter to use                
        
        :returns: The filename and used filter
        :rtype: str, str
        
        Example
        
        >>> filename, filter = gui.putfile('Text(*.txt);;Image (*.tif *.png)', "Give it a filename", r"C:\\temp\\default.tif", "Image (*.tif *.png)")
        """    
        return dialogs.putFile(filter, title, file, defaultfilter)  

    @staticmethod
    def putfilename(filter='*.*', title='save', file=None, defaultfilter=""):
        r"""       
        Open a save file dialog and return a file name selected by the user.
        The file does not have to exist.
                        
        :param str filter: File type filter, filters are seperated by ``;;``
            e.g.: \\*.tif, Image (\\*.tif \\*.png), Text(\\*.txt);;Image (\\*.tif \\*.png)
        :param str title: Title of the dialog
        :param file: Propose of file name
        :type file: str or None
        :param str defaultfilter: Default filter to use
        
        :returns: The filename
        :rtype: str
        
        Example
        
        >>> filename = gui.putfile('Text(*.txt);;Image (*.tif *.png)', "Give it a filename", r"C:\\temp\\default.tif", "Image (*.tif *.png)")
        """
        return DialogGuiProxy.putfile(filter, title, file, defaultfilter)[0]          

    @StaticGuiCall
    def filterlist(items=None, selection=None, filter=None, title='Items'):
        r"""
        Open a items filter dialog.
        The user have to select items from it.
        
        selection = None : select nothing
                  = one_item : select the one item
                  = []: use checkable items
                  = [str1, str2] : check items on string value
        filter    = None: check nothing
                  = False: check everything
                  = ``\w*01\w*``: use re to match string
        """                
        if items is None:
            items = list()        
        
        if isinstance(selection, list): 
            multiple = True
        else:
            multiple = False

        fl = FilterList(items, multiple, title=title)        
        
        if not multiple:
            if not selection is None:
                fl.selectItem(selection)
            
        else:
            if filter is False:
                fl.checkAll(True)

            elif isinstance(filter, str):
                fl.checkItemsRe(filter) 
                
            elif isinstance(selection, list):
                fl.checkItems(selection)                                       
            
        dialog_code = fl.exec_()
        
        if dialog_code == QtWidgets.QDialog.DialogCode.Rejected:
            return None
        
        if multiple:
            return fl.checkedItems()
        else:
            return fl.selectedItem()        
            
            
    # TO DO: formlayout.fedit doc string can not be available if the process
    #        is not allowed to load QT (like Canvas GUI)
    @StaticGuiCall
    # @wraps(formlayout.fedit)
    def fedit(*args, **kwargs):
        """
        Create form dialog and return result
        (if Cancel button is pressed, return None)

        :param tuple data: datalist, datagroup (see below)
        :param str title: form title
        :param str comment: header comment
        :param QIcon icon: dialog box icon
        :param QWidget parent: parent widget
        :param str ok: customized ok button label
        :param str cancel: customized cancel button label
        :param tuple apply: (label, function) customized button label and callback
        :param function apply: function taking two arguments (result, widgets)
        :param str result: result serialization ('list', 'dict', 'OrderedDict',
                                                 'JSON' or 'XML')
        :param str outfile: write result to the file outfile.[py|json|xml]
        :param str type: layout type ('form' or 'questions')
        :param bool scrollbar: vertical scrollbar
        :param str background_color: color of the background
        :param str widget_color: color of the widgets

        :return: Serialized result (data type depends on `result` parameter)
        
        datalist: list/tuple of (field_name, field_value)
        datagroup: list/tuple of (datalist *or* datagroup, title, comment)
        
        Tips:
          * one field for each member of a datalist
          * one tab for each member of a top-level datagroup
          * one page (of a multipage widget, each page can be selected with a 
            combo box) for each member of a datagroup inside a datagroup
           
        Supported types for field_value:
          - int, float, str, unicode, bool
          - colors: in Qt-compatible text form, i.e. in hex format or name (red,...)
                    (automatically detected from a string)
          - list/tuple:
              * the first element will be the selected index (or value)
              * the other elements can be couples (key, value) or only values
        """    
        return formlayout.fedit(*args, **kwargs)         
        
    @StaticGuiCall
    def dedit(*args, **kwargs):
        dt = DictionaryTreeDialog(*args, **kwargs)
        dt.edit()
        return dt.to_dict_list()
        
       
    @StaticGuiCall       
    def textbrowser(content: str='No content', title: str='HTML', icon: str=None):        
        window = TextBrowser(content, title, icon)
        window.exec_()
        
