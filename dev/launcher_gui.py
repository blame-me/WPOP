"""PyInstaller entry point: launches the wpop desktop GUI."""
import sys

from wpop.ui.app import main

if __name__ == "__main__":
    sys.exit(main())