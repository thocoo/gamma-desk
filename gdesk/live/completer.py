"""Word completion for GNU readline.

The completer completes keywords, built-ins and globals in a selectable
namespace (which defaults to __main__); when completing NAME.NAME..., it
evaluates (!) the expression up to the last dot and completes its attributes.

It's very cool to do "import sys" type "sys.", hit the completion key (twice),
and see the list of names defined by the sys module!

Tip: to use the tab key as the completion key, call

    readline.parse_and_bind("tab: complete")

Notes:

- Exceptions raised by the completer function are *ignored* (and generally cause
  the completion to fail).  This is a feature -- since readline sets the tty
  device in raw (or cbreak) mode, printing a traceback wouldn't work well
  without some complicated hoopla to save, reset and restore the tty state.

- The evaluation of the NAME.NAME... form may cause arbitrary application
  defined code to be executed if an object with a __getattr__ hook is found.
  Since it is the responsibility of the application (or the user) to enable this
  feature, I consider this an acceptable risk.  More complicated expressions
  (e.g. function calls or indexing operations) are *not* evaluated.

- When the original stdin is not a tty device, GNU readline is never
  used, and this module (and the readline module) are silently inactive.

"""

import atexit
import builtins
import __main__
from .manage import LiveScriptScan, LiveScriptTree

__all__ = ["Completer"]

def get_dict_attr(obj, attr):
    # getting attribute without calling property getter
    if isinstance(obj, type):
        raise AttributeError
    objs = [obj] + obj.__class__.mro()
    
    for obj in objs:
        if attr in obj.__dict__:
            return obj.__dict__[attr]
    raise AttributeError
    
def is_property(obj, attr):
    try:
        class_attr = getattr(type(obj), attr)
        if isinstance(class_attr, property):
            return True
    except:
        return False   
    return False
    
def is_matched(expression, opening='({[', closing=')}]'):
    """
    Finds out how balanced an expression is.
    With a string containing only brackets.

    >>> is_matched('[]()()(((([])))')
    False
    >>> is_matched('[](){{{[]}}}')
    True
    """
    opening = tuple(opening)
    closing = tuple(closing)
    mapping = dict(zip(opening, closing))
    queue = []

    for letter in expression:
        if letter in opening:
            queue.append(mapping[letter])
        elif letter in closing:
            if not queue or letter != queue.pop():
                return False
    return not queue    

