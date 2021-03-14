
"""
Provide OrderedStruct and DictStruct classes.

Also, provide two utility functions: current_code_path() and force2bytes().
"""

import os, sys
import collections
from pathlib import Path

def current_code_path():
    """
    Return the path of the caller's source code file.

    If the caller is the shell (interactive scripting), None is returned.

    :return: Path object or None.

    Example:
        # works only when used from a .py file, not when used
        # in a shell (on standard input):
        from iskutil.names import current_code_path
        folder = current_code_path().parent

        # in a shell this is what happens:
        current_code_path() is None
        >>> True
    """

    # ensure that pathlib is available
    if Path is None:
        raise ImportError("Could not import pathlib; you need to use Python version v >= 3.4 or install a discrete pathlib module (e.g. pathlib2)")

    frame = sys._getframe(1)
    code_path = Path(frame.f_code.co_filename)

    if code_path.name == '<input>':
        # this code did not come from a .py file, but from standard
        # input; we don't have a valid Path to that
        return None

    return code_path.resolve()


class OrderedStruct:

    """
    Object that mimics a classic structure type for holding data and retains the order
    of the elements.

    You can think of this as an ordered DictStruct, but the name is 'OrderedStruct'
    because that is shorter ;-)

    All the methods of the dict class are supported, but they will return
    their values NOT ordered.  Instead, call _keys(), _values(), _items() and friends
    prepended with an underscore.

    Usage:
    .. code :: Python
        os = OrderedStruct(a=20)
        os.b = 'new attribute b'
        [key_value for key_value in os]
        >>> [('a', 20), ('b', 'new attribute b')]
    """

    def __init__(self, *args, **argv):
        if not argv is None:
            self.__dict__ = argv
            self.__keyorder__ = list(argv.keys())
        else:
            self.__keyorder__ = []

    def _keys(self):
        """
        Alternative for the standard dict.keys() which *does* return elements
        in order.
        """
        for key in self.__dict__.keys():
            if not key.startswith('__'):
                yield key

    def _values(self):
        """
        Alternative for the standard dict.values() which *does* return elements
        in order.
        """
        for key in self._keys():
            if not key.startswith('__'):
                yield self.__dict__[key]

    def _items(self):
        """
        Alternative for the standard dict.items() which *does* return elements
        in order.
        """
        for key in self._keys():
            if not key.startswith('__'):
                yield (key, self.__dict__[key])

    def __repr__(self):
        """
        Return string reperesentation of the OrderedStruct.
        """
        return "OrderedStruct(keys=['{}'])".format(
            "','".join(k for k in self.__keyorder__ if not k.startswith('_'))
        )

    def __str__(self):
        """
        Human-readable representation of the OrderedStruct.
        """
        s = ''
        for key in self.__keyorder__:
            s += '%s: %s\n' % (key, getattr(self, key))
        return s[:-1]

    def __setattr__(self, name, val):
        if name in ['__dict__', '__keyorder__']:
            object.__setattr__(self, name, val)
        elif not name  == '__keyorder__':
            self.__dict__[name] = val
            if not name in self.__keyorder__:
                self.__keyorder__.append(name)

    def __delattr__(self, name):
        index = self.__keyorder__.index(name)
        self.__keyorder__.pop(index)
        self.__dict__.pop(name)

    def __add__(self, other):
        """
        Return an OrderedStruct which is the superset of the current and the given
        OrderedStruct.
        """
        if not isinstance(other, OrderedStruct):
            raise ValueError("Operation '+=' (__iadd__) is only defined for other OrderedStruct instances")
        result = OrderedStruct()
        result.__keyorder__ = self.__keyorder__.copy()
        result.__dict__.update(self.__dict__)
        return result.__iadd__(other)

    def __iadd__(self, other):
        """
        Extend the current OrderedStruct by updating the current values with the values
        from the given OrderedStruct.
        """
        if not isinstance(other, OrderedStruct):
            raise ValueError("Operation '+=' (__iadd__) is only defined for other OrderedStruct instances")
        keyorderbackup = self.__keyorder__.copy()
        self.__dict__.update(other.__dict__)
        #note that this update will overwrite self.__keyorder__
        self.__keyorder__ = keyorderbackup
        for key in other.__keyorder__:
            if not key in self.__keyorder__:
                self.__keyorder__.append(key)
        return self

    def __iter__(self):
        """
        Return all keys in the OrderedDict.
        """
        for key in self.__keyorder__:
            yield key, self.__dict__[key]

    def __getitem__(self, index):
        return self.__dict__[self.__keyorder__[index]]

    def __getattr__(self, name):
        """
        Get the value of any attribute name in the internal dictionary.

        This exposes the dict methods themselves as well, such as keys(), items(), get(),
        clear(), update(), ...
.
        If the name is not present in the dictionary, raise AttributeError.
        That makes it compatible to hasattr(), which only catches
        AttributeErrors, but not KeyErrors.

        Note: this method returns 'None' for all attribute names
        which start with double underscore.  This breaks hasattr(),
        which will return True for *any* such attributename.
        """
        if name[0:2] == '__':
            return None

        return getattr(self.__dict__, name)

    def __contains__(self, key):
        """
        Check if the DictStruct contains the given key.

        The main purpose of implementing this is speed: if it is missing,
        the 'in' operator will to an iteration over all the elements instead of just
        using the hash lookup.
        """
        return key in self.__dict__
        
    def __getstate__(self):
        target = dict()
        for key, item in self.__dict__.items():
            target[key] = item
        return target
        
    def __setstate__(self, state):
        for key, item in state.items():
            self.__dict__[key] = item         


