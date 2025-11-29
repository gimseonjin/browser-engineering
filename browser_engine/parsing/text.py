class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent
        self.is_focus = False
    
    def __repr__(self) -> str:
        return repr(self.text)