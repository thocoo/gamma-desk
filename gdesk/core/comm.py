import os
import sys
import queue
import threading
import collections
import socket
import json
import multiprocessing
import _multiprocessing

import zmq
zmq_context = zmq.Context()

from .conf import config

if sys.platform == 'win32':
    from .comm_nonduplex import NonDuplexQueue   

sentinel = object()

class CommQueues(object):
    def __init__(self, QueueCls, process=False):
        self.host = 'localhost'
        self.flow_queue = QueueCls()
        self.return_queue = QueueCls()

        self.stdin_queue = QueueCls()
        self.stdout_queue = QueueCls()

        if process:
            self.gui_call_queue = QueueCls()
            self.gui_return_queue = QueueCls()
        else:
            self.gui_call_queue = None
            self.gui_return_queue = None

    def clear(self):
        while not self.flow_queue.empty():
            self.flow_queue.get()

        while not self.stdout_queue.empty():
            self.stdout_queue.get()

        while not self.return_queue.empty():
            self.return_queue.get()

        if not self.gui_call_queue is None:
            while not self.gui_call_queue.empty():
                self.gui_call_queue.get()

        if not self.gui_return_queue is None:
            while not self.gui_return_queue.empty():
                self.gui_return_queue.get()

    def close(self):
        for q in [self.flow_queue, self.stdout_queue, self.return_queue,
                  self.gui_call_queue, self.gui_return_queue]:
            if isinstance(q, NonDuplexQueue):
                q.close()


class ZmqQueue(object):

    def __init__(self, port=None):
        self.port = port

    def setup_as_server(self):
        self.socket = zmq_context.socket(zmq.PAIR)
        self.port = self.socket.bind_to_random_port('tcp://*',
            min_port=config['zmq_queue_min_port'],
            max_port=config['zmq_queue_max_port'],
            max_tries=100)

    def setup_as_client(self, host='localhost'):
        self.socket = zmq_context.socket(zmq.PAIR)
        self.socket.connect(f"tcp://{host}:{self.port}")

    def __getstate__(self):
        state = dict()
        state['port'] = self.port
        return state

    def __setstate__(self, state):
        self.port = state['port']

    def put(self, data):
        self.socket.send_pyobj(data, flags=zmq.NOBLOCK)

    def get(self, timeout=None):
        if not timeout is None:
            event = self.socket.poll(timeout*1000)
            if event == 0:
                raise queue.Empty()
        return self.socket.recv_pyobj()

    def empty(self):
        return self.socket.poll(0) == 0


class ZmqQueues(object):
    ports = {
        'cmd': None,
        'stdin': None,
        'stdout': None,
        'return': None,
        'gui_call': None,
        'gui_return': None,
        }

    def __init__(self, ports=None):
        if ports is None:
            ports = ZmqQueues.ports

        for queue_name, port in ports.items():
            self.__dict__[f'{queue_name}_queue'] = ZmqQueue(port=port)

    def setup_host(self):
        self.hostname = socket.gethostname()
        hostname_ex, aliaslist, ipaddrlist = socket.gethostbyname_ex(self.hostname)
        self.hostname_ex = hostname_ex
        self.aliaslist = aliaslist
        self.ipaddrlist = ipaddrlist

    @classmethod
    def from_json(Cls, json_string):
        d0 = json.loads(json_string)
        d1 = d0['channel']

        ports = dict()
        ports['cmd'] = d1['cmd']
        ports['stdin'] = d1['stdin']
        ports['stdout'] = d1['stdout']
        ports['return'] = d1['return']
        ports['gui_call'] = d1['gui_call']
        ports['gui_return'] = d1['gui_return']

        instance = Cls(ports)

        instance.hostname = d1['hostname']
        instance.hostname_ex = d1['hostname_ex']
        instance.aliaslist = d1['aliaslist']
        instance.ipaddrlist = d1['ipaddrlist']

        return instance

    def to_json(self):
        d0 = dict()
        d1 = d0['channel'] = dict()
        d1['method'] = 'zmq'

        d1['hostname'] = self.hostname
        d1['hostname_ex'] = self.hostname_ex
        d1['aliaslist'] = self.aliaslist
        d1['ipaddrlist'] = self.ipaddrlist

        d1['cmd'] = self.flow_queue.port
        d1['stdin'] = self.stdin_queue.port
        d1['stdout'] = self.stdout_queue.port
        d1['return'] = self.return_queue.port
        d1['gui_call'] = self.gui_call_queue.port
        d1['gui_return'] = self.gui_return_queue.port
        return json.dumps(d0)

    def setup_as_server(self):
        self.setup_host()
        self.flow_queue.setup_as_server()
        self.stdin_queue.setup_as_server()
        self.stdout_queue.setup_as_server()
        self.return_queue.setup_as_server()
        self.gui_call_queue.setup_as_server()
        self.gui_return_queue.setup_as_server()

    def setup_as_client(self, host=None):
        if host is None:
            self.host = 'localhost'
        else:
            self.host = host

        self.flow_queue.setup_as_client(self.host)
        self.stdin_queue.setup_as_client(self.host)
        self.stdout_queue.setup_as_client(self.host)
        self.return_queue.setup_as_client(self.host)
        self.gui_call_queue.setup_as_client(self.host)
        self.gui_return_queue.setup_as_client(self.host)
