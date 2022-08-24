"""
Small utils directly related to QT
"""
import collections
from pathlib import Path
from qtpy import QtWidgets, QT6

from .. import config

respath = Path(config['respath'])

def relax_menu_text(text):
    """Remove any &, lower case, stop at first \\t"""
    tmp = text.replace('&', '').lower()
    tabind = tmp.find('\t')
    if tabind > 0:
        tmp = tmp[:tabind]
    return tmp.strip()

def relax_menu_trace(menutrace):
    """relax_menu_text on every string of menutrace"""
    return tuple(relax_menu_text(item) for item in menutrace)

def getMenuTrace(menu):
    """Return the current menu location as a list of strings"""
    menutrace = [menu.title().strip('&')]
    scan_action = menu.menuAction()
    
    while not scan_action is None:
        if QT6:
            aw = scan_action.associatedObjects()
        else:
            aw = scan_action.associatedWidgets()
            
        if len(aw) > 0 and isinstance(aw[0], QtWidgets.QMenu):
            menu = aw[0]
            menutrace.append(menu.title().strip('&'))
            scan_action = menu.menuAction()
        else:
            break

    return menutrace[::-1]

def getMenuAction(menubar, menutrace):
    """Locate the action in a menubar"""
    actions = menubar.actions()
    action = None

    menutrace = relax_menu_trace(menutrace)

    for check_action_name in menutrace:
        for action in actions:
            action_name = action.text()
            action_name = relax_menu_text(action_name)

            if action_name == check_action_name:
                menu = action.menu()
                if not menu is None:
                    #Cause showEvent which is sometimes used to refresh the menu content
                    menu.show()
                    actions = action.menu().actions()
                    menu.hide()
                else:
                    actions = []
                break

        else:
            raise KeyError(f'Action part "{check_action_name}" not found')

    return action
    
class ActionArguments(object):
    def __init__(self, qwidget):
        self.qwidget = qwidget
        self.args = collections.OrderedDict()
        
    def __setitem__(self, key, value):
        self.args[key] = value
        
    def __getitem__(self, key):
        return self.args[key]

    def isNotSet(self):
        return self.qwidget.sender().data() is None
        
    def __enter__(self):        
        return self
        
    def __exit__(self, *args, **kwargs):
        arguments = self.qwidget.sender().data() or {}
        self.args.update(dict(zip(self.args.keys(), arguments.get('args', []))))
        self.args.update(arguments.get('kwargs', {}))
