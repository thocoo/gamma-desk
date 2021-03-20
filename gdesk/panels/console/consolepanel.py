import os
import textwrap
import psutil
import time
from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets

from qtpy.QtCore import Qt, QTimer, QSize
from qtpy.QtGui import QFont, QFontMetrics, QTextCursor, QTextOption, QPainter, QTextCharFormat
from qtpy.QtWidgets import (QAction, QMainWindow, QPlainTextEdit, QSplitter, QVBoxLayout, QLineEdit, QLabel,
    QMessageBox, QTextEdit, QWidget, QStyle, QStyleFactory, QApplication, QCompleter, QComboBox)

from ... import config, gui
from ...core import tasks
from ...core.shellmod import Shell
from ...panels.base import BasePanel, selectThisPanel, CheckMenu
from ...dialogs.formlayout import fedit
from ...dialogs.base import messageBox
from ...dialogs.editpaths import EditPaths
from ...utils.syntax_light import analyze_python, ansi_highlight
from ...utils.ansi_code_processor import QtAnsiCodeProcessor
from ...gcore.utils import getMenuAction

respath = Path(config['respath'])

MAXCHARPERLINE = 10000  #Only for ansi mode
#PREFIXWIDTH = 30  # width of the left side line numbers

ANSI_ESCAPE_SYNTAX_HIGHLIGHT = {
    'comment': ('\033[38;5;2m', '\033[39m'),
    'string': ('\033[38;5;8m', '\033[39m'),
    'docstring': ('\033[38;5;208m', '\033[39m'),
    'keyword': ('\033[38;5;12m', '\033[39m'),
    'builtin': ('\033[38;5;6m', '\033[39m'),
    'definition': ('\033[38;5;12m', '\033[39m'),
    'defname': ('\033[38;5;13m', '\033[39m'),
    'operator': ('\033[38;5;4m', '\033[39m'),
}

ESC = '\033['
ERROR_PREFIX = ESC + '38;5;9m'
ERROR_SUFFIX = ESC + '0m' 


class LineNumberArea(QWidget):

    def __init__(self, textEditor):
        QWidget.__init__(self, textEditor)
        self.textEditor=textEditor
        self.prefix_color = Qt.lightGray
        self.prefix_font_color = Qt.black
        self.update_font()
        
        self._firstlinecode = [' >>> ']
        self.blinks = [':',' ']
        
        self.painter = QPainter()
        
        self.promptTimer = QTimer(self)
        self.promptTimer.timeout.connect(self.nextPrompt)        
        
        self.profile_start = time.monotonic()
        self.profile_threshold = 10
        self.profile_enabled = False
        
    def start_profiling(self):
        self.profile_start = time.monotonic()
        self.profile_enabled = True
        
    def stop_profiling(self):
        self.profile_enabled = False        
        
    def update_font(self):
        self.setFont(self.textEditor.font())
        self.fontmetric = QFontMetrics(self.textEditor.font())
        self.prefixwidth = self.fontmetric.width('12345')
        self.prefixheight = self.fontmetric.height()
        self.setFixedWidth(self.prefixwidth)
        self.textEditor.setViewportMargins(self.prefixwidth, 0, 0, 0)
                
    def set_firstlinecode(self, prefices):
        self._firstlinecode = prefices        
        
        if len(self._firstlinecode) > 1:
            self.promptTimer.start(500)
        else:
            self.promptTimer.stop()
        
    def get_firstlinecode(self):
        if self.profile_enabled:
            elapsed = time.monotonic() - self.profile_start
            if elapsed > self.profile_threshold:                
                if elapsed >= 3600:
                    profile = time.strftime("%H:%M", time.gmtime(elapsed))
                else:
                    profile = time.strftime("%M:%S", time.gmtime(elapsed))                                
                return profile[:-3] + self.blinks[0] + profile[-2:]
        return self._firstlinecode[0]
        
    firstlinecode = property(get_firstlinecode, set_firstlinecode)
        
    def nextPrompt(self):
        self._firstlinecode = self._firstlinecode[1:] + self._firstlinecode[:1]        
        self.blinks = self.blinks[1:] + self.blinks[:1]
        self.repaint()

    def paintEvent(self, event): 
        cursor = self.textEditor.cursorForPosition(self.textEditor.viewport().pos())        
        
        painter = self.painter        
        try:
            painter.begin(self)        
            painter.fillRect(event.rect(), self.prefix_color)

            for i in range(100):
                blockNumber = cursor.block().blockNumber()

                if blockNumber == 0:
                    code = self.firstlinecode
                else:
                    code = str(blockNumber + 1)

                painter.setPen(self.prefix_font_color)
                y = self.textEditor.cursorRect(cursor).y() + self.textEditor.viewport().pos().y() - 2
                painter.drawText(0, y, self.prefixwidth, self.prefixheight, Qt.AlignRight, code)

                if y > event.rect().bottom():
                    break
                if not cursor.block().next().isValid():
                    break

                cursor.movePosition(cursor.NextBlock)     
        finally:
            painter.end()

    def sizeHint(self):
        return QSize(self.prefixwidth, 0) 
        
