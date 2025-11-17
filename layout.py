import tkinter.font as tkFont
from constants import HSTEP, VSTEP
from font import get_font


class Text:
    def __init__(self, text):
        self.text = text

class Tag:
    def __init__(self, tag):
        self.tag = tag

def lex(body):
    out = []
    buffer = ""
    in_tag = False

    for c in body:
        if c == "<":
            in_tag = True
            if buffer: out.append(Text(buffer))
            buffer = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        else:
            if c == "&lt;":
                c = "<"
            elif c == "&gt;":
                c = ">"
             
            buffer += c

    if not in_tag and buffer:
        out.append(Text(buffer))

    return out

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
        for tok in tokens:
            self.token(tok)
        self.flush()
    
    def token(self, token):
        if isinstance(token, Tag):
            self.tag(token)

        if isinstance(token, Text):
            for word in token.text.split():
                self.word(word)

    def tag(self, token):
        if token.tag == "i":
            self.style = "italic"
        elif token.tag == "/i":
            self.style = "roman"
        elif token.tag == "b":
            self.weight = "bold"
        elif token.tag == "/b":
            self.weight = "normal"
        elif token.tag == "small":
            self.size -= 2
        elif token.tag == "/small":
            self.size += 2
        elif token.tag == "big":
            self.size += 4
        elif token.tag == "/big":
            self.size -= 4
        elif token.tag == "br":
            self.flush()
        elif token.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP
    
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