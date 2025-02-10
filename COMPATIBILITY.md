
# Package compatibility


## Windows
 
We use a compiled version of `pywinpty`; otherwise you'd need a Rust compiler.

Since `PyWinPty` dropped Python 3.8 support in `v2.0.15`, we stay below that version on 3.8.


## Matplotlib

Avoid MatPlotLib 3.5.2: because it crashes plotting on PySide6.


## PySide6

PySide 6.8.0 has a bug which breaks qtpy; avoid that specific release.


## Numpy

Numpy v2 introduces some different behavior w.r.t. clipping.

Also, all PySide6 releases before v6.8 choke on numpy 2.x.

We try to avoid numpy v2, but that is only possible up to Python v3.12.

3.12 also misses `distutils`, which is inconvenient for numpy installing.

To avoid the most problems, starting from Python 3.12, we move to numpy v2 and require PySide6 v6.8.


## PySide2

Using `pyside2` instead of `pyside6` is possible only up to Python 3.10.

For this reason, PySide6 is preferred for new installs.

To use `pyside2`, install with `--no-deps` and install dependencies manually.
