"""A collections of utils."""
import sys
from functools import reduce

import numpy as np


def new_id_using_keys(keys):
    """Find the lowest new id starting from already exisiting ids."""
    keys = np.array(keys)

    if len(keys) == 0:
        return 1

    keys.sort()
    np.diff(keys)
    gaps = np.where(np.diff(keys) > 1)[0]

    if len(gaps) > 0:
        key = keys[gaps[0]] + 1
    else:
        key = keys[-1] + 1

    return key


def lazyf(template):
    """Do a f-string formating."""
    frame = sys._getframe(1)
    result = eval('f"""' + template + '"""', frame.f_globals, frame.f_locals)
    return result


def clip_values(dtype):
    """Get the lowest and highest clipvalue for a certain numpy data type."""
    if dtype == 'uint8':
        low, high = 0, 255

    elif dtype == 'int8':
        low, high = -127, 127        

    elif dtype == 'uint16':
        low, high = 0, 65535       

    elif dtype == 'int16':
        low, high = -32768, 32767        
        
    elif dtype == 'uint32':
        low, high = 0, 4294967295       

    elif dtype == 'int32':
        low, high = -2147483648, 2147483647
        
    elif dtype == 'uint64':
        low, high = 0, 2**63-1       

    elif dtype == 'int64':
        low, high = -2**63, 2**63-1        

    elif dtype in ['float', 'double']:
        low, high = 0, 1

    else:
        raise AttributeError(f'clip values not defined for {dtype}')

    return low, high


def clip_array(array, dtype):
    """Clip the array to clipvalues of dtype."""
    if dtype in ['float16', 'float32', 'float64', 'float', 'double']: return array
    
    array = array.clip(*clip_values(dtype)).astype(dtype)
    return array

def get_factors(n):
    return set(reduce(list.__add__, 
                ([i, n//i] for i in range(1, int(n**0.5) + 1) if n % i == 0)))