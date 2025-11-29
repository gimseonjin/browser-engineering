"""DOM Text node"""


class Text:
    """텍스트 콘텐츠를 나타내는 DOM 노드"""

    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent
        self.is_focus = False
        self.style = {}  # CSS 스타일

    def __repr__(self) -> str:
        return repr(self.text)
