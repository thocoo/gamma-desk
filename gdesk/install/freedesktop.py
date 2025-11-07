"""
Install the current Gamma Desk as an application in a FreeDesktop.org desktop environment.

This places a GammaDesk.desktop file in folder `~/.local/share/applications/`.

Tested on Ubuntu 24.4 LTS.

Usage:

    uv run -m gdesk.install.freedesktop

"""

import sys
from pathlib import Path

import gdesk


HOME = Path.home()
APP_DESKTOP_FILE = HOME / ".local/share/applications/GammaDesk.desktop"
DESKTOP_FILE_TEMPLATE = "gdesk/resources/install/freedesktop/GammaDesk.desktop"


def install() -> None:
    """
    Create a GammaDesk.desktop file in the user's applications folder.

    This assumes the environment is non-ephemeral, and has its user scripts in the same
    folder as the Python executable.
    """
    if APP_DESKTOP_FILE.exists():
        print(f"Desktop file already exists: '{APP_DESKTOP_FILE}'.", file=sys.stderr)
        return

    package_folder = Path(gdesk.__file__).parent.parent
    scripts_folder = Path(sys.executable).parent

    desktop_file_template = package_folder / DESKTOP_FILE_TEMPLATE
    desktop_file_content = desktop_file_template.read_text()
    desktop_file_content = desktop_file_content.replace("PACKAGE_PATH", str(package_folder))
    desktop_file_content = desktop_file_content.replace("SCRIPTS_PATH", str(scripts_folder))

    APP_DESKTOP_FILE.write_text(desktop_file_content)


def uninstall() -> None:
    """Delete the GammaDesk.desktop file from the user's applications folder."""
    if not APP_DESKTOP_FILE.exists():
        return

    APP_DESKTOP_FILE.unlink()


if __name__ == "__main__":
    install()