class StdInputPanel(QPlainTextEdit):
    def __init__(self, parent, task, outputPanel):
        super().__init__(parent = parent)        
        self.task = task
        self.outputPanel = outputPanel
        self.qapp = QApplication.instance()     

        self.prior_cmd_id = None
        self.hist_prefix = None                       
        
        self.configure(config)
        self.lineNumberArea=LineNumberArea(self)
        
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.styles = dict()
        self.styles['interprete'] = "background-color:white;" 
        self.styles['wait'] = "background-color:#DDBBBB;"         
        self.styles['running'] = "background-color:#FFFFE0;"         
        self.styles['input'] = "background-color:#BBBBDD;"                   
        self.styles['ended'] = "background-color:#EFEFEF;"
        
        self.setMinimumHeight(32)
        
        self.mode = 'interprete'
        self.heightHint = 100

    def configure(self, config):  
        console_font = QFont('Consolas', pointSize=config['console']['fontsize'])
        self.setFont(console_font)                
        
        if config['console']['wrap']:
            self.setWordWrapMode(QTextOption.WordWrap)   
        else:
            self.setWordWrapMode(QTextOption.NoWrap)
            
        self.setMaximumBlockCount(config['console']['maxblockcount'])  
        
    def sizeHint(self):
        return QtCore.QSize(200, self.heightHint)        

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect=self.contentsRect()
        self.lineNumberArea.setGeometry(rect.x(),rect.y(), self.lineNumberArea.prefixwidth, rect.height())        
        
    def keyPressEvent(self, event):
        self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height()) 
        
        #Is the enter pressed on numeric keypad or on the base keypad
        key_enter = (event.key() == Qt.Key_Return) or \
            (event.key() == Qt.Key_Enter)        
            
        #left or right shift
        modifiers = event.nativeModifiers()
        key_shift = modifiers & 1 == 1 or  modifiers & 16 == 16
        #left or right ctrl
        key_ctrl = modifiers & 2 == 2 or modifiers & 32 == 32
        
        if not event.key() in [Qt.Key_Up, Qt.Key_Down]:
            self.prior_cmd_id = None
            self.hist_prefix = None
            
        if key_enter:
            if key_ctrl:
                self.execute_commands()
            elif key_shift:
                self.textCursor().insertBlock()
            else:
                if self.blockCount() == 1:
                    self.execute_commands()
                else:                    
                    if self.lastLineIsEmpty():
                        self.execute_commands()
                    else:
                        self.textCursor().insertBlock()                 
            
        elif event.key() == Qt.Key_Tab:
            if key_ctrl or key_shift:
                self.startAutoCompleter(wild=True)
            else:
                self.startAutoCompleter()
                
        elif event.key() == Qt.Key_Up and self.textCursor().block().blockNumber() == 0:
            if self.hist_prefix is None:
                self.hist_prefix = self.toPlainText()
            self.prior_cmd_id, cmd = self.qapp.history.retrievecmd(self.hist_prefix, self.prior_cmd_id, distinct=True, back=True, prefix=not key_ctrl)
            
            self.setPlainText(cmd)
            self.moveCursorToEndOfBlock()                            

        elif event.key() == Qt.Key_Down and self.textCursor().block().blockNumber() == (self.blockCount()-1):
            if self.hist_prefix is None:
                self.hist_prefix = self.toPlainText()
                    
            self.prior_cmd_id, cmd = self.qapp.history.retrievecmd(self.hist_prefix, self.prior_cmd_id, distinct=True, back=False, prefix=not key_ctrl)
            
            self.setPlainText(cmd)
            self.moveCursorToEndOfDoc()      
            
        else:
            super().keyPressEvent(event)
            
    def lastLineIsEmpty(self):
        self.cursor=self.textCursor()
        if self.cursor.block().blockNumber() != (self.blockCount() - 1):
            return False
            
        self.cursor.movePosition(self.cursor.EndOfLine, self.cursor.KeepAnchor)
        curdocpos = self.cursor.position()
        self.cursor.movePosition(self.cursor.StartOfLine, self.cursor.KeepAnchor)
        startlinepos = self.cursor.position()
        
        return curdocpos == startlinepos            

    def startAutoCompleter(self, wild=False):
        
        #delims = ' \t\n\\"\'`@$><=;|&{('                
        delims = ' \t\n\\`@$><=;|&{('
        
        current_text = self.toPlainText()
        
        try:
            pos = min(current_text[::-1].index(c) for c in delims if c in current_text)
            part = current_text[-pos:]
        except:
            pos = len(current_text)
            
        if pos == 0:
            self.insertText('    ')
            return 
            
        self.keep, self.part = current_text[:-pos], current_text[-pos:]
            
        self.outputPanel.addText(f'{self.part}*\n')                
                
        max_items = config['console']['max_complete']
        self.task.call_func(Shell.get_completer_data, (self.part, max_items, wild), self.response_to_autocomplete)
        
    def moveCursorToEndOfBlock(self):
        cursor=self.textCursor()
        cursor.movePosition(cursor.EndOfBlock)
        self.setTextCursor(cursor)    

    def moveCursorToEndOfDoc(self):
        cursor=self.textCursor()
        cursor.movePosition(cursor.End)
        self.setTextCursor(cursor)         
            
    def execute_commands(self, cmd=None):  
        if cmd is None:
            cmd = self.toPlainText()
                
        if self.mode in ['interprete', 'running']:            
            cmd = textwrap.dedent(cmd)
            histcmd = cmd
            
            if cmd.startswith('%'):
                cmd = 'shell.magic(r"""' + cmd[1:]+ '""")'            
            
            elif cmd.startswith('!!'):
                cmd = 'shell.popen(r"""' + cmd[2:] + '""", shell=False)'            
            
            elif cmd.startswith('!'):
                cmd = 'shell.popen(r"""' + cmd[1:] + '""", shell=True)'

            elif cmd.endswith('??'):
                cmd = 'shell.edit(' + cmd[:-2] + ')'        
                
            elif cmd.endswith('?'):
                histcmd = cmd
                cmd = 'help(' + cmd[:-1] + ')'                
                
            elif cmd.endswith('!!'):
                cmd = 'shell.pprint(' + cmd[:-2] + ')'                
                
            elif cmd.endswith('!'):
                cmd = 'print(' + cmd[:-1] + ')'                
                    
            if cmd.count('\n') == 0:
                prefix = '\033[48;5;7m>>>\033[0m \033[1m'
                suffix = '\033[0m\n'
            else:
                prefix = '\033[48;5;7m>>>\n\033[0m\033[1m'
                suffix = '\033[0m\n\033[48;5;7m<<<\033[0m\n'
                
            try:
                cmdecho = ansi_highlight(analyze_python(cmd), colors=ANSI_ESCAPE_SYNTAX_HIGHLIGHT)
            except:
                cmdecho = cmd
                
            self.outputPanel.addAnsiText(prefix + cmdecho + suffix)
                           
            self.qapp.history.logcmd(histcmd)        
            self.task.send_command(cmd, self.retval_ready)
                         
            #self.set_mode('running')
            
            self.clear()
            
        elif self.mode == 'input':                

            if cmd.count('\n') == 0:
                prefix = '\033[48;5;7m>?\033[0m \033[1m'
                suffix = '\033[0m\n'
            else:
                prefix = '\033[48;5;7m>?\n\033[0m\033[1m'
                suffix = '\033[0m\n\033[48;5;7m?<\033[0m\n'
                
            self.outputPanel.addAnsiText(prefix + cmd + suffix)
            self.task.send_input(cmd)
            self.clear()
        
    def retval_ready(self,  mode, error_code, result):        
        if mode == 'interprete':            
            if error_code == 1:
                self.outputPanel.addAnsiText(f'\033[38;5;9msyntax error: {result}\033[0m\n')
                
            elif error_code == 2:
                self.outputPanel.addAnsiText(f'\033[38;5;9mincomplete error: {result}\033[0m\n')
                self.setPlainText(result + '\n')
                self.moveCursorToEndOfDoc()
                
        self.set_mode('interprete')
        
    def set_mode(self, mode='interprete'):
        if mode == 'wait':
            self.setStyleSheet(self.styles[mode])
            self.mode = mode            
            self.lineNumberArea.firstlinecode = [' ... ',
                                                 '  ...',
                                                 '   ..',
                                                 '    .',
                                                 '     ',
                                                 '.    ',
                                                 '..   ',
                                                 '...  ']                                                 
            self.lineNumberArea.start_profiling()
            self.setReadOnly(True)
            
        if mode == 'running':
            self.setStyleSheet(self.styles[mode])
            self.mode = mode            
            self.lineNumberArea.firstlinecode = [' ... ',
                                                 '  ...',
                                                 '   ..',
                                                 '    .',
                                                 '     ',
                                                 '.    ',
                                                 '..   ',
                                                 '...  ']                                                 
            self.lineNumberArea.start_profiling()
            self.setReadOnly(False)            
            
        elif mode == 'interprete':
            self.setStyleSheet(self.styles[mode])
            self.mode = mode            
            self.lineNumberArea.firstlinecode = [' >>> ']
            self.lineNumberArea.stop_profiling()
            self.setReadOnly(False)
            
        elif mode == 'input':
            self.setStyleSheet(self.styles[mode])
            self.mode = mode                   
            self.lineNumberArea.firstlinecode = ['>?   ', '   >?']
            self.lineNumberArea.stop_profiling()
            self.setReadOnly(False)
            
        elif mode == 'ended':
            self.outputPanel.setStyleSheet(self.styles[mode])
            self.hide()
            self.mode = mode            
            self.lineNumberArea.firstlinecode = ['Ended']
            self.lineNumberArea.stop_profiling()
            self.setReadOnly(True)            
            
        self.lineNumberArea.update()

    def response_to_autocomplete(self, tag, error_code, items):        
        if len(items) == 0:
            return
            
        if len(items) == 1:
            self.setPlainText(self.keep + items[0])
            self.moveCursorToEndOfDoc()
            
        else:            
            for item in items:
               self.outputPanel.addText(f'{item}\n')
               
            commonprefix = os.path.commonprefix(items)
           
            if commonprefix != self.part:
                self.setPlainText(self.keep + commonprefix)
                self.moveCursorToEndOfDoc()
                
    def wheelEvent(self, event):
        modifiers = event.modifiers()
        #key_ctrl = modifiers & 2 == 2 or modifiers & 32 == 32
        key_ctrl = modifiers & Qt.ControlModifier
        #key_ctrl = True
        
        #print(modifiers)
        
        if key_ctrl and event.delta() < 0:
            font = self.font()
            font.setPointSize(font.pointSize()-1)
            self.setFont(font)
            
        elif key_ctrl and event.delta() > 0:
            font = self.font()
            font.setPointSize(font.pointSize()+1)
            self.setFont(font)
            
        self.lineNumberArea.update_font()
            
        if not key_ctrl:
            super().wheelEvent(event)   

    # def focusInEvent(self, event):
        # selectThisPanel(self)
        # super().focusInEvent(event)
        
    def replaceSelected(self, text):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        if cursor.hasSelection():
            cursor.insertText(text)
            #end = cursor.position()
            end = start + len(text)
        
        #QTextCursor.KeepAnchor       
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)
        
    def insertText(self, text):
        cursor=self.textCursor()
        cursor.insertText(text)
        
    def addText(self, text):
        cursor=self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.moveCursor(QTextCursor.End)        
        
        
