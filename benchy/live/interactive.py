import sys
import platform
import code
from pathlib import Path

def interact(workspace=None, banner=None, exitmsg=None, completer='standard'):    
    if workspace is None:
        frame = sys._getframe(1)
        globs = frame.f_globals
        locs = frame.f_locals
        workspace = globs
        workspace.update(locs) 

    try:
        import readline
        if completer=='standard':
            from rlcompleter import Completer
            readline.set_completer(Completer(workspace).complete)          
        elif completer=='key':
            from .completer import Completer
            readline.set_completer_delims(' \t\n\\`@$><=;|&{(')
            readline.set_completer(Completer(workspace).complete)
        else:
            raise AttributeError(f'Invalid completer {completer}')
                          
        readline.parse_and_bind('tab:complete')
    except:
        print('Could not start auto complete!')
                                            
    shell = code.InteractiveConsole(workspace)
    shell.interact(banner=banner, exitmsg=exitmsg)          