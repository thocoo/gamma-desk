import ctypes
GW_HWNDNEXT = 2

def get_windows():
    '''Returns windows in z-order (top first)'''
    user32 = ctypes.windll.user32
    lst = []
    top = user32.GetTopWindow(None)
    if not top:
        return lst
    lst.append(top)
    while True:
        next = user32.GetWindow(lst[-1], GW_HWNDNEXT)
        if not next:
            break
        lst.append(next)
    return lst
    
    
def get_z_values(*windows):
    """
    Order these window in z order
    Top window first and lowest z value
    returns a list of [(z, window), ...]
    """
    all_winids_zorder = get_windows()
    zorder = ((all_winids_zorder.index(window.winId()), window) for window in windows if window.winId() in all_winids_zorder)
    return sorted(zorder, key = lambda item: item[0])