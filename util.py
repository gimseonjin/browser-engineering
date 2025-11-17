from constants import HSTEP, VSTEP

def lex(body):
    text = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            if c == "&lt;":
                c = "<"
            elif c == "&gt;":
                c = ">"
            text += c
    return text

def layout(text, width):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP

    for c in text:
        display_list.append((cursor_x, cursor_y, c))

        cursor_x += HSTEP

        if cursor_x > width - HSTEP:
            cursor_y += VSTEP
            cursor_x = HSTEP

        if c == "\n":
            cursor_y += VSTEP * 2
            cursor_x = HSTEP

    return display_list