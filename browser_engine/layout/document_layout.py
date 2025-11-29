from ..common.constants import HSTEP, VSTEP
from ..dom.text import Text


class DocumentLayout:
    def __init__(self, node, width):
        self.node = node
        self.parent = None
        self.width = width
        self.children = []

        self.x = None
        self.y = None
        self.height = None

    def layout(self):
        from .block_layout import BlockLayout
        child = BlockLayout(self.node, self.width, self, None)
        self.children.append(child)
        self.x = HSTEP
        self.y = VSTEP
        self.width = self.width - 2 * HSTEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []
    
    def should_paint(self):
        return isinstance(self.node, Text) or \
            (self.node.tag == "input" or self.node.tag == "button")