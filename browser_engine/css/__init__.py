# CSS (Cascading Style Sheets) components
from .css_parser import CSSParser
from .tag_selector import TagSelector
from .descendant_selector import DescendantSelector
from .cascade import cascade_priority
from .style import style, INHERITED_PROPERTIES

__all__ = [
    'CSSParser',
    'TagSelector',
    'DescendantSelector',
    'cascade_priority',
    'style',
    'INHERITED_PROPERTIES',
]
