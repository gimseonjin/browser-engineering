"""CSS Tag Selector"""
from ..dom.element import Element


class TagSelector:
    """태그 이름으로 요소를 선택하는 CSS 셀렉터"""

    def __init__(self, tag):
        self.tag = tag
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag
