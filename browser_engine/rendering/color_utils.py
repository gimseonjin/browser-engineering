import skia

COLOR_MAP = {
    "black": skia.ColorBLACK,
    "white": skia.ColorWHITE,
    "red": skia.ColorRED,
    "green": skia.ColorGREEN,
    "blue": skia.ColorBLUE,
    "yellow": skia.ColorYELLOW,
    "cyan": skia.ColorCYAN,
    "magenta": skia.ColorMAGENTA,
    "gray": skia.Color(128, 128, 128, 255),
    "grey": skia.Color(128, 128, 128, 255),
    "lightgray": skia.Color(211, 211, 211, 255),
    "lightgrey": skia.Color(211, 211, 211, 255),
    "lightblue": skia.Color(173, 216, 230, 255),
    "darkgray": skia.Color(169, 169, 169, 255),
    "darkgrey": skia.Color(169, 169, 169, 255),
    "orange": skia.Color(255, 165, 0, 255),
    "purple": skia.Color(128, 0, 128, 255),
    "pink": skia.Color(255, 192, 203, 255),
    "brown": skia.Color(165, 42, 42, 255),
    "transparent": skia.Color(0, 0, 0, 0),
}


def parse_color(color_str):
    """CSS 색상 문자열을 Skia Color로 변환"""
    if color_str is None:
        return skia.ColorBLACK

    color_str = color_str.lower().strip()

    # Named colors
    if color_str in COLOR_MAP:
        return COLOR_MAP[color_str]

    # #RRGGBB or #RGB format
    if color_str.startswith("#"):
        hex_color = color_str[1:]
        if len(hex_color) == 3:
            # #RGB -> #RRGGBB
            hex_color = hex_color[0] * 2 + hex_color[1] * 2 + hex_color[2] * 2
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return skia.Color(r, g, b, 255)
        elif len(hex_color) == 8:
            # #RRGGBBAA
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            a = int(hex_color[6:8], 16)
            return skia.Color(r, g, b, a)

    # rgb(r, g, b) format
    if color_str.startswith("rgb(") and color_str.endswith(")"):
        values = color_str[4:-1].split(",")
        if len(values) == 3:
            r = int(values[0].strip())
            g = int(values[1].strip())
            b = int(values[2].strip())
            return skia.Color(r, g, b, 255)

    # rgba(r, g, b, a) format
    if color_str.startswith("rgba(") and color_str.endswith(")"):
        values = color_str[5:-1].split(",")
        if len(values) == 4:
            r = int(values[0].strip())
            g = int(values[1].strip())
            b = int(values[2].strip())
            a = int(float(values[3].strip()) * 255)
            return skia.Color(r, g, b, a)

    # Default to black
    return skia.ColorBLACK
