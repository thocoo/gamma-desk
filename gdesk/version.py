
"""Version details of Gamma Desk"""

from importlib.metadata import version
from packaging.version import parse

__version__ = version("gamma-desk")
__version_info__ = parse(__version__)

VERSION_INFO = __version_info__
VERSION = __version__