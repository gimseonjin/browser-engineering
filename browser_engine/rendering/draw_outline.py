import skia
from .color_utils import parse_color


class DrawOutline:
    def __init__(self, rect, color, thickness):
        self.rect = rect
        self.color = color
        self.thickness = thickness

    def execute(self, scroll, canvas):
        """Skia Canvas에 테두리 사각형 렌더링"""
        paint = skia.Paint()
        paint.setColor(parse_color(self.color))
        paint.setStyle(skia.Paint.kStroke_Style)
        paint.setStrokeWidth(self.thickness)
        paint.setAntiAlias(True)

        rect = skia.Rect(
            self.rect.left,
            self.rect.top - scroll,
            self.rect.right,
            self.rect.bottom - scroll,
        )
        canvas.drawRect(rect, paint)
