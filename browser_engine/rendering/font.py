import skia

FONTS = {}

WEIGHT_MAP = {
    "normal": skia.FontStyle.kNormal_Weight,
    "bold": skia.FontStyle.kBold_Weight,
}

STYLE_MAP = {
    "roman": skia.FontStyle.kUpright_Slant,
    "italic": skia.FontStyle.kItalic_Slant,
}


class SkiaFont:
    """Skia 폰트 래퍼 - 기존 Tkinter Font 인터페이스 유지"""

    def __init__(self, size, weight, style):
        font_style = skia.FontStyle(
            WEIGHT_MAP.get(weight, skia.FontStyle.kNormal_Weight),
            skia.FontStyle.kNormal_Width,
            STYLE_MAP.get(style, skia.FontStyle.kUpright_Slant),
        )
        self.typeface = skia.Typeface.MakeFromName(None, font_style)
        self.skia_font = skia.Font(self.typeface, size)
        self._size = size
        self._weight = weight
        self._style = style

    def measure(self, text):
        """텍스트 너비 반환 (픽셀)"""
        return self.skia_font.measureText(text)

    def metrics(self, name):
        """폰트 메트릭 반환"""
        fm = self.skia_font.getMetrics()
        if name == "ascent":
            return abs(fm.fAscent)
        elif name == "descent":
            return fm.fDescent
        elif name == "linespace":
            return abs(fm.fAscent) + fm.fDescent + fm.fLeading
        else:
            raise ValueError(f"Unknown metric: {name}")


def get_font(size, weight, style):
    """폰트 캐시에서 폰트 반환 (없으면 생성)"""
    key = (size, weight, style)
    if key not in FONTS:
        FONTS[key] = SkiaFont(size, weight, style)
    return FONTS[key]
