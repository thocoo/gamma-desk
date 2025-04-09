
# Use Gamma Desk with uv


## Use Gamma Desk in a project

To create a simple project with Gamma Desk using `uv`, follow these steps.

Create a folder and cd into it.

```shell
uv init
uv add gamma-desk
```

To run Gamma Desk:

```shell
uv run gdesk
```


## Try the latest Gamma Desk from GitHub

```shell
uv tool install --python 3.13 git+https://github.com/thocoo/gamma-desk
uvx --from gamma-desk gdesk path/to/image.tif
```


## Build Gamma Desk wheel

```shell
uvx flit build
uvx flit build --format wheel
uvx flit build --format sdist
```


## Run Gamma Desk test suite

```shell
uv run --python 3.13 python -m gdesk -i ./test/setup/test_gdesk.py
QT_API=pyqt5 && uv run --python 3.13 --with pyqt5 python -m gdesk -i ./test/setup/test_gdesk.py
QT_API=pyqt6 && uv run --python 3.13 --with pyqt6 python -m gdesk -i ./test/setup/test_gdesk.py
uv run --python 3.10 --extra pyside2 python -m gdesk -i ./test/setup/test_gdesk.py
uv run --python 3.10 --extra pyside6 python -m gdesk -i ./test/setup/test_gdesk.py
```


## Run Gamma Desk with custom config file

```shell
uv run python -m gdesk -c ./test/gdconf.json
```


## Upload release files to PyPI

```shell
uv publish --index pypi dist/gamma_desk-1.6.4.dev0-py3-none-any.whl
uv publish --index pypi dist/gamma_desk-1.6.4.dev0.tar.gz
```
