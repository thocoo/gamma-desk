from ..core.watcher import CommandClient

def send_array_to_gui(array, port=None, host='localhost', new=False):    
    cmdclient = CommandClient(port, host)
    cmdclient.send({'cmd': 'open_array', 'args': (array, new)}, timeout=5000, retries=1)