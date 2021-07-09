v0.1.3
------

- Add menu item close other panels of same category
- Add guess of resolution on raw image import dialog
- new definition and system of which config files to load

  - config item "next_config_files" replaced by "path_config_files"
  - is now a list of files to load in order
  - by default: ["%USERPROFILE%/AppData/Local/Gamma-Desk/gdconf.json", "gdconf.json"]   
  
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

 
