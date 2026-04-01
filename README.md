# Gamma Desk

![Gamma Desk Logo](https://github.com/thocoo/gamma-desk/raw/main/gdesk/resources/logo/logo_128px.png)

A Python work environment with image viewers & Plots


# Screen shots

![Screen Shot 1](https://github.com/thocoo/gamma-desk/raw/main/doc/sphinx/source/figures/screenshot_01.jpg)


# Features

- Multiple Consoles in the Gui Process
- Multiple Child Process Consoles
- More advanced auto command completion
- Matplotlib integration
- Image Viewers using QT Painter
- Image histograms
- Image column & row profiles
- Advanced window & panel docking
- Linked Image Viewers


# Installation

Install Gamma Desk with one of the supported Qt backends, or the default one.

    pip install gamma-desk[default]
    pip install gamma-desk[pyside6]
    pip install gamma-desk[pyside2]

Backends are `pyside6` (default from 3.11 and up) or `pyside2` (default up to Python 3.10).
PyQt backends `pyqt6`, `pyqt5` are tested less thoroughly.

As of Gamma Desk v1.10, on Python >= 3.12, the `pyside6` extra installs `pyside6-essentials`
instead of `pyside6`, which avoids the large dependency `pyside6-addons`.


# Usage

    python -m gdesk
  
or

    gdesk
    gamma-desk
  

# More documentation

[Program Help](https://thocoo.github.io/gdesk-data/docs)

[Source Code](https://github.com/thocoo/gamma-desk)

[On PyPi](https://pypi.org/project/gamma-desk)


# Dependencies 

`numpy`
`numba`
`matplotlib`
`scipy`
`PySide6` or `PySide2`
`qtpy`
`psutil`
`pyzmq`
`toml`
`pillow`
`imageio`
`imageio-ffmpeg`
`numba`
`pywinpty`
