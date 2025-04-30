
vNext
-----
date: TBD

- Support `GDESKSTARTUP` environment variable; execute that file when configured.
- Improve support for PyQt5, PyQt6.
- Support multiple ROI widgets.


v1.7.0
------

date: 2025-04-30

- Do project management with ``uv``.
- Expose detailed (parsed) version information (``packaging.version.Version``)

Do note the version semantics have changed:

* ``VERSION_INFO`` does no longer exist.
* ``__version__`` is now a string.
* Access ``__version_info__`` for detailed version attributes.


v1.6.3
------

date: 2025-02-05

- Fixing getfile in formlayout
- Add elapsed attribute in console


v1.6.2
------

date: 2025-01-22

- import of Path object was missing in formlayout


v1.6.1
------

date: 2024-12-13

- The workspace __module__ is now a string instead of the module itself


v1.6.0
------

date: 2024-12-13

- Fix to except Exception to BaseException in the command loop
- Fix the missing raise of error to the command loop (cause 10 sec check on KeyBoard break)
- cleanup code for mode func and func_ext
- Fix getcodefile for script files
- fix enforce ymin to 0 for all scaling modes except for log+cum
- Cycle through y-scales on button press
- Remove roi switch, draw histograms based on active statistics
- Add multi mask selection on profiles and histogram
- Reduce keyboard capture to 2 sec
- SURPRISE, floor division is faster than bitshift! (a x86 thing)
- Enforcing parallel execution seems to only stress the PC to 100% CPU, but very little gain in performance
- Tryout auto completion on input (on the 1 level higher workspace)
- Show the top of the html page on show
- pop missing modules before update and reget the function pointer after a possible update
- Prepare for window variant of the textbrowser dialog
- The ask_refresh flow (request and acknowledge) was lagging
- ask_refresh was not set to 0 if no update was needed.
- But because of this, there was also no mark_for_update needed for next time.
- Which was also not done.
- Split markUpdateCall into markUpdateCallTop and markUpdateCallNest
- Use an Enum for the Update Flags
- Use enum for load results
- Merge markUpdateCallTop and markUpdateCallNest and use nested argument
- Return at begin in check_for_update if UpdateFlag.DONE
- Fixing ImportError message in mark_for_update
- Use module qualifier as key instead of the path
- remove unused workspace attribute and argument from manager
- Refer script manager in workspace
- Auto set top attribute based on __loader__ value in caller workspace
- Use notepad.exe as backup text editor
- Remove the unused path argument and attribute from LiveScriptModuleReference
- Add is_nested and is_main function
- Test for LiveScriptManager type in is_nested
- use the is_nested() instead of the top or nested attribute
- Removing all top and nested attributes and arguments
- Fix correct class name in __repr__
- Make 'console' font configurable
- Scripts: Fix proper loading of prior failed loads
- Add a required roi size > 0 to be valid statistics
- Prevent markUpdateCall on LiveScriptModuleReference
- Let the autocompleter execute the __script_manager__.mark_for_update()
- Raise KeyError on trying to overwrite a predefined mask
- Allow to select roi on full sized masks
- Log info of succeed loading a script
- Use the name 'roi' for the widget selection and 'mask' for all the other roi's.


v1.5.0
------

date: 2024-11-14

