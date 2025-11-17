from constants import HSTEP, VSTEP, WIDTH
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

class DrawText:
    def __init__(self, x1, y1, text, font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            anchor="nw"
        )

class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width = 0,
            fill=self.color
        )

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
        child = BlockLayout(self.node, self.width, self, None)
        self.children.append(child)
        self.x = HSTEP
        self.y = VSTEP
        self.width = self.width - 2 * HSTEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []

class BlockLayout:
    BLOCK_ELEMENTS = [
        "html", "body", "article", "section", "nav", "aside",
        "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
        "footer", "address", "p", "hr", "pre", "blockquote",
        "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
        "figcaption", "main", "div", "table", "form", "fieldset",
        "legend", "details", "summary"
    ]

    def __init__(self, node, width, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.width = width

        self.x = None
        self.y = None
        self.width = None
        self.height = None

        self.display_list = []

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"

        elif any([isinstance(child, Element) and \
                child.tag in self.BLOCK_ELEMENTS \
                for child in self.node.children]):
            return "block"

        elif self.node.children:
            return "inline"
        else:
            return "block"

    def layout(self):
        self.x = self.parent.x
        self.width = self.parent.width

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        mode = self.layout_mode()
        if mode == "block":
            previous = None
            for child in self.node.children:
                next = BlockLayout(child, self.width, self, previous)
                self.children.append(next)
                previous = next
            
            for child in self.children:
                child.layout()
            
            # 높이 계산은 하위 child 다 계산하고 나서
            self.height = sum([child.height for child in self.children])
        else:
            self.cursor_x = 0
            self.cursor_y = 0
            self.size = 12
            self.weight = "normal"
            self.style = "roman"

            self.line = []
            self.recurse(self.node)
            self.flush()
            # 높이 계산은 flush 로 계산 하고 나서
            self.height = self.cursor_y

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
        if self.cursor_x + w > self.width:
            self.flush()
        
        # 단어를 현재 줄에 추가
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for _, _, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        for rel_x, word, font in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))
        
        max_descent = max(metric["descent"] for metric in metrics)
        self.cursor_y = baseline + 1.25 * max_descent

        self.cursor_x = 0
        self.line = []

    def paint(self):
        cmds = []

        # 텍스트 이전에 와야함
        # 안 그러면 텍스트 덮음
        if isinstance(self.node, Element) and self.node.tag == "pre":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, "blue")
            cmds.append(rect)
            
        if self.layout_mode() == "inline":
            for x, y, word, font in self.display_list:
                cmds.append(DrawText(x, y, word, font))

        return cmds

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)