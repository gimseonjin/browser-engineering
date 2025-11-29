# Browser Engine Package
# A simple web browser implementation in Python

__version__ = "1.0.0"
__author__ = "Browser Practice Project"

# Re-export main classes for convenience
from .core.browser import Browser
from .ui.chrome import Chrome
from .content.tab import Tab
from .content.frame import Frame

__all__ = ['Browser', 'Chrome', 'Tab', 'Frame']
