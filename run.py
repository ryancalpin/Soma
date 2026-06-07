"""Developer launcher. Thin wrapper around ``python -m soma``.

For end users, the portable bundle's Soma.command / Soma.bat launchers call
``python -m soma`` directly.
"""

from soma.__main__ import main

if __name__ == "__main__":
    main()
