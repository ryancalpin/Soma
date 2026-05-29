"""Single-command launcher: start the local server and open the browser.

Binds to 127.0.0.1 only so patient data never leaves the machine.
"""

from __future__ import annotations

import threading
import webbrowser

import uvicorn

from soma import config


def _open_browser() -> None:
    webbrowser.open(f"http://{config.HOST}:{config.PORT}")


def main() -> None:
    config.ensure_dirs()
    # Open the browser shortly after the server starts.
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run("soma.main:app", host=config.HOST, port=config.PORT, reload=False)


if __name__ == "__main__":
    main()
