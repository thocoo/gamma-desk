# My alternative for multiprocessing Queues
# The original multiprocessing.Queues with locks can only be
# initialized to a process by inheritance
# The shared locks are the problem
# Because there are no locks, to be save
# only a single writer and reader can use this queue

import os
import threading
import collections
import multiprocessing
import _multiprocessing

from multiprocessing.connection import PipeConnection
from multiprocessing.reduction import duplicate, steal_handle
    

class NonDuplexQueue(object):

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