from .. import config, gui

if config.get('qapp', False):
    from .base import BasePanel, CheckMenu, thisPanel, selectThisPanel
    from .. import dialogs
    from ..dialogs.formlayout import fedit
    from ..dialogs.base import messageBox   
    from ..dialogs.editpaths import EditPaths
    MainPanel = BasePanel

from ..core import tasks
from ..core.shellmod import Shell

from ..utils.syntax_light import analyze_python, ansi_highlight
from ..utils.ansi_code_processor import QtAnsiCodeProcessor