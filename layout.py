import tkinter.font as tkFont
from constants import HSTEP, VSTEP
from font import get_font


class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent
    
    def __repr__(self) -> str:
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self) -> str:
        return f"<{self.tag}>"

class Layout:
    def __init__(self, tokens, width):
        self.display_list = []
        self.line = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.size = 12
        self.width = width
        self.weight = "normal"
        self.style = "roman"

        self.recurse(tokens)
        self.flush()
    
    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "br/":
            self.flush()
    
    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP
    
    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    # Text 의 text string
    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        
        w = font.measure(word)
        # 줄이 넘치면 먼저 현재 줄을 flush
        if self.cursor_x + w > self.width - HSTEP:
            self.flush()
        
        # 단어를 현재 줄에 추가
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for _, _, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))
        
        max_descent = max(metric["descent"] for metric in metrics)
        self.cursor_y = baseline + 1.25 * max_descent

        self.cursor_x = HSTEP
        self.line = []