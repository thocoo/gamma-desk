import logging
import time
import sys, os
import threading
import queue
import socket
import json

import zmq

from . import conf
from .conf import config
from .gui_proxy import gui

logger = logging.getLogger(__name__)
context = zmq.Context()

class CommandServer(object):

    def __init__(self, shell):
        self.shell = shell
        self.server_thread = None
        self.socket_loop = False
        self.queue_loop = False
        self.cmd_queue = queue.Queue()

    def start(self, qapp):
        self.socket = context.socket(zmq.REP)

        min_port = config.get('zmq_watcher_min_port', 5550) 
        max_port = config.get('zmq_watcher_max_port', 5560)                
        
        try:
            self.port = self.socket.bind_to_random_port('tcp://*',
                min_port=min_port, max_port=max_port, max_tries=100)        
            logger.info(self.host_info())
            
        except zmq.error.ZMQError as err:
            if err.strerror == 'Address in use':
                self.socket.close()
                logger.info(f'Watcher port {self.port} is already in use')
                return False
            else:
                raise        
                
        with open(self.shell.logdir.logpath / 'cmdserver.json', 'w') as fp:
            info = {'port': self.port}
            json.dump(info, fp)
        
        self.socket_loop = True
        self.server_thread = threading.Thread(target=self.recv_socket_socket_loop, args=(qapp.handover,))
        self.server_thread.setDaemon(True)
        self.server_thread.start()
        return True
        
    def host_info(self):
        hostname_ex, aliaslist, ipaddrlist = socket.gethostbyname_ex(socket.gethostname())
        message = []
        message.append(f'Watcher port : {self.port}')
        message.append(f'Hostname     : {hostname_ex}')
        message.append(f'Aliases      : {aliaslist}')
        message.append(f'IP addresses : {ipaddrlist}')
        return '\n'.join(message)
        
    def start_queue_loop(self, qapp):        
        self.queue_loop = True
        self.cmd_queue_thread = threading.Thread(target=self.recv_queue_socket_loop, args=(qapp.handover,))
        self.cmd_queue_thread.setDaemon(True)
        self.cmd_queue_thread.start()        
        
    def stop(self):
        self.socket_loop = False
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(f"tcp://localhost:{self.port}")
        self.socket.send_pyobj('close')
        self.socket.close()
        
    @staticmethod
    def open_images(*image_paths):
        for image_path in image_paths:
            gui.img.open(image_path, new=True)
            
    @staticmethod        
    def connect_process(cqs_config=None):
        from .tasks import ZmqQueues
        print(f'cqs_config:{cqs_config}')
        
        if cqs_config is None:        
            cqs = conf.config_objects['cqs']
        else:
            cqs = ZmqQueues.from_json(cqs_config)
            cqs.setup_as_client()
            
        gui.qapp.panels['console'][0].get_container().window().hide()
        gui.qapp.panels.select_or_new('console', None, 'child', kwargs={'cqs': cqs})
        
        return cqs_config
        
    @staticmethod        
    def connect_zmq_process(cqs_config=None):
        from .tasks import ZmqQueues       
        
        if cqs_config is None:       
            cqs = ZmqQueues()
            cqs.setup_as_server()
        else:
            cqs = ZmqQueues.from_json(cqs_config)
            cqs.setup_as_client(cqs.hostname_ex)
            
        gui.qapp.panels['console'][0].get_container().window().hide()
        gui.qapp.panels.select_or_new('console', None, 'child', kwargs={'cqs': cqs})
        
        return cqs.to_json()        
        
    @staticmethod        
    def execute_file(init_file, console_id):                
        gui.console.execute_file(init_file, console_id)     

    @staticmethod        
    def execute_code(init_code, console_id):        
        from .. import gui
        gui.console.execute_code(init_code, console_id)          

    @staticmethod
    def start_kernel(kerneltype='ipykernel', connectfile='', rundir=None, child=True, threaded=False):
        from .. import gui
        from ..external import jupyter
        
        if child:
            gui.console.child(jupyter.start_kernel, kerneltype, connectfile, rundir, threaded)
        else:
            pass
                      
    def recv_socket_socket_loop(self, handover):
        while self.socket_loop:
            request = self.socket.recv_pyobj()
            
            if request == 'close':
                break
                
            else:
                cmd, args = request['cmd'], request['args']
                        
            answer = self.execute_command(handover, cmd, args)
            self.socket.send_pyobj(answer or request)

        self.socket.close()
        logger.info(f'Watcher stoppped')
        
    def recv_queue_socket_loop(self, handover):
        while self.queue_loop:
            request = self.cmd_queue.get()
            
            if request == 'close':
                break
                
            else:
                cmd, args = request['cmd'], request['args']
                
            answer = self.execute_command(handover, cmd, args)                              
                        
        
    def execute_command(self, handover, cmd, args):
        if cmd is None:
            return
            
        elif cmd == 'open_images':            
            return handover.send(True, CommandServer.open_images, *args)
            
        elif cmd == 'start_kernel':
            return handover.send(True, CommandServer.start_kernel, *args)
            
        elif cmd == 'connect_process':
            return handover.send(True, CommandServer.connect_process, *args)
            
        elif cmd == 'connect_zmq_process':
            return handover.send(True, CommandServer.connect_zmq_process, *args)            
            
        elif cmd == 'execute_file':
            return handover.send(True, CommandServer.execute_file, *args)
            
        elif cmd == 'execute_code':
            return handover.send(True, CommandServer.execute_code, *args)            
        
class CommandClient(object):

    def __init__(self, port=None, host='localhost'):
        self.timeout = 10000
        self.retries = 1
        self.port = port or config.get('watcher_port', 5998)
        self.host = host       
    
    def send(self, message, timeout=None, retries=None):
        timeout = timeout or self.timeout
        retries_left = retries or self.retries
        server_endpoint = f"tcp://{self.host}:{self.port}"
        logging.info(f"Connecting to server {server_endpoint}...")
        
        self.socket = context.socket(zmq.REQ)
        
        try:
            self.socket.connect(server_endpoint)
        except:
            raise

        request = message
        logging.debug(f"Sending {request}")
        self.socket.send_pyobj(request)
        
        while True:
            if (self.socket.poll(timeout) & zmq.POLLIN) != 0:
                reply = self.socket.recv_pyobj()
                return reply

            retries_left -= 1
            logging.warning("No response from server")
            # Socket is confused. Close and remove it.
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.close()
            if retries_left == 0:
                logging.error("Server seems to be offline, abandoning")
                break

            logging.info("Reconnecting to server...")
            # Create new connection
            self.socket = context.socket(zmq.REQ)
            self.socket.connect(server_endpoint)
            logging.info("Resending (%s)", request)
            self.socket.send_pyobj(request)

        self.socket.close()