class DictStruct(object):

    """
    Object that mimics a classic structure type for holding data.

    You can consider it to be a dict with all the key/value pairs as object
    attributes, making it easier to do auto-completion on.

    Regular dict methods such as keys(), values() and get() are all present.

    Usage:
    .. code :: Python
        from iskutil.names import DictStruct
        d = DictStruct(x=50)
        d.a = 'new attribute a on first level'
        d.b = 508
        print(d.a, d.b)
    """

    def __init__(self, dictionary=None):
        '''dictionary: use the existing dictionary for this class'''
        if not dictionary is None:
            self.__dict__ = dictionary

    def __repr__(self):
        """
        Return string reperesentation of the DictStruct.
        """
        return "DictStruct(keys=['{}'])".format(
            "','".join(k for k in self.keys())
        )

    def __str__(self):
        s = ''
        for key, val in self.__dict__.items():
            s += '%s: %s\n' % (key, str(val))
        return s[:-1]

    def __getattr__(self, name):
        """
        Get the value of any attribute name in the internal dictionary.

        This exposes the dict methods themselves as well, such as keys(), items(), get(),
        clear(), update(), ...

        If the name is not present in the dictionary, raise AttributeError.
        That makes it compatible to hasattr(), which only catches
        AttributeErrors, but not KeyErrors.

        Note: this method returns 'None' for all attribute names
        which start with double underscore.  This breaks hasattr(),
        which will return True for *any* such attributename.
        """
        if name[0:2] == '__':
            return None

        return getattr(self.__dict__, name)

    def __iadd__(self, other):
        """
        Extend the current DictStruct by updating the current values with the values
        from the given DictStruct.
        """
        if not isinstance(other, DictStruct):
            raise ValueError("Operation '+=' (__iadd__) is only defined for other DictStruct instances")
        self.__dict__.update(other.__dict__)
        return self

    def __iter__(self):
        """
        Allow to loop over all keys in the DictStruct.

        Ignore keys which start with an underscore.
        """
        keys = list(self.__dict__.keys())
        for key in keys:
            if not key.startswith('_'):
                yield key

    def _clear(self, keys):
        """
        Remove the given keys (or key) from the DictStruct.

        This is a public function, but starts with an underscore to avoid it showing
        up in auto-complete, where you expect only the *content* of the DictStruct
        to appear.

        Usage:
            ds._clear(['a', 'b', 'x'])
            ds._clear('my_var')
        """
        # we expect a list; convert a single string to a list
        if isinstance(keys, str):
            keys = [keys]
        for key in list(keys):
            del self.__dict__[key]

    def __getitem__(self, key):
        """
        Get the given item using obj[angle_bracket] syntax.

        Is essentially the same as using obj.direct_access.
        """

        return self.__dict__[key]

    def __setitem__(self, key, value):
        """
        Set the given item using obj[angle_bracket] syntax.

        Is essentially the same as using obj.direct_access.
        """
        self.__dict__[key] = value

    def __delitem__(self, key):
        """
        Remove the given item from the dictstruct.

        Is an alternative to _clear().
        """
        del self.__dict__[key]

    def __contains__(self, key):
        """
        Check if the DictStruct contains the given key.

        The main purpose of implementing this is speed: if it is missing,
        the 'in' operator will to an iteration over all the elements instead of just
        using the hash lookup.
        """
        return key in self.__dict__


def addprop(inst, name, getter, setter=None, doc=None):
    cls = type(inst)
    if not hasattr(cls, '__perinstance'):
      cls = type(cls.__name__, (cls,), {})
      cls.__perinstance = True
      inst.__class__ = cls #not sure this is needed !
    setattr(cls, name, property(getter, setter, doc))

def fromfilename(fileName):
    '''parse a filename to a valid identifier
    extension is removed
    '''
    basename = os.path.basename(fileName)
    (rootname, ext) = os.path.splitext(basename)

    rootname = rootname.replace(' ','_')
    varname = ''

    ch = rootname[0]

    if ch.isdigit():
        varname += 'x' + ch
    elif ch.isidentifier():
        varname += ch
    else:
        varname += 'x' + hex(ord(ch))

    for i in range(1, len(rootname)):
        ch = rootname[i]
        if ch.isidentifier() or ch.isdigit():
            varname += ch
        else:
            varname += hex(ord(ch))

    if not varname.isidentifier():
        raise Exception('could not parse to valid identifier')

    return varname

def find_names(obj):
    #return the list of names refering to the object
    #
    #http://pythonic.pocoo.org/2009/5/30/finding-objects-names
    import gc, sys

    #Well, since the names of all locals are known at compile-time, Python optimizes function locals,
    #putting them into an array instead of a dictionary, which speeds up access tremendously.
    #But there is a way to get at the locals in a dictionary, namely the locals() function.
    #There must be some way to get Python to create it for us!
    #This is best done accessing the frame object's f_locals attribute which creates and caches this dictionary,
    #and that can be used to create dict references to all locals if the whole chain
    #of currently executed frames is traversed, as the first for loop does.
    #
    #next lines are needed to find names of compiled objects
    #not needed for life objects
    #frame = sys._getframe()
    #for frame in iter(lambda: frame.f_back, None):
    #    frame.f_locals
    #=========

    result = []
    for referrer in gc.get_referrers(obj):
        if isinstance(referrer, dict):
            for k, v in referrer.items():
                if v is obj:
                    result.append(k)
    return result

def force2bytes(s):
    """
    Convert the given string to bytes by encoding it.

    If the given argument is not a string (already bytes?), then return it verbatim.

    :param s: Data to encode in bytes, or any other object.
    :return: Bytes-encoded variant of the string, or the given argument verbatim.
    """
    if isinstance(s, str):
        return s.encode()
    else:
        return s
