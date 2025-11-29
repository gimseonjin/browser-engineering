class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent
        self.is_focus = False

    def __repr__(self) -> str:
        return f"<{self.tag}>"