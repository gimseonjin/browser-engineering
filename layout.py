from constants import HSTEP, VSTEP, WIDTH
from font import get_font


class Rect:
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
    
    def containsPoint(self, x, y):
        return x >= self.left and x < self.right \
            and y >= self.top and y < self.bottom


class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent
        self.is_focus = False
    
    def __repr__(self) -> str:
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent
        self.is_focus = False

    def __repr__(self) -> str:
        return f"<{self.tag}>"

class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.rect = Rect(x1, y1, x1 + font.measure(text), y1 + font.metrics("linespace"))
        self.text = text
        self.font = font
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.rect.left, self.rect.top - scroll,
            text=self.text,
            font=self.font,
            fill=self.color,
            anchor="nw"
        )

class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.rect = Rect(x1, y1, x2, y2)
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.rect.left, self.rect.top - scroll,
            self.rect.right, self.rect.bottom - scroll,
            width = 0,
            fill=self.color
        )

class DrawOutline:
    def __init__(self, rect, color, thickness):
        self.rect = rect
        self.color = color
        self.thickness = thickness
    
    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.rect.left, self.rect.top - scroll,
            self.rect.right, self.rect.bottom - scroll,
            width = self.thickness,
            outline = self.color
        )

class DrawLine:
    def __init__(self, x1, y1, x2, y2, color, thickness):
        self.rect = Rect(x1, y1, x2, y2)
        self.color = color
        self.thickness = thickness

    def execute(self, scroll, canvas):
        canvas.create_line(
            self.rect.left, self.rect.top - scroll,
            self.rect.right, self.rect.bottom - scroll,
            width = self.thickness,
            fill = self.color
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
    
    def should_paint(self):
        return isinstance(self.node, Text) or \
            (self.node.tag == "input" or self.node.tag == "button")


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

        elif self.node.children or self.node.tag == "input" or self.node.tag == "button":
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
            self.new_line()
            self.recurse(self.node)
            # 높이 계산은 flush 로 계산 하고 나서
            for child in self.children:
                child.layout()
            self.height = sum([child.height for child in self.children])

    def recurse(self, node):
        if isinstance(node, Text):
            for word in node.text.split():
                self.word(node, word)
        else:
            if node.tag == "br":
                self.new_line()
            elif node.tag == "input" or node.tag == "button":
                self.input(node)
            else:
                for child in node.children:
                    self.recurse(child)

    def word(self, node, word):
        line = self.children[-1]
        previouse_word = line.children[-1] if line.children else None
        
        # 이전 단어가 있으면 먼저 layout 호출하여 위치 계산
        if previouse_word and (not hasattr(previouse_word, 'x') or previouse_word.x is None):
            previouse_word.layout()
        
        # 단어의 폰트 정보 가져오기
        color = node.style["color"]
        weight = node.style["font-weight"]
        style_val = node.style["font-style"]
        if style_val == "normal":
            style_val = "roman"
        elif style_val == "oblique":
            style_val = "italic"
        size = int(float(node.style["font-size"][:-2]) * .75)
        font = get_font(size, weight, style_val)
        
        word_width = font.measure(word)
        space_width = font.measure(" ")
        
        # 현재 줄에서 단어가 들어갈 위치 계산
        if previouse_word:
            # 이전 단어가 있으면 이전 단어의 끝 위치 + 공백 + 단어 너비
            total_width = previouse_word.x + previouse_word.width + space_width + word_width
        else:
            # 이전 단어가 없으면 줄 시작 위치 + 단어 너비
            total_width = line.x + word_width
        
        # 줄을 넘어가면 새 줄 생성
        if total_width > line.x + line.width:
            self.new_line()
            line = self.children[-1]
            previouse_word = None
        
        # 단어 추가
        text = TextLayout(node, word, line, previouse_word)
        line.children.append(text)

    def new_line(self):
        self.cursor_x = 0
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)

    def self_rect(self):
        return Rect(self.x, self.y, self.x + self.width, self.y + self.height)

    def paint(self):
        cmds = []

        # 텍스트 이전에 와야함
        # 안 그러면 텍스트 덮음
        bgcolor = self.node.style.get("background-color",
                                        "transparent")
        if bgcolor != "transparent":
            rect = DrawRect(self.x, self.y, self.x + self.width, self.y + self.height, bgcolor)
            cmds.append(rect)
            
        if self.layout_mode() == "inline":
            for x, y, word, font, color in self.display_list:
                cmds.append(DrawText(x, y, word, font, color))

        return cmds

    def should_paint(self):
        return isinstance(self.node, Text) or \
            (self.node.tag != "input" and self.node.tag != "button")

    def input(self, node):
        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        
        # 이전 요소가 있으면 먼저 layout 호출하여 위치 계산
        if previous_word and (not hasattr(previous_word, 'x') or previous_word.x is None):
            previous_word.layout()
        
        # 임시로 InputLayout 생성하여 줄바꿈 필요 여부 확인
        temp_input = InputLayout(node, line, previous_word)
        temp_input.layout()
        
        # 줄을 넘어가면 새 줄 생성
        if temp_input.x + INPUT_WIDHT_PX > line.x + line.width:
            self.new_line()
            line = self.children[-1]
            previous_word = None
        
        # 실제 InputLayout 생성 및 추가
        input = InputLayout(node, line, previous_word)
        line.children.append(input)

