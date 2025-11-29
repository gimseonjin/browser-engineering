"""DOM Element node"""


class Element:
    """HTML Element를 나타내는 DOM 노드"""

    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent
        self.is_focus = False
        self.style = {}  # CSS 스타일

    def __repr__(self) -> str:
        return f"<{self.tag}>"