class Completer:
    def __init__(self, namespace = None):
        """Create a new completer for the command line.

        Completer([namespace]) -> completer instance.

        If unspecified, the default namespace where completions are performed
        is __main__ (technically, __main__.__dict__). Namespaces should be
        given as dictionaries.

        Completer instances should be used as the completion mechanism of
        readline via the set_completer() call:

        readline.set_completer(Completer(my_namespace).complete)
        """

        if namespace and not isinstance(namespace, dict):
            raise TypeError('namespace must be a dictionary')

        # Don't bind to namespace quite yet, but flag whether the user wants a
        # specific namespace or to use __main__.__dict__. This will allow us
        # to bind to __main__.__dict__ at completion time, not now.
        if namespace is None:
            self.use_main_ns = 1
        else:
            self.use_main_ns = 0
            self.namespace = namespace

    def complete(self, text, state, wild=False):
        """Return the next possible completion for 'text'.

        This is called successively with state == 0, 1, 2, ... until it
        returns None.  The completion should begin with 'text'.

        """        
        if self.use_main_ns:
            self.namespace = __main__.__dict__

        if not text.strip():
            if state == 0:
                if _readline_available:                            
                    try:
                        readline.insert_text('\t')
                        readline.redisplay()
                    except:
                        return '\t'
                    return ''
                else:
                    return '\t'
            else:
                return None

        if state == 0:
            self.wild = wild
            if not is_matched(text, '[', ']'):
                self.matches = self.key_matches(text)        
            elif "." in text:
                self.matches = self.attr_matches(text)                
            else:
                self.matches = self.global_matches(text)
        try:
            return self.matches[state]
        except IndexError:
            return None

    def _callable_postfix(self, val, word):
        if callable(val):
            word = word + "("
        return word

    def global_matches(self, text):
        """Compute matches when text is a simple name.

        Return a list of all keywords, built-in functions and names currently
        defined in self.namespace that match.

        """
        import keyword
        matches = []
        seen = {"__builtins__"}
        n = len(text)
        for word in keyword.kwlist:
            if self.wild:
                test = text.lower() in word.lower()
            else:
                test = word[:n] == text
            if test:
                seen.add(word)
                if word in {'finally', 'try'}:
                    word = word + ':'
                elif word not in {'False', 'None', 'True',
                                  'break', 'continue', 'pass',
                                  'else'}:
                    word = word + ' '
                matches.append(word)
        for nspace in [self.namespace, builtins.__dict__]:
            for word, val in nspace.items():
                if self.wild:
                    test = text.lower() in word.lower() and word not in seen
                else:
                    test = word[:n] == text and word not in seen
                if test:
                    seen.add(word)
                    matches.append(self._callable_postfix(val, word))
        return matches

    def attr_matches(self, text):
        """Compute matches when text contains a dot.

        Assuming the text is of the form NAME.NAME....[NAME], and is
        evaluable in self.namespace, it will be evaluated and its attributes
        (as revealed by dir()) are used as possible completions.

        For class instances, class members are also considered except if the instance
        contains a flag `_AUTO_COMPLETE_HIDE_CLASS_ATTRIBUTES` set to True.

        WARNING: this can still invoke arbitrary C code, if an object
        with a __getattr__ hook is evaluated.
        """
        import re
        #m = re.match(r"(\w+(\.\w+)*)\.(\w*)", text)
        m = re.match(r"""([\w\[\]'"]+(\.[\w\[\]'"]+)*)\.(\w*)""", text)
        if not m:
            return []
        expr, attr = m.group(1, 3)
        try:
            thisobject = eval(expr, self.namespace)
        except Exception:
            return []

        # get the content of the object, except __builtins__
        words = set(dir(thisobject))
        words.discard("__builtins__")

        # Get the class-level attributes, but only if these are not explicitly hidden.
        hide_class_level_attributes = getattr(thisobject, "_AUTO_COMPLETE_HIDE_CLASS_ATTRIBUTES", False)
        if hasattr(thisobject, '__class__'):
            words.add('__class__')
            if not hide_class_level_attributes:
                words.update(get_class_members(thisobject.__class__))
        matches = []
        n = len(attr)
        if attr == '':
            noprefix = '_'
        elif attr == '_':
            noprefix = '__'
        else:
            noprefix = None
        while True:
            for word in words:
                if self.wild and attr.lower() in word.lower():
                    match = "%s.%s" % (expr, word)
                    matches.append(match)                    
                elif (word[:n] == attr and
                    not (noprefix and word[:n+1] == noprefix)):
                    match = "%s.%s" % (expr, word)
                    if is_property(thisobject, word):
                        #Don't do getattr on the property
                        #It would call the getter, which can start executing code
                        #Which can be anyoing
                        pass
                    elif isinstance(thisobject, (LiveScriptScan, LiveScriptTree)):
                        pass
                    else:
                        try:
                            val = getattr(thisobject, word)
                        except Exception:
                            pass  # Include even if attribute not set
                        else:
                            match = self._callable_postfix(val, match)
                    matches.append(match)
            if matches or not noprefix:
                break
            if noprefix == '_':
                noprefix = '__'
            else:
                noprefix = None
        matches.sort()
        return matches
        
    def key_matches(self, text):
        """Compute matches when text contains a [.
        """        
        import re
        m = re.match(r"""(\w+(\.\w+)*)\[([\"\'\\/\w]*)""", text)
        
        if not m:
            return []
            
        expr, attr = m.group(1, 3)
        if attr.startswith('"'):
            delim = '"'
            attr = attr[1:]
        elif  attr.startswith("'"):
            delim = "'"
            attr = attr[1:]
        else:
            delim = "'"                    
        
        try:
            thisobject = eval(expr, self.namespace)
        except Exception:
            return []

        # get the content of the object, except __builtins__
        try:
            keys = list(thisobject.keys())
        except:
            keys = []
            
        if sum([isinstance(key, str) for key in keys]) == len(keys):            
            #It are all strings
            n = len(attr)
            matches =  [f"{expr}[{delim}{key}" for key in keys if key[:n] == attr]
        else:
            attr = str(attr)
            n = len(attr)
            matches =  [f"{expr}[{key}" for key in keys if str(key)[:n] == attr]

        return matches        

def get_class_members(klass):
    ret = dir(klass)
    if hasattr(klass,'__bases__'):
        for base in klass.__bases__:
            ret = ret + get_class_members(base)
    return ret

try:
    import readline
except ImportError:
    _readline_available = False
else:
    readline.set_completer(Completer().complete)
    # Release references early at shutdown (the readline module's
    # contents are quasi-immortal, and the completer function holds a
    # reference to globals).
    atexit.register(lambda: readline.set_completer(None))
    _readline_available = True
