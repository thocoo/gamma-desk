Live Scripting
==============

Custom functions can be programmed in an external Python file (.py extension) using the scripting system.
These functions can be called from the shell.
The code is reloaded to Gamma Desk automatically when saved and a function is called from the shell.

Place the following content in a Python file.

.. code-block:: python

    def main():
        print("Hello world")

Save for example the file as C:\\temp\\livescripts\\hello.py

Check then if C:\\temp\\livescripts is in the Live Scripting search path.
Take the menu of a console panel, and go to Script->Edit Live paths...

Then, the following should print Hello World.


.. code-block:: python

    use.hello.main()

::

    Hello world


If you edit the hello.py, save and recall it, it should call the updated function.


.. code-block:: python

    def main():
        print("Hello, new world")


.. code-block:: python

    use.hello.main()

::

    Hello, new world
    
    
Refer across scripts
--------------------

.. code-block:: python

    from gdesk import using

    other = using.other

    def func1():
        other.func2()
        
    def main():
        func1()
