import os
import queue
import threading
import collections
import socket
import json
import multiprocessing
import _multiprocessing

try:
    from multiprocessing.connection import PipeConnection
    from multiprocessing.reduction import duplicate, steal_handle

except:
    #Not on Linux
    pass

try:
    import zmq
    zmq_context = zmq.Context()

except:
    pass

from .conf import config

sentinel = object()

class CommQueues(object):
    def __init__(self, QueueCls, process=False):
        self.host = 'localhost'
        self.cmd_queue = QueueCls()
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
        while not self.cmd_queue.empty():
            self.cmd_queue.get()

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
        for q in [self.cmd_queue, self.stdout_queue, self.return_queue,
                  self.gui_call_queue, self.gui_return_queue]:
            if isinstance(q, DuplexQueue) or isinstance(q, NonDuplexQueue):
                q.close()

class NonDuplexQueue(object):
    #My alternative for multiprocessing Queues
    #The original multiprocessing.Queues with locks can only be
    #initialized to a process by inheritance
    #The shared locks are the problem

    def __init__(self):
        self.reader, self.writer = multiprocessing.Pipe(duplex=False)

        self._buffer = collections.deque()
        self._thread = None

    def steal_pipe(self, pid, read_handle, write_handle):
        read_handle = steal_handle(pid, read_handle)
        write_handle = steal_handle(pid, write_handle)

        reader = PipeConnection(read_handle, writable=False)
        writer = PipeConnection(write_handle, readable=False)
        return reader, writer

    def duplicate_pipe(self):
        read_handle = duplicate(self.reader._handle)
        write_handle = duplicate(self.writer._handle)
        return read_handle, write_handle

    def __getstate__(self):
        state = dict()
        state['pid'] = os.getpid()
        read_handle, write_handle = self.duplicate_pipe()
        state['read_handle'] = read_handle
        state['write_handle'] = write_handle
        return state

    def __setstate__(self, state):
        self.reader, self.writer = self.steal_pipe(state['pid'],
            state['read_handle'], state['write_handle'])
        self._buffer = collections.deque()
        self._thread = None

    def empty(self):
        return not self.reader.poll()

    def put(self, data):
        # The _notempty lock can not be pickled and shared
        # between processes (only by inheritance)!
        # So this function should be called after the this queue
        # has been setup between the 2 processes

        if self._thread is None:
            self._notempty = threading.Condition(threading.Lock())
            self._thread = threading.Thread(target=self._feed,
                name='NonDuplexQueueFeed' ,daemon=True)
            self._thread.start()

        with self._notempty:
            self._buffer.append(data)
            self._notempty.notify()

    def get(self, timeout=None):
        if self.reader.poll(timeout):
            return self.reader.recv()
        else:
            raise RuntimeError('Queue is empty')

    def _feed(self):
        while True:
            with self._notempty:
                self._notempty.wait()

            try:
                while True:
                    data = self._buffer.popleft()
                    if data is sentinel:
                        return
                    self.writer.send(data)

            except IndexError:
                pass

    def close(self):
        self.put(sentinel)

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

        d1['cmd'] = self.cmd_queue.port
        d1['stdin'] = self.stdin_queue.port
        d1['stdout'] = self.stdout_queue.port
        d1['return'] = self.return_queue.port
        d1['gui_call'] = self.gui_call_queue.port
        d1['gui_return'] = self.gui_return_queue.port
        return json.dumps(d0)

    def setup_as_server(self):
        self.setup_host()
        self.cmd_queue.setup_as_server()
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

        self.cmd_queue.setup_as_client(self.host)
        self.stdin_queue.setup_as_client(self.host)
        self.stdout_queue.setup_as_client(self.host)
        self.return_queue.setup_as_client(self.host)
        self.gui_call_queue.setup_as_client(self.host)
        self.gui_return_queue.setup_as_client(self.host)