class StdPlainOutputPanel(QPlainTextEdit):
    def __init__(self, parent, stdout_queue):
        super().__init__(parent = parent)        
        self.stdout_queue = stdout_queue
        self.setReadOnly(True)
        self._ansi_processor = None
        
        self.configure(config)
        
    @property
    def panel(self):
        return self.parent().parent().parent()
        
    def configure(self, config):    
        console_font = QFont('Consolas', pointSize=config['console']['fontsize'])
        self.setFont(console_font)
        
        if config['console']['wrap']:
            self.setWordWrapMode(QTextOption.WordWrap)   
        else:
            self.setWordWrapMode(QTextOption.NoWrap)
            
        self.setMaximumBlockCount(config['console']['maxblockcount'])           

    def flush(self):        
        text = ''
        while not self.stdout_queue.empty():
            data = self.stdout_queue.get() 
            if isinstance(data, tuple):
                ttype, content = data
            else:
                ttype = 'raw'
                content = data
            text += content            
        if not text == '':
            if ttype == 'raw':
                self.addText(text)
            elif ttype == 'error':
                self.addAnsiText(f'{ERROR_PREFIX}{text}{ERROR_SUFFIX}')
                self.panel.show_me()
            elif ttype == 'ansi':
                self.addAnsiText(text)
                #Some bug, reset format to normal
                #self.addAnsiText('\n')

    def addText(self, text):
        cursor=self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.moveCursor(QTextCursor.End)
        
    def addAnsiText(self, text):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)        
        self._insert_ansi_escape_text(cursor, text)
        self.moveCursor(QTextCursor.End)   
        
    def _insert_ansi_escape_text(self, cursor, text):                           
        cursor.beginEditBlock()        
        
        if self._ansi_processor == None:                    
            self._ansi_processor = QtAnsiCodeProcessor()
        
        if len(text) > 0:
            if text[0] == '\r':
                # BUG when no character is preceding the <CR>
                # editor goes to some string state
                text = ' ' + text
                
        for substring in self._ansi_processor.split_string(text):                            
            for act in self._ansi_processor.actions:                    

                # Unlike real terminal emulators, we don't distinguish
                # between the screen and the scrollback buffer. A screen
                # erase request clears everything.
                if act.action == 'erase' and act.area == 'screen':
                    cursor.select(QTextCursor.Document)
                    cursor.removeSelectedText()

                # Simulate a form feed by scrolling just past the last line.
                elif act.action == 'scroll' and act.unit == 'page':
                    cursor.insertText('\n')
                    cursor.endEditBlock()
                    self._set_top_cursor(cursor)
                    cursor.joinPreviousEditBlock()
                    cursor.deletePreviousChar()

                elif act.action == 'carriage-return':
                    cursor.movePosition(
                        cursor.StartOfLine, cursor.KeepAnchor)

                elif act.action == 'beep':
                    gui.qapp.beep()

                elif act.action == 'backspace':            
                    cursor.movePosition(
                        cursor.PreviousCharacter, cursor.KeepAnchor)

                elif act.action == 'newline':
                    cursor.movePosition(cursor.EndOfLine)

            format = self._ansi_processor.get_format()
            
            # This doesn't seem to work with special characters
            # backspace seems to disable the output, no recovery

            selection = cursor.selectedText()
            if len(selection) == 0:
                if substring is None:
                    pass
                elif len(substring) > MAXCHARPERLINE:
                    cursor.insertText(substring[:MAXCHARPERLINE] + "...%d chars not displayed" % (len(substring) - MAXCHARPERLINE), format)
                else:
                    cursor.insertText(substring, format)
                    
            elif substring is not None:
                # BS and CR are treated as a change in print
                # position, rather than a backwards character
                # deletion for output equivalence with (I)Python
                # terminal.
                if len(substring) >= len(selection):
                    cursor.insertText(substring, format)
                else:
                    old_text = selection[len(substring):]
                    cursor.insertText(substring + old_text, format)
                    cursor.movePosition(cursor.PreviousCharacter,
                           cursor.KeepAnchor, len(old_text))
                           
        cursor.setBlockCharFormat(QTextCharFormat())
        cursor.endEditBlock()        
        
    # def focusInEvent(self, event):
        # selectThisPanel(self)  
        # super().focusInEvent(event)        
        
        
