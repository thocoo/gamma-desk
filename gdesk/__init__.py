#-------------------------------------------------------------------------------
# Copyright 2021 Thomas Cools
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#-------------------------------------------------------------------------------

"""Gamma Desk"""

import sys
from .version import VERSION_INFO
from .core.conf import config, configure

#from .core.gui_proxy import gui
gui = None

from .live import use, using

PROGNAME = 'Gamma Desk'
DOC_HTML = 'https://thocoo.github.io/gdesk-data/docs'
DOC_HTML_EXTRA = ['https://test.pypi.org/project/gamma-desk']

__release__ = "-".join(map(str, VERSION_INFO)).replace("-", ".", 2)
__version__ = ".".join(map(str, VERSION_INFO[:3]))

shell = None


def init_tiny_gdesk(workspace=None):
    """
    Init the most minimal gdesk environment.
    Load no gui components.
    Init a shell object but leave the stdout and input as is.
    Do not initialize the logging.
    Init a fake gui object.
    """
    from gdesk.core import shellmod
    from gdesk.core import gui_proxy
    
    if workspace is None:
        frame = sys._getframe(1)
        workspace = frame.f_globals
        
    shell = shellmod.Shell(workspace, redirect=False, logdir=False)
    refer_shell_instance(shell)
        
    gui = gui_proxy.FakeGui()
    shell.wsdict['gui'] = gui    
    refer_gui_instance(gui)
    

def refer_shell_instance(shellinst):
    """refer_shell_instance"""
    global shell
    shell = shellinst


def refer_gui_instance(guiinst):
    global gui
    gui = guiinst