class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.width = self.parent.width
        self.x = self.parent.x
        self.y = None
        self.height = None
    
    def layout(self):
        # y 위치 계산 (이전 줄이 있으면 이전 줄의 layout이 먼저 호출되어야 함)
        if self.previous:
            # 이전 줄이 아직 layout되지 않았다면 먼저 layout 호출
            if self.previous.height is None:
                self.previous.layout()
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        
        for word in self.children:
            word.layout()
        
        # 빈 줄인 경우 처리
        if not self.children:
            # 기본 폰트를 사용하여 최소 높이 설정
            from font import get_font
            default_font = get_font(12, "normal", "roman")
            self.height = 1.25 * default_font.metrics("linespace")
            return
        
        max_ascent = max(word.font.metrics("ascent") for word in self.children)
        baseline = self.y + 1.25 * max_ascent

        for word in self.children:
            word.y = baseline - word.font.metrics("ascent")
            
        max_descent = max(word.font.metrics("descent") for word in self.children)
        self.height =1.25 * (max_ascent + max_descent)

    def paint(self):
        return []
    
    def should_paint(self):
        return False

class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous

    def layout(self):
        color = self.node.style["color"]
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal":
            style = "roman"
        elif style == "oblique":
            style = "italic"
        size = int(float(self.node.style["font-size"][:-2]) * .75)
        self.font = get_font(size, weight, style)

        self.width = self.font.measure(self.word)

        if self.previous:
            space = self.font.measure(" ")
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

        self.height = self.font.metrics("linespace")
        
    def paint(self):
        color = self.node.style["color"]
        return [DrawText(self.x, self.y, self.word, self.font, color)]
    
    def should_paint(self):
        return True

INPUT_WIDHT_PX = 200

class InputLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.children = []
        self.parent = parent
        self.previous = previous
        self.width = INPUT_WIDHT_PX

    def layout(self):
        color = self.node.style["color"]
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal":
            style = "roman"
        elif style == "oblique":
            style = "italic"
        size = int(float(self.node.style["font-size"][:-2]) * .75)
        self.font = get_font(size, weight, style)

        self.width = INPUT_WIDHT_PX

        # TextLayout처럼 이전 요소의 위치를 고려한 x 위치 계산
        if self.previous:
            space = self.font.measure(" ")
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

        self.height = self.font.metrics("linespace")
        
    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color",
                                        "transparent")
        if bgcolor != "transparent":
            rect = DrawRect(self.x, self.y, self.x + self.width, self.y + self.height, bgcolor)
            cmds.append(rect)

        if self.node.tag == "input":
            text = self.node.attributes.get("value", "")
        elif self.node.tag == "button":
            if len(self.node.children) == 1 and \
                isinstance(self.node.children[0], Text):
                text = self.node.children[0].text
            else:
                print("Ignoring HTML contents inside button")
                text = ""

        if self.node.is_focus:
            cx = self.x + self.font.measure(text)
            cmds.append(DrawLine(
                cx, self.y, cx, self.y + self.height, "black", 1
            ))
            
        color = self.node.style["color"]
        cmds.append(DrawText(self.x, self.y, text, self.font, color))

        return cmds
    
    def should_paint(self):
        return True

def paint_tree(layout_object, display_list):
    if layout_object.should_paint():
        display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)