from ... import config

if config.get('qapp', False):
    from .consolepanel import MainThreadConsole, SubThreadConsole, ChildProcessConsole, ChildThreadConsole

from .consoleproxy import ConsoleGuiProxy