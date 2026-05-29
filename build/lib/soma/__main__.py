"""Module entrypoint: ``python -m soma`` starts the local server and opens a browser.

Binds to 127.0.0.1 only so patient data never leaves the machine. This is the entry
used by the portable USB launchers (Soma.command / Soma.bat).
"""

from __future__ import annotations

import threading
import webbrowser

from . import config


def _open_browser() -> None:
    webbrowser.open(f"http://{config.HOST}:{config.PORT}")


def main() -> None:
    import uvicorn

    config.ensure_dirs()
    print(f"\n  Soma is running.  Open  http://{config.HOST}:{config.PORT}  in your browser.")
    print("  (Keep this window open. Close it to stop Soma.)\n")
    # Open the default browser shortly after the server comes up.
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run("soma.main:app", host=config.HOST, port=config.PORT, reload=False)


if __name__ == "__main__":
    main()
