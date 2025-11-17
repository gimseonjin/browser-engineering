import tkinter
import tkinter.font as tkFont

FONTS = {}

def get_font(size, weight, style):
    key = (size ,weight, style)
    if key not in FONTS:
        font = tkFont.Font(
            size=size,
            weight=weight,
            slant=style
        )
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]