- Fix error on loading new panel layout
- Add context menu to statistics panel to choose columns
- Add call_func_ext as extension on call_func to call a function on another thread of process with kwargs
- Extend the functionality on default dir and file for formlayout get and set file/dir dialog
- Fix cancel of Choose statistic dialog and add stat dependent formatting
- Fix some ndim = 3 behavior combined with bayer pattern
- Add callbackexcept to wrap around a callback to capture errors from other thread or process
- Return a error codes on deeper exception
- Add dump and who functions
- Fix gamma for negative values
- Improved walking ants (fixes missing redraws)
- Add color argument on creation
- Add add_roi_slices to image proxy
- Add roi of selected pixel to select menu
- Support empty roi
- Add Reselect Roi as replacement for Select All
- Add ViewerRoiAccess as easy interface to the roi's
- Auto color for new roi's
- Don't enforce 4 decimals
- Add menu to select custom roi
- add gui.roi as The named roi interface of the current image viewer
- Refresh profiles and histogram on check/uncheck roi's
- Add active argument to add_roi_slices
- fix(34): Avoid crash on PySide v6.8.0
- Roi's: Move non actives to end and new actives to last active
- Add header menu
- Add body context menu and more advanced check box click behavior
- Add a simple textbrowser message window
- Add TextBrowser dialog
- dev: Base 'interprete' console background on 'base' color
- This is white (#ffffff) for the light windows theme and a dark gray (#2d2d2d) for the dark windows theme. For pyside2 and older pyside6 it remains white even if the dark windows theme is active.
- This makes the dark theme at least usable, but it still does not look great.
- dev: Use default widget back ground color for rulers
- This is needed to make it readable in the dark mode and should not affect the light mode
- dev: Force black text on light background labels
- Otherwise, in dark mode the white text won't be readable
- dev: Expand range of allowed matplotlib versions
- doc(minor): Add some type hints
- fix(36): Avoid crash with matplotlib/PySide6/Linux
- Don't interfere with buffer ref count.
- fix(36): Only adjust refcount on PySide/Pyside2
- Fix passing the error message to gui for exec_func and exec_one_command in console interpreter
- Support for use of default messagebox icons on textbrowser dialog
- Set the icon to the titlebar
- Add cfa pattern icons
- Replace default titlebar of statwindow with the profbutton itself
- Add 20, 22 and 24 bit scales in levels
- Make a group of 3 button for y scale: lin, log, and 1
- Extend the statistcs/roi toolbar
- Add checkbox icons
- Use check_boxes icon
- Fix docking button for StatsDock
- Move the ImageViewerWidget object to separate file
- Add gui.img.is_roi_selected()
- Add icons for rgb and monochrome masks selection
- Add mask selection button to statspanel
- Add option for cumulative histogram
- Use inverse error function scaling for log+norm levels scaling
- Remove commented out code
- Move imgview status bar to separate file
- Don't freeze y or enforce fixed y 0 when moving the plot if log and cumulative
- Remove auto show of roi selection, use double click or menu item
- Add refresh after adding new roi
- Prevent content editing the statistic panel
- Request image viewer context menu by signaling
- Remove all searchForRoiSlot after context menu ended
- Hide the dock when needed on docking
- Give the __wrapped__ object priority on shell.edit
- Add gui.putdir()
- dev: Create an image panel if needed when loading file in ndim panel
- fix: Apply all Linux-specific workarounds also to OSX
- fix: Disable redbull on non-Windows platforms
- fix: Import PressKey only on Windows
- fix: Make compatible with PySide6 v6.8.0.2
- fix: Don't use native menu bar on OSX
- Let Qt render the menu inside the window.
- dev: Fix colored background for checked tool button
- This is needed for pyside6 where for some reason it is not visible if it is checked or not in the default style. But it does not hurt pyside2 either.
- Add options to turn of the ylabels on the levels
- Don't enforce ymin=0 for auto y zoom
- add setWaitCursor and restoreCursor
- rename setWaitCursor to setBusyCursor and use BusyCursor
- Add button in statpanel to cycle through show onyl roi/hide roi or show  all
- Add button in level panel to cycle through show onyl roi/hide roi or show  all
- Tolerate a selected rows on the now empty table
- Use an eye icon for the show/hide/all roi menu
- Don't redefine the chanstat everything, but only update the needed items
- Remove some roi icons
- Still overwrite all predefined mask def by default
- Support Python 3.13


v1.4.0
------

date: 2024-09-27

- Add more options for the column and row profiles
- Replace meanprofile by the all mask profile
- Make roi profiles as an auto generated mask profile
- Add profile per color for full color images
- Tune alpha channel of profiles of roi versus full image
- Prepare imgdata for more general masking
- use roi. prefix for roi related masks
- Add Gr and Gb
- Add the different bayer configs for profiles
- add cfa parameter
- Add Data split menu
- Use same mask definitions for histogram and profiles
- Add set_cfa to viewer proxy
- Fix mask definition error
- Add and use roi.color item to masks
- Only keep auto zoom in profiles context menu
- Change mouse cursor on roi on hovering
- Use selectmenu as context menu
- set pickCursor
- Ignore center button release on roi
- Remove unused function
- using imgdata to organize the profiles
- Fix to remove roi profiles
- Fix update levels on roi removal
- Remove the not cached histogram option
- Fixing start slice from 0
- Ensure minimum roi size of 1x1
- Update roi only if visible on show_array
- Also return the return lock
- Tolerate different ndim for slices and full_array
- Rename arr2d to toi and attach_arr2d to attach_full_array
- Extend the statistic dock
- Add statsPanel in the corner of image viewer
- Remove StatsticPanel from levels
- Layout fixes related to statspanel
- Add addRoiStaistics
- Remove unused arguments
- Clear the custom chanstat on next shown image
- Add removeRoiStatistics and  selectProfile
- Fix empty masks to delete
- Change color of K mask to grey
- Set functional limits on Statistic panel dock
- Add select mask feature on levels
- Add skip_init argument for faster show_array
- Change chanstats gui
- Refresh statpanel after roi hide
- Fix error on std of mask of size 1
- Add option to normalize histogram
- Add active property to chanstats and checkboxes in statistic panel
- Remove fullImageVisible on profiles
- Fix z values for histograms
- Add isCleared on chanstat
- Use preferred order of the masks
- Show the roi with the selection widget


v1.3.1
------

date: 2024-07-01

- Fix for extra argument 'title' of new_panel()


v1.3.0
------

date: 2024-06-28

- formlayout: add setfile
- Add echo feature to stdout
- pass title from json setting file to panel long_title


v1.2.0
------

date: 2024-05-15

- On image sigma gain, when calculated black and white points are the same, ignore the action
- Add option to clear the stdin queue on Keyboardbreak
  config.json: console.clear_on_break = true
- Limit the Keyboard breakable part to use_one_func() and use_one_command()


v1.1.0
------

date: 2024-04-19

- gcore.guiapp: return the shortcut instance on setShortCut
- Raise Import error if live script is not found
- Add log_level argument to SubThreadConsole init


v1.0.0
------

date: 2024-03-22

- Add support for Darwin
- Add successive key auto-complete


v0.9.0
------

date: 2024-02-24

- Bug Fixes


v0.8.0
------

date: 2023-12-15

- Bug Fixes 


v0.7.0
------

date: 2023-08-29

- Add support for roi on column and row profiles


v0.6.0
------

date: 2023-06-30

- Support for more recent matplotlib 


v0.5.0
------

date: 2023-03-07

- Improve histogram
- Fix numpy with numba compatibility
- Add support for Python 3.11


v0.4.0
------

date: 2022-10-11

- Add support for Python 3.10
- Add support for PySide6


v0.3.0
------

date: 2022-02-25

- Fixes for Linux


v0.2.0
------

date: 2022-01-04

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
- Split image viewer status panel into multiple panels
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
