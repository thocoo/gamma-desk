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

"""Bench Eye"""

from .version import VERSION_INFO
from .core.conf import config, configure
from .core.gui_proxy import gui
from .live import use, using

progname = 'Gamma Desk'
doc_html = 'https://thocoo.github.io/gdesk-doc'
doc_html_extra = ['https://test.pypi.org/project/gamma-desk']

__release__ = "-".join(map(str, VERSION_INFO)).replace("-", ".", 2)
__version__ = ".".join(map(str, VERSION_INFO[:3]))

shell = None

def refer_shell_instance(shellinst):
    global shell
    shell = shellinst