# Re-export all selector classes for backward compatibility
from .tag_selector import TagSelector
from .descendant_selector import DescendantSelector
from .cascade_priority import cascade_priority

# Re-export for backward compatibility
__all__ = [
    'TagSelector',
    'DescendantSelector',
    'cascade_priority'
]