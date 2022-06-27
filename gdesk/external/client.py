from ..core.watcher import CommandClient

def send_array_to_gui(array, port=None, host='localhost'):
    import numpy as np
    
    cmdclient = CommandClient(port, host)
    cmdclient.send({'cmd': 'open_array', 'args': (array,)}, timeout=5000, retries=1)