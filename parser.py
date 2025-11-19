from typing import List
from layout import Element, Text
from selector import DescendantSelector, TagSelector
from url import URLFactory

INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black"
}

class HTMLParser:
    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr,"
    ]
    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "sytle", "script",
    ]

    def __init__(self, body):
        self.body = body
        self.unfinished: List[Text] = []
    
    def parse(self):
        text = ""
        in_tag = False
        for c in self.body:
            if c == "<":
                in_tag = True
                if text: self.add_text(text)
                text = ""
            elif c == ">":
                in_tag = False
                self.add_tag(text)
                text = ""
            else:
                text += c
        if not in_tag and text:
            self.add_text(text)
        return self.finish()
    
    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]

            if open_tags == [] and tag != "html":
                self.add_tag("html")

            elif open_tags == ["html"] \
                and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            
            elif open_tags == ["html", "head"] and \
                tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            
            else:
                break

    def add_text(self, text: str):
        if text.isspace(): return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag: str):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"): return
        
        self.implicit_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)

        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)

        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def finish(self):
        if not self.unfinished:
            self.implicit_tags(None)

        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()

    def get_attributes(self, text:str):
        parts = text.split(None, 1)  # 태그와 나머지를 분리
        tag = parts[0].casefold() if parts else ""
        attributes = {}
        
        if len(parts) > 1:
            rest = parts[1]
            i = 0
            while i < len(rest):
                # 공백 건너뛰기
                while i < len(rest) and rest[i].isspace():
                    i += 1
                if i >= len(rest):
                    break
                
                # 속성 이름 찾기
                key_start = i
                while i < len(rest) and rest[i] not in ["=", " ", "\t", "\n"]:
                    i += 1
                key = rest[key_start:i]
                
                if not key:
                    break
                
                # 공백 건너뛰기
                while i < len(rest) and rest[i].isspace():
                    i += 1
                
                if i >= len(rest) or rest[i] != "=":
                    attributes[key.casefold()] = ""
                    continue
                
                i += 1  # '=' 건너뛰기
                
                # 공백 건너뛰기
                while i < len(rest) and rest[i].isspace():
                    i += 1
                
                if i >= len(rest):
                    attributes[key.casefold()] = ""
                    break
                
                # 값 파싱 (따옴표 처리)
                if rest[i] in ["'", "\""]:
                    quote = rest[i]
                    i += 1
                    value_start = i
                    while i < len(rest) and rest[i] != quote:
                        i += 1
                    value = rest[value_start:i]
                    if i < len(rest):
                        i += 1  # 닫는 따옴표 건너뛰기
                else:
                    value_start = i
                    while i < len(rest) and rest[i] not in [" ", "\t", "\n"]:
                        i += 1
                    value = rest[value_start:i]
                
                attributes[key.casefold()] = value

        return tag, attributes

class CSSParser:
    def __init__(self, s):
        self.s: str = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception("Parsing error")
        return self.s[start:self.i]

    def literal(self, literal):
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception("Parsing error")
        self.i += 1
    
    def pair(self):
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.casefold(), val

    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop.casefold()] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs
    
    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None

    def selector(self):
        out = TagSelector(self.word().casefold())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            tag = self.word()
            descendant = TagSelector(tag.casefold())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out

    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except Exception:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules


def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)

def style(node, rules):
    node.style = {}

    for selector, body in rules:
        if not selector.matches(node): continue
        for property, value in body.items():
            node.style[property] = value

    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items():
            node.style[property] = value

    for property, default_value in INHERITED_PROPERTIES.items():
        if property not in node.style:  # 이미 설정되지 않은 속성만 상속
            if node.parent:
                node.style[property] = node.parent.style[property]
            else:
                node.style[property] = default_value

    if "font-size" in node.style:
        font_size = node.style["font-size"]
        if font_size.endswith("%"):
            if node.parent:
                parent_font_size = node.parent.style["font-size"]
            else:
                parent_font_size = INHERITED_PROPERTIES["font-size"]
            node_pct = float(font_size[:-1]) / 100
            parent_px = float(parent_font_size[:-2])
            node.style["font-size"] = str(node_pct * parent_px) + "px"
        elif font_size.endswith("em"):
            if node.parent:
                parent_font_size = node.parent.style["font-size"]
            else:
                parent_font_size = INHERITED_PROPERTIES["font-size"]
            node_em = float(font_size[:-2])
            parent_px = float(parent_font_size[:-2])
            node.style["font-size"] = str(node_em * parent_px) + "px"

    for child in node.children:
        style(child, rules)
    
def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

if __name__ == "__main__":
    import sys
    url = URLFactory.parse(sys.argv[1])
    [_, _, body] = url.request()
    nodes = HTMLParser(body).parse()
    print_tree(nodes)