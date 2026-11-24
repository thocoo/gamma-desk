import sys
import pprint
import code
import threading


class RemoteInterpreter:
    """Base class for InteractiveConsole.

    This class deals with parsing and interpreter state (the user's
    namespace); it doesn't deal with input buffering or prompting or
    input file naming (the filename is always passed in explicitly).

    """

    def __init__(self, cqs):
        self.cqs = cqs
        self.resetbuffer()
        
        
    def raw_input(self, prompt=""):
        """Write a prompt and read a line.

        The returned line does not include the trailing newline.
        When the user enters the EOF key sequence, EOFError is raised.

        The base implementation uses the built-in function
        input(); a subclass may replace this with a different
        implementation.

        """
        return input(prompt)        
        

    def interact(self, banner=None, exitmsg=None):
        """Closely emulate the interactive Python console.

        The optional banner argument specifies the banner to print
        before the first interaction; by default it prints a banner
        similar to the one printed by the real Python interpreter,
        followed by the current class name in parentheses (so as not
        to confuse this with the real interpreter -- since it's so
        close!).

        The optional exitmsg argument specifies the exit message
        printed when exiting. Pass the empty string to suppress
        printing an exit message. If exitmsg is not given or None,
        a default message is printed.

        """
        try:
            sys.ps1
        except AttributeError:
            sys.ps1 = ">>> "
        try:
            sys.ps2
        except AttributeError:
            sys.ps2 = "... "            
        
        if banner is None:
            self.write("Remote Gamma Desk\n")
            
        elif banner:
            self.write("%s\n" % str(banner))
            
        t1 = threading.Thread(target=self.print_stdout)
        t1.start()
        
        t2 = threading.Thread(target=self.hartbeat)
        t2.start()
            
        more = 0
        while 1:
            try:
                if more:
                    prompt = sys.ps2
                else:
                    prompt = sys.ps1
                    
                try:
                    line = self.raw_input(prompt)
                    
                except EOFError:
                    self.write("\n")
                    break
                    
                else:
                    more = self.push(line)
                    
            except KeyboardInterrupt:
                self.write("\nKeyboardInterrupt\n")
                self.resetbuffer()
                more = 0
                
        if exitmsg is None:
            self.write('now exiting %s...\n' % self.__class__.__name__)
            
        elif exitmsg != '':
            self.write('%s\n' % exitmsg)


    def resetbuffer(self):
        """Reset the input buffer."""
        self.buffer = []
        
            
    def write(self, data):
        sys.stderr.write(data)
        
        
    def print_stdout(self):
        
        while True:
            mode, text = self.cqs.stdout_queue.get()
            sys.stdout.write(text)
            sys.stdout.flush()
                    
            
    def push(self, line):
        """Push a line to the interpreter.
        """
        
        self.buffer.append(line)
        source = "\n".join(self.buffer)
        more = self.runsource(source)
        if not more:
            self.resetbuffer()
        return more
        
        
    def hartbeat(self):
        while True:
            message = self.cqs.gui_call_queue.get()
            self.cqs.gui_return_queue.put(message)
        
        
    def runsource(self, source, filename="<input>", symbol="single"):
        """Compile and run some source in the interpreter.

        Arguments are as for compile_command().

        One of several things can happen:

        1) The input is incorrect; compile_command() raised an
        exception (SyntaxError or OverflowError).  A syntax traceback
        will be printed by calling the showsyntaxerror() method.

        2) The input is incomplete, and more input is required;
        compile_command() returned None.  Nothing happens.

        3) The input is complete; compile_command() returned a code
        object.  The code is executed by calling self.runcode() (which
        also handles run-time exceptions, except for SystemExit).

        The return value is True in case 2, False in the other cases (unless
        an exception is raised).  The return value can be used to
        decide whether to use sys.ps1 or sys.ps2 to prompt the next
        line.

        """
        self.cqs.stdin_queue.put(('interprete', (source,), None))
        callbackargs = self.cqs.return_queue.get()
        return False
        
        
class GDeskClient(object):
    
    def __init__(self):
        self.client = None
    
    def connect(self, port=None, host='localhost'):        
            
        if port == None:
            from gdesk.external.channel import get_cmd_server_ports
            ports = get_cmd_server_ports()            
            
            if len(ports) == 0:
                raise FileNotFoundError()
                
            else:
                port = ports[-1]
                
        from .watcher import CommandClient            
        self.client = CommandClient(port, host, keep_connected=True)


class TinyGui(GDeskClient):
    
    def show(self, *args, **kwargs):
        if self.client is None:
            print(*args)
        else:
            self.client.send({'cmd': 'open_array', 'args': args})  
            
        
class GuiClient(GDeskClient):
    
    def __init__(self, shell=None):
        self.shell = shell
        GDeskClient.__init__(self)
        
        
    def connect(self, port=None, host='localhost'):        
        from gdesk.core.tasks import ZmqQueues
        
        GDeskClient.connect(self, port, host)
            
        cqs_config = self.client.send({'cmd': 'connect_zmq_process',
            'args': ()}, timeout=5000, retries=1)
            
        pprint.pprint(cqs_config)
        
        cqs = ZmqQueues.from_json(cqs_config)
        cqs.setup_as_client(host)
        
        console_id = json.loads(cqs_config)['console_id']
        self.init_gui(self.shell, cqs, gui_redirect=True, client=False, console_id=console_id)            
                        
            
    def init_gui(self, shell, commqueues, gui_redirect=True, client=True, console_id=None):
        from gdesk import gui
        
        name, tid = shell.new_interactive_thread(commqueues, client=client, console_id=console_id)

        if gui_redirect:
            this_tid = threading.get_ident()
            gui.redirects[this_tid] = tid
            
            while not tid in sys.stdout.streams:
                time.sleep(0.1)

        return tid
        
        
class InteractiveClient(GDeskClient):
    
    def __init__(self):
        self.cqs = None
        GDeskClient.__init__(self)    
        
        
    def connect(self, port=None, host='localhost'):        
        from gdesk.core.tasks import ZmqQueues
        
        GDeskClient.connect(self, port, host)
            
        cqs_config = self.client.send({'cmd': 'init_zmq_queue',
            'args': ()}, timeout=5000, retries=1)
            
        pprint.pprint(cqs_config)
        
        self.cqs = ZmqQueues.from_json(cqs_config)
        self.cqs.setup_as_client(host)
        
        
    def interact(self):
        console = RemoteInterpreter(self.cqs)
        console.interact()
            
