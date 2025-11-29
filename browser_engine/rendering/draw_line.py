import skia
from .geometry import Rect
from .color_utils import parse_color


class DrawLine:
    def __init__(self, x1, y1, x2, y2, color, thickness):
        self.rect = Rect(x1, y1, x2, y2)
        self.color = color
        self.thickness = thickness

    def execute(self, scroll, canvas):
        """Skia Canvas에 선 렌더링"""
        paint = skia.Paint()
        paint.setColor(parse_color(self.color))
        paint.setStrokeWidth(self.thickness)
        paint.setStyle(skia.Paint.kStroke_Style)
        paint.setAntiAlias(True)

        canvas.drawLine(
            self.rect.left,
            self.rect.top - scroll,
            self.rect.right,
            self.rect.bottom - scroll,
            paint,
        )
