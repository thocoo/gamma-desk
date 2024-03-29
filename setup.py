#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build an installable package."""

import io
import os
import sys
import glob
from pathlib import Path

from setuptools import find_packages, setup, Command, Distribution

herepath = Path(__file__).parent.absolute()
here = str(herepath)

MODULE_NAME = 'gdesk'
DISTRO_NAME = 'gamma-desk'
DESCRIPTION = 'A Python work environment image viewers & plots'
URL = 'https://github.com/thocoo/gamma-desk'
EMAIL = 'thomas.cools@telenet.be'
AUTHOR = 'Thomas Cools'

modpath = herepath / 'gdesk'

REQUIRED = [
    'numpy',
    'pillow',
    'imageio',
    'imageio-ffmpeg',
    # Exclude MatPlotLib 3.5.2 because it crashes plotting on PySide6.
    'matplotlib != 3.5.2',
    'scipy',
    'qtpy',
    'psutil',
    'numba',
    'pyzmq',
    'pywinpty; sys_platform=="win32"',
]

EXTRAS_REQUIRED = {
    'all': ['PySide6'],
    'pyside2': ['PySide2'],
    'pyside6': ['PySide6'],
    }

PYTHON_REQUIRED = '>=3.6'


def get_resources():
    found_resources = [str(modpath / 'config' / 'defaults.json'), str(modpath / 'config' / 'defaults_unix.json')]

    for path in modpath.glob('resources/**/*'):
        if path.is_dir():
            continue
        found_resources.append(str(path))

    return found_resources


with open(modpath / 'version.py') as fp:
    exec(fp.read())

# Import the README and use it as the long-description.    
with open(herepath / 'README.md', encoding='utf-8') as fp:
    LONG_DESCRIPTION = '\n' + fp.read()    

setup(
    name=DISTRO_NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author=AUTHOR,
    author_email=EMAIL,
    license='Apache License 2.0',
    url=URL,
    packages=find_packages(exclude=('tests',)),
    package_data=dict(gdesk=get_resources(),),
    entry_points={'console_scripts': [f'{MODULE_NAME} = {MODULE_NAME}.console:argexec']},
    install_requires=REQUIRED,
    include_package_data=True,
    python_requires=PYTHON_REQUIRED,
    extras_require=EXTRAS_REQUIRED,
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',        
    ],
)
