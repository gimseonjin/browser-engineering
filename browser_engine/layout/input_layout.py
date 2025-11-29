from ..rendering.font import get_font
from ..rendering import DrawRect, DrawText, DrawLine
from ..dom.text import Text

INPUT_WIDTH_PX = 200


class InputLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.children = []
        self.parent = parent
        self.previous = previous
        self.width = INPUT_WIDTH_PX

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

        self.width = INPUT_WIDTH_PX

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