class StdOutputPanel(QTextEdit):
    def __init__(self, parent, stdout_queue):
        super().__init__(parent = parent)        
        self.stdout_queue = stdout_queue
        self.setReadOnly(True)
        
        self.configure(config)
        
    def configure(self, config):    
        console_font = QFont('Consolas', pointSize=config['console']['fontsize'])
        self.setFont(console_font)
        
        if config['console']['wrap']:
            self.setWordWrapMode(QTextOption.WordWrap)   
        else:
            self.setWordWrapMode(QTextOption.NoWrap)

    def flush(self):        
        text = ''
        while not self.stdout_queue.empty():
            data = self.stdout_queue.get() 
            if isinstance(data, tuple):
                ttype, content = data
            else:
                content = data
            text += content          
        if not text == '':
            self.addText(text)

    def addText(self, text):
        cursor=self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.moveCursor(QTextCursor.End)    

    def addHtml(self, text):
        cursor=self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(text)
        self.moveCursor(QTextCursor.End) 
        
    # def focusInEvent(self, event):
        # selectThisPanel(self)        
        # super().focusInEvent(event)
        
        
class StdioFrame(QWidget):
    """
    A Window with standard input and output panels
    For threads and processes.
    """
    def __init__(self, parent, title, task):
        super().__init__(parent=parent)
        
        self.task = task
        
        self.setWindowTitle(title)    
        self.stdOutputPanel = StdPlainOutputPanel(self, task.stdout_queue)
        self.stdInputPanel = StdInputPanel(self, task, self.stdOutputPanel)
        
        task.set_flusher(self.stdOutputPanel.flush) 

        splitter = QSplitter(Qt.Vertical, self)
        splitter.addWidget(self.stdOutputPanel)
        splitter.addWidget(self.stdInputPanel)

        vbox = QVBoxLayout()
        self.setLayout(vbox)        
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(splitter)               
        
    def keyPressEvent(self, event):
        pass   
        
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
        self.panel = self.parent()
        
    def showEvent(self, event):
        self.initactions()        

    def initactions(self):
        self.clear()        
        self.actions = []

        for rowid, timestamp, path in gui.qapp.history.yield_recent_paths(category='console'):                                
            action = QtWidgets.QAction(path, self)
            action.triggered.connect(WrapCaller(self.panel.openFile, path))
            self.addAction(action)
            self.actions.append(action)           

