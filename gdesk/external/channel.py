import os
import sys
import threading
import pathlib
import pprint
import json

from multiprocessing import Process, Queue

from .. import config, configure

configure(matplotlib={'backend':'svg'})

from .. import gui

from .. import console
from ..core.shellmod import Shell
from ..core.tasks import ZmqQueues
from ..core.tasks import CommQueues
from ..core.watcher import CommandClient


def python_executable():
    executable = pathlib.Path(sys.executable)
    if executable.name == 'python.exe':
        #This is also correct for virtual env
        #Note that the os module is loaded from the master Python location
        #not the virtual env
        return str(executable)
    else:
        #In case of embeded python in on other executable (Canvas)
        #Base the python.exe location on the os module location
        executable = pathlib.Path(os.__file__).parent.parent / 'python.exe'
        return str(executable)


def connect_to_gui(port=None, host='localhost',
        namespace=None, gui_redirect=True, as_server=False):
    """
    Start Gamma Desk as a independend process and open a zmq communication channel
    This function start a new thread.

    :param int port: TCP port number to connect to (default 5998)
    :param str host: Hostname of ip address to connect to (default localhost)
    :param dict namespace: The namespace to use in the Gamma Desk console
        (Caller namespace by default)
    :param bool gui_redirect: Make the gui mapper accesible in this thread
    :param bool as_server: True -> This will be the zmq server
        (default False -> GD acts as server)

    Typical usage in a second Python process by the following command:

    >>>  from gdesk.external import channel
    >>>  channel.connect_to_gui()

    Connecting to a running GD instance at another computer

    >>>  channel.connect_to_gui(5998, 'mylaptop.ad.example.com')

    """
    if namespace is None:
        namespace = sys._getframe(1).f_globals

    shell = Shell(namespace)
    
    import gdesk
    gdesk.refer_shell_instance(shell)

    if host not in ['localhost', '127.0.0.1']:
        config['image']['queue_array_shared_mem'] = False

    if port is None:
        ports = shell.get_watcher_ports()
        port = ports[-1]

    cmdclient = CommandClient(port, host)

    if as_server:
        print('Connecting as server')
        cqs = ZmqQueues()
        cqs.setup_as_server()
        cqs_config = cmdclient.send({'cmd': 'connect_zmq_process',
            'args': (cqs.to_json(),)}, timeout=5000, retries=1)
        pprint.pprint(cqs_config)

    else:
        print('Connecting as client')
        cqs_config = cmdclient.send({'cmd': 'connect_zmq_process',
            'args': ()}, timeout=5000, retries=1)
        pprint.pprint(cqs_config)
        cqs = ZmqQueues.from_json(cqs_config)
        cqs.setup_as_client(host)
        
    console_id = json.loads(cqs_config)['console_id']

    return init_gui(shell, cqs, gui_redirect, client=False, console_id=console_id)


def start_gui_as_child(namespace=None, gui_redirect=True):
    """
    Start Gamma Desk as a child process and open a communication channel
    to a new thread in this process.

    :param dict workspace: The workspace to use in the Shell object
    :param bool gui_redirect: make the gui mapper accesible in this thread

    Typical usage in Canvas by the following command:

        from gdesk.external.channel import start_gui_as_child; start_gui_as_child(globals())
    """
    if namespace is None:
        namespace = sys._getframe(1).f_globals

    shell = Shell(namespace)

    #CommQueues can only be send to other process by
    #spawn process inheritance
    cqs = CommQueues(Queue, process=True)

    start_gui(child=True, commqueues=cqs)
       
    return init_gui(shell, cqs, gui_redirect)


def start_gui(child=False, commqueues=None, deamon=False):
    if child:
        #Start the Gui as a subprocess using the multiprocessing module
        #hack the executable in sys (for embeded Python)
        sys.executable = python_executable()
        proc_config = {
            'default_perspective': 'base',
            'init_command': {'cmd': 'connect_process', 'args': ()}}

        process = Process(target=console.run_as_child,
            args=((), proc_config, {'cqs': commqueues}), daemon=deamon)
        process.start()

    else:
        os.system(f'start {python_executable()} -m ghawk2')


def init_gui(shell, commqueues, gui_redirect=True, client=True, console_id=None):
    name, tid = shell.new_interactive_thread(commqueues, client=client, console_id=console_id)

    if gui_redirect:
        gui.redirects[threading.get_ident()] = tid

    return tid
