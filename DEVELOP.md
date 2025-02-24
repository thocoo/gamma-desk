
# Gamma Desk development

Project management is handled with 'uv'.

This means no explicit 'installation' is necessary for development.


## Version bump

Edit `version` in the `[project]` section of `pyproject.toml`.


## Package

    uvx flit build


## Run

    uv run --python 3.13 gdesk