class Console(BasePanel):  
    panelCategory = 'console'
    userVisible = False
    
    classIconFile = str(respath / 'icons' / 'px16' / 'application_xp_terminal.png')
    
    def __init__(self, parent, panid, task):
        super().__init__(parent, panid, 'console')        
        
        self.stdio = StdioFrame(self, '', task)
        task.console = self
        self.setCentralWidget(self.stdio)
        self.createMenus()
        self.createStatusBar()
        
        self.stdio.stdOutputPanel.flush()
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateProcessInfo)
        self.timer.start(config['system info period'])  

    @property
    def task(self):
        return self.stdio.task
        
    def createMenus(self):
        self.fileMenu = self.menuBar().addMenu("&File")        
        #self.executionMenu = self.menuBar().addMenu("&Execution")
        
        self.executionMenu = CheckMenu("&Execution", self.menuBar())
        self.menuBar().addMenu(self.executionMenu)                 
            
        self.addMenuItem(self.fileMenu, "Execute Python File", self.exec_file,
            statusTip="Execute Python File",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'script_start.png')))
            
        self.addMenuItem(self.fileMenu, 'Open Image Data Base', self.openIdmDialog)
        self.addMenuItem(self.fileMenu, 'New Thread', self.newThread)
        self.fileMenu.addMenu(RecentMenu(self))
        self.addMenuItem(self.fileMenu, "Close", self.close_panel,
            statusTip = "Close this Thread",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'cross.png')))
        
        traceMenu = QtWidgets.QMenu('tracing')
        traceMenu.addAction(QAction("Enable Tracing", self, triggered=lambda: self.task.set_tracing(True),
            statusTip="Enable Tracing, needed for sync breaks"))
        traceMenu.addAction(QAction("Disable Tracing", self, triggered=lambda: self.task.set_tracing(False),
            statusTip="Disable Tracing"))
        self.addMenuItem(traceMenu, "Enable Timeit", lambda: self.task.set_timeit(True), 
            statusTip="Show elapsed time report at end of execution",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'time_red.png')))
        traceMenu.addAction(QAction("Disable Timeit", self, triggered=lambda: self.task.set_timeit(False),
            statusTip="Disable Timeit"))
        traceMenu.addAction(QAction("Enable profiling", self, triggered=lambda: self.task.enable_profiling(),
            statusTip="One time profiling of the next command"))
        self.executionMenu.addMenu(traceMenu)        
        
        self.addMenuItem(self.executionMenu, 'Check Flow Alive', self.checkAlive,
            statusTip="Check if the flow loop is still alive")
        self.addMenuItem(self.executionMenu, 'Print Trace', self.stdio.task.print_trace,
            statusTip="Print the trace of the current execution frame")
        self.addMenuItem(self.executionMenu, 'Print Locals', self.stdio.task.print_locals,
            statusTip="Print the locals of the current namespace")
        self.addMenuItem(self.executionMenu, 'Sync Break', self.syncBreak, 
            statusTip="Send a synchronous break, tracing should be active",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'cog_stop.png')))
        self.addMenuItem(self.executionMenu, 'Async Break', self.asyncBreak,
            statusTip="Send a asynchronous break",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'cog_stop.png')))
        self.addMenuItem(self.executionMenu, 'System Exit Thread', self.stdio.task.system_exit,
            statusTip="System Exit")
            
        self.executionMenu.addSeparator()           
        
        # self.addMenuItem(self.executionMenu, 'Pause Process', self.suspendResumeProcess,
            # statusTip="Suspend this windows process")
        self.addMenuItem(self.executionMenu, 'Kill Process', self.killProcess, 
            statusTip="Kill this Python Process and its threads",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'scull.png')))
        
        self.viewMenu = CheckMenu("&View", self.menuBar())
        self.menuBar().addMenu(self.viewMenu)            
        
        self.addMenuItem(self.viewMenu, 'input', self.toggleInputVisible, 
            checkcall=lambda: self.stdio.stdInputPanel.isVisible())        
        
        scripMenu = self.menuBar().addMenu("&Script")
        self.addMenuItem(scripMenu, 'Edit sys.path...', self.editSysPaths,
            statusTip="Edit the search path used to import Python packages",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'application_view_list.png')))
        self.addMenuItem(scripMenu, 'Edit Live paths...', self.editLivePaths,
            statusTip="Edit the search path used to import user live scripts",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'script_gear.png')))

        self.addBaseMenu() 
        
    def createStatusBar(self):
        self.tasktype = QLabel('')
        self.pid = QLabel('Pid:0')
        self.pname = QLabel('Name:')
        self.tid = QLabel('Tid:0')
        self.pmem = QLabel('Mem:')
        
        self.statusBar().addWidget(self.tasktype,1)         
        self.statusBar().addWidget(self.pid,1)         
        self.statusBar().addWidget(self.pname,1)         
        self.statusBar().addWidget(self.tid,1)
        self.statusBar().addWidget(self.pmem,1)
                    

    def refresh_pid_tid(self):
        self.pid.setText(f'Pid:{self.stdio.task.process_id}')
        self.tid.setText(f'Tid:{self.stdio.task.thread_id}')
        self.long_title = f'{self.short_title} Pid {self.stdio.task.process_id} Tid {self.stdio.task.thread_id}'
        
    def updateProcessInfo(self):
        if self.stdio.task.process_id == -1:
            return
            
        try:        
            proc = psutil.Process(self.stdio.task.process_id)
        except:
            return
            
        self.tasktype.setText(f'{self.stdio.task.tasktype}')
        self.pname.setText(f'Name:{proc.name()}')
        self.tid.setText(f'Tid:{self.stdio.task.thread_id}/{proc.num_threads()}')
        self.pmem.setText(f'Mem:{proc.memory_full_info().rss / 1024 / 1024:.4g} MB')        
        
    def set_mode(self, mode):
        self.stdio.stdInputPanel.set_mode(mode)        
        
    def newThread(self):
        self.duplicate()
        
    def checkAlive(self):
        def response(mode, error_code, result):
            messageBox(f'Mode: {mode}\nError Code: {error_code}\nResult: {result}', 'Info', 'Info')
            
        self.stdio.task.flow_alive(response, 5)
        
    def suspendResumeProcess(self):
        proc = psutil.Process(self.stdio.task.process_id)        
        
        if proc.status() == 'running':
            proc.suspend()
            
        elif proc.status() == 'stopped':
            proc.resume()       
        
    def killProcess(self):
        proc = psutil.Process(self.stdio.task.process_id)        
        
        mem = proc.memory_full_info().rss / 1024 / 1024
        
        if gui.dialog.question(f'Kill this following Process?\nExecutable: {proc.exe()}\nProcess id: {proc.pid} Cpu: {proc.cpu_percent(0.1)}% Mem: {mem:.4g}MB'):
            self.stdio.task.kill()
            
    def syncBreak(self):
        self.stdio.task.sync_break()
            
    def asyncBreak(self):
        self.stdio.task.async_break()                     
        
    def exec_cmd(self, cmd):
        self.stdio.stdInputPanel.execute_commands(cmd)
    
    def exec_file(self):
        cmd = """exec(open(gui.getfilename('*.py'),'r').read())"""
        self.exec_cmd(cmd)
        
    def openFile(self, filepath):    
        filepath = Path(filepath)
        
        print(f'<{filepath}>')
        
        if filepath.suffix == '.db':
            self.openIdm(filepath)

    def openIdmDialog(self, filepath):            
        filepath = gui.dialog.getfilename('*.db')
        self.openIdm(filepath)
        
    def openIdm(self, filepath):        
        ref = gui.dialog.getstring('Give reference name', 'idminst')
                
        self.exec_cmd('from iss.idm import ImageDataManager')
        self.exec_cmd(f'{ref} = ImageDataManager(r"""{filepath}""")')
        
        gui.qapp.history.storepath(str(filepath), category='console')        
        
    def addText(self, text):
        self.stdio.stdOutputPanel.addText(text)
        
    def editSysPaths(self):                
        task = self.stdio.task
        result = task.call_func(Shell.get_sys_paths, args=(False,), wait=True)
        paths = result.copy()
        
        dialog_code = EditPaths(paths).exec_()
        
        result = task.call_func(Shell.set_sys_paths, args=(paths,))
        
    def editLivePaths(self):            
        task = self.stdio.task
    
        result = task.call_func(Shell.get_live_paths, wait=True)
        paths = result.copy()
        
        dialog_code = EditPaths(paths).exec_()               
        
        result = task.call_func(Shell.set_live_paths, args=(paths,))
                
    def toggleInputVisible(self):
        if self.stdio.stdInputPanel.isVisible():
            self.stdio.stdInputPanel.hide()
        else:
            self.stdio.stdInputPanel.show()
                
    def close_panel(self):                
        try:
           self.stdio.task.system_exit()
           
        finally:
            self.stdio.task.unregister()
            super().close_panel()
        
