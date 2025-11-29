from typing import List
from .element import Element
from .text import Text


class HTMLParser:
    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"
    ]
    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
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