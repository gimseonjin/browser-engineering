# User interface components (Browser Chrome only)
from .chrome import Chrome

# Re-export from content for backwards compatibility
from ..content import Tab, Frame

__all__ = ['Chrome', 'Tab', 'Frame']
