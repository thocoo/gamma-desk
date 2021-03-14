"""Function tools."""
from types import CodeType, FunctionType


def find_nested_func(parent, child_name, globs, closure=None):
    """
    Find nested funcion.

    Return the function named <child_name> that is defined inside
    a <parent> function
    Returns None if nonexistent
    """
    consts = parent.__code__.co_consts
    for item in consts:
        if isinstance(item, CodeType) and item.co_name == child_name:
            return FunctionType(item, globs, closure=closure)
