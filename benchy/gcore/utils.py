"""
Small utils directly related to QT
"""
from pathlib import Path
from qtpy import QtWidgets

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
