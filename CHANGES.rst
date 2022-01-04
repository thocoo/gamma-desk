v0.2.0
------

date: 2021-11-29

- add read_raw to gui.img
- keep numpy at 1.20.3 (numba doesn't support numpy > 1.20)
- Add shell.pty(), the virtual terminal
- Add gui.img.grab() to grab the image viewer widget as an numpy array
- Selectable logging level in console menu
- Fixes on image conversion to other datatypes
- Display pixel value labels on pixels on large zooms
- Fix of swap of channels on bayer split
- Support Matplotlib 3.5
- Delay plot panel creation if not interactive
- Improved behavior of histograms for doubles
- Add support for more image types

 - uint32
 - int8
 - int16
 - int32
 
- Add operation menu
- Add opencv menu
- Split image viewier status panel into multiple panels
- Customizable panel size at init
- Improved panel resize behavior of histograms and profiles
- Add test image
- Various bug fixes


v0.1.4
------

date: 2021-10-22

- add as_default argument to gui.img.set_offset_gain()
- On functional call in console, switch to running mode
- Inherit panel size to new window
- Reorder buttons on histogram panel
- Improve internal panel selection
- Extend contrast options
- Replace sqrt scale in semilog on histogram panel


v0.1.3
------

- Add menu item close other panels of same category
- New raw image import featues:

  - guess of resolution based of file size
  - Little or big endian pixels
  
- new definition and system of which config files to load

  - config item "next_config_files" replaced by "path_config_files"
  - is now a list of files to load in order
  - by default: ["%USERPROFILE%/AppData/Local/Gamma-Desk/gdconf.json", "gdconf.json"]   
  
- More conservative panel drop policy  
- Matplotlib backend for child processes
  Use ``pylab.switch_backend('module://gdesk.matplotbe')`` in child process to activate
- Bug fixes


v0.1.2
------

date: 2021-05-04

- Add options to disable auto scroll down on new text added to console output
- Fix Ctrl+O shortcut for console
- Using Ctrl+Shift+Z or Ctrl+Shift+Y for prior or next image
- On StdInput: using maximum block count disables undo history, removing the set of maximum block count
- Fix bad returned part causing doubling ' in some cases
- Add loglevels to logfile and console logging handlers
- Use TIFF FI format by default on save image dialog
- Add menu items on image panel: to 8-bit, to 16-bit
- Save the selected figure to a file
- Adding hist size policy to config
- Support for different versions of matplotlib: 3.2, 3.3 and 3.4
- Add multiple shortcuts on plot menu


v0.1.1
------

date: 2021-03-30

- Console: Open file with suitable panel class
- Byte size limit on Image History 
- Support panel proxies with shell.edit(object) 
- Improve panel placement in scroll area (still experimental)
- Code clean-up
- Bug fixes


v0.1.0
------

date: 2021-03-23

- Add bindmenu to image viewer
- Add more documentation
- Add command history panel
- Add HTML panel


v0.0.1
------

date: 2021-03-22

- First release

 
