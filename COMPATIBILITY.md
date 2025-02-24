
# Package compatibility


## Windows
 
We use a compiled version of `pywinpty`; otherwise you'd need a Rust compiler.

Since `PyWinPty` dropped Python 3.8 support in `v2.0.15`, we stay below that version on 3.8.


## Matplotlib

Avoid MatPlotLib 3.5.2: because it crashes plotting on PySide6.


## Qt wrapper

Gamma Desk is best tested with PySide2 and PySide6.  In the past, PyQt5 was also used.

On Python 3.11 and higher, PySide6 is a hard dependency as PySide2 is not available there.

Up until Python 3.10, you must choose the 'extra' `pyside6` or `pyside2`.

PySide 6.8.0 (requiring Python >= 3.12) has a bug which breaks qtpy; avoid that specific release.

If you want to use PyQt5, you have to install it manually and set environment variable `QT_API=PyQt5`.

| Python | PySide6  | PySide2  | PtQt5    | PyQt6    |
|--------|----------|----------|----------|----------|
| 3.13   | required | n/a      | possible | untested |
| 3.12   | required | n/a      | possible | untested |
| 3.11   | required | n/a      | possible | untested |
| 3.10   | optional | optional | possible | untested |
| 3.9    | optional | optional | possible | untested |
| 3.8    | optional | optional | possible | n/a      |
|--------|----------|----------|----------| -------- |


## Numpy

Numpy v2 introduces some different behavior w.r.t. clipping.

Also, all PySide6 releases before v6.8 choke on numpy 2.x.

We try to avoid numpy v2, but that is only possible up to Python v3.12.

3.12 also misses `distutils`, which is inconvenient for numpy installing.

To avoid the most problems, starting from Python 3.12, we move to numpy v2 and require PySide6 v6.8.


# Pooch

Pooch is used by scipy for downloading datasets (used in test only).

Older scipy versions (pre Python 3.9) had the datasets built-in.