class MainThreadConsole(Console):
    panelShortName = 'main'
    userVisible = False
    
    def __init__(self, mainWindow, panid):
        shell = QApplication.instance().shell
        task = tasks.ThreadTask(shell, new_thread=False)
        super().__init__(mainWindow, panid, task)     
        task.start()
        self.stdio.stdInputPanel.styles['interprete'] = "background-color:#CBE9FF;" 
        self.stdio.stdInputPanel.set_mode('interprete')
        self.stdio.stdInputPanel.heightHint = 0
        self.stdio.stdInputPanel.setPlainText('# Reserved for debugging only')
        self.stdio.stdInputPanel.hide()
        self.executionMenu.setEnabled(False)
        
        getMenuAction(self.menuBar(), ['File', 'Close']).setEnabled(False)
        
    def close_panel(self):  
        pass
        
class SubThreadConsole(Console):
    panelShortName = 'thread'
    userVisible = True
    
    def __init__(self, mainWindow, panid):
        shell = QApplication.instance().shell
        task = tasks.ThreadTask(shell, new_thread=True)
        super().__init__(mainWindow, panid, task)
        task.start()


class ChildProcessConsole(Console):
    panelShortName = 'child'
    userVisible = True
    
    def __init__(self, mainWindow, panid, cqs=None):
        shell = QApplication.instance().shell
        task = tasks.ProcessTask(shell, cqs)
        super().__init__(mainWindow, panid, task)
        task.start()
        
    def duplicate(self, floating=False):
        newpanel = gui.qapp.panels.new_panel(ChildThreadConsole, None, None, floating=floating,
            kwargs={'parent_pid': self.task.process_id})
        return newpanel

        
class ChildThreadConsole(Console):
    panelShortName = 'child-thread'
    userVisible = True
    
    def __init__(self, mainWindow, panid, parent_pid=None):
        if parent_pid is None:
            pids = [str(pid) for pid in tasks.PROCESSES.keys()][1:]
            qtypes = ['zmq', 'pipe']
            form = [('Process Id', [1] + pids), ('Queue Type', [1] + qtypes)]
            (ind0, ind1) = fedit(form)        
            pid = int(pids[ind0-1])
            queue_type = qtypes[ind1-1]        
        else:
            pid = parent_pid
            queue_type = 'zmq'
        
        master = next(iter(tasks.PROCESSES[pid].values()))        
        shell = QApplication.instance().shell
        task = tasks.ProcessThreadTask(shell, master, queue_type)
        super().__init__(mainWindow, panid, task)  
        task.start()        

    def duplicate(self, floating=False):
        newpanel = gui.qapp.panels.new_panel(ChildThreadConsole, None, None, floating=floating,
            kwargs={'parent_pid': self.task.process_id})
        return newpanel        

