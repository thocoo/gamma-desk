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

It is prefered to use gdesk with pyside2

    pip install gamma-desk[pyside2] 

but it should also work with pyside6

    pip install gamma-desk[pyside6] 
  

# Usage

    python -m gdesk
  
or

    gdesk
  

# More documentation

[Program Help](https://thocoo.github.io/gdesk-data/docs)

[Source Code](https://github.com/thocoo/gamma-desk)

[On PyPi](https://pypi.org/project/gamma-desk)


# Dependencies 

`numpy`
`matplotlib`
`scipy`
`PySide2`
`qtpy`
`psutil`
`pyzmq`
`toml`
`pillow`
`imageio`
`imageio-ffmpeg`
`numba`
`pywinpty`
