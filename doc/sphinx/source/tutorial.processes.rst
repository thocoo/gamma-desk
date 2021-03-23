Processes
=========

Introduction
------------

Gamma Desk (GD) can connect to other Python threads and processes.
This process can be started by GD as a child processes or can be an already running Python process.
The process can also run on another computer.

Gamma Desk as process and thread starter
----------------------------------------

Main Thread in the GUI process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The main thread of Gamma Desk is also the QT eventloop.
This eventloop process all gui events, the the gui will end if this eventloop is exitted.

The main thread of the GUI process is always in console#0.
By default, the panel and input console ishidden.

:: 
    
    Panels Dialog > Panel > console#0    
    
You can make the input visible by the menu.    

Note that while commands are executed from this console, the GUI will freeze.
For example, if you execute the following command on console#0, the gui will freeze for 10 seconds:

>>> import time; time.sleep(10)

Window will even mark Gamma Desk as '(Not Responding)', because you are freezing the eventloop for a few seconds.

This console is typicaly not used be the user, but it is very usefull to debug the GUI.
The QApplication is available by gui.qapp.

Note that you should create QT objects only in this thread.
Qt garbage should also only be collected in this thread.
The default Python garbage collector will collect garbage in any current running thread.
For this reason, Gamma Desk disiabled this default Python garbage collecter timer and has its own implementation of a timer to always start the garbage
collection in the main gui thread.

Sub Threads in the GUI process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These threads runs in the same process as the GUI thread.
The workspace is the same for every thread in the same process.

:: 
    
    Panels Dialog > New > Console > thread

There is a shell and gui api available for showing images, making plots,
calling simple dialogs.

The shell object is common for all threads in the same process.

The gui object is a proxy to a thread dependend gui instance.
If you access a attribute on the gui proxy, Gamma Desk will first check from
which thread you doing the call and then access the attribute from the
thread dependend instance. It is possible that the caller thread has
no gui instance. In this case, there are not attributes on the gui proxy.

gui.qapp will also be None if called from anywhere except console#0.
This is done to protect the user of accessing QT directly.
The user should not access QT (or for sure not create any Qt object) outside the gui thread.


Main Thread in a Child Process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    Panels Dialog > New > Console > child

This thread has a new namespace.

The GUI API is still available. But note that all arguments and returned values
are piped between this child process and the GUI process.
This means that all arguments and returns should be pickable.

An exception are image arrays. These are placed on shared memory so the GUI can show them.

Sub Thread in a Child Process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Panels Dialog > New > Console > child-thread

The workspace is the same as the main thread of the same process.
The behavior is the same as the main thread.

Connection to an already running Python Process
-----------------------------------------------

When Gamma Desk has no current console on an other process,
it still can receive commands from another process.
A command server will listen to a certain tcp port.
Every new instance of GD will bind a different port.


Connection on the same computer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the following command in the already running Python Process
The user doesn't have to give the port number because code
can find it in the current active logdir of GD.

.. code-block:: python

    from gDesk2.external import channel
    channel.connect_to_gui()
   
Connection from another computer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~   

For example, a Gamma Desk is running on  host 'FFYBVR-L1.ad.onsemi.com'.
An the watcher is active on port 5559.

The user have to give the port number and the host when he wants to connect to GD.

.. code-block:: python

    from gdesk.external import channel
    channel.connect_to_gui(5559, 'FFYBVR-L1.ad.onsemi.com')


Gamma Desk as child of a Python process
---------------------------------------

The following command will start a new Gamma Desk process as a child process

.. code-block:: python

    from gDesk2.external.channel import start_gui_as_child
    start_gui_as_child()
    
As soon the python process exit, GD will also exit.
    