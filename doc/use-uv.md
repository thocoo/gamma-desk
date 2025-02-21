
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


## Build Gamma Desk wheel

```shell
uvx filt build
uvx filt build --format wheel
uvx filt build --format sdist
```


## Run Gamma Desk test suite

```shell
uv run --python 3.13 python -m gdesk -i ./test/setup/test_gdesk.py
uv run --python 3.10 --group pyside2 python -m gdesk -i ./test/setup/test_gdesk.py
uv run --python 3.10 --group pyside6 python -m gdesk -i ./test/setup/test_gdesk.py
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
