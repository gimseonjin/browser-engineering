"""CSS Style Application"""
from ..dom.element import Element
from .css_parser import CSSParser

INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black"
}


def style(node, rules):
    """DOM 노드에 CSS 규칙을 적용"""
    node.style = {}

    for selector, body in rules:
        if not selector.matches(node):
            continue
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
