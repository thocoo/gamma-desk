import sys
import pprint

if __name__ == '__main__':
    pprint.pprint(sys.path)
    from gdesk.external import channel
    channel.start_gui_as_child()