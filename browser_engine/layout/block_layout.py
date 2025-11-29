from ..dom.text import Text
from ..dom.element import Element
from ..rendering.font import get_font
from ..rendering import DrawRect, DrawText
from ..rendering.geometry import Rect
from .line_layout import LineLayout
from .text_layout import TextLayout
from .input_layout import InputLayout, INPUT_WIDTH_PX


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
        if temp_input.x + INPUT_WIDTH_PX > line.x + line.width:
            self.new_line()
            line = self.children[-1]
            previous_word = None
        
        # 실제 InputLayout 생성 및 추가
        input = InputLayout(node, line, previous_word)
        line.children.append(input)