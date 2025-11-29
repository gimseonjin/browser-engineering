import skia
from .geometry import Rect
from .color_utils import parse_color


class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.rect = Rect(x1, y1, x1 + font.measure(text), y1 + font.metrics("linespace"))
        self.text = text
        self.font = font
        self.color = color

    def execute(self, scroll, canvas):
        """Skia Canvas에 텍스트 렌더링"""
        paint = skia.Paint()
        paint.setColor(parse_color(self.color))
        paint.setAntiAlias(True)

        # Skia drawString은 baseline 기준이므로 ascent 더함
        baseline_y = self.rect.top - scroll + self.font.metrics("ascent")

        canvas.drawString(
            self.text,
            self.rect.left,
            baseline_y,
            self.font.skia_font,
            paint,
        )
