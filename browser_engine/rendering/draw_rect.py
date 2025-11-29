import skia
from .geometry import Rect
from .color_utils import parse_color


class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.rect = Rect(x1, y1, x2, y2)
        self.color = color

    def execute(self, scroll, canvas):
        """Skia Canvas에 채워진 사각형 렌더링"""
        if self.color == "transparent":
            return

        paint = skia.Paint()
        paint.setColor(parse_color(self.color))
        paint.setStyle(skia.Paint.kFill_Style)

        rect = skia.Rect(
            self.rect.left,
            self.rect.top - scroll,
            self.rect.right,
            self.rect.bottom - scroll,
        )
        canvas.drawRect(rect, paint)
