class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.width = self.parent.width
        self.x = self.parent.x
        self.y = None
        self.height = None
    
    def layout(self):
        # y 위치 계산 (이전 줄이 있으면 이전 줄의 layout이 먼저 호출되어야 함)
        if self.previous:
            # 이전 줄이 아직 layout되지 않았다면 먼저 layout 호출
            if self.previous.height is None:
                self.previous.layout()
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        
        for word in self.children:
            word.layout()
        
        # 빈 줄인 경우 처리
        if not self.children:
            # 기본 폰트를 사용하여 최소 높이 설정
            from ..rendering.font import get_font
            default_font = get_font(12, "normal", "roman")
            self.height = 1.25 * default_font.metrics("linespace")
            return
        
        max_ascent = max(word.font.metrics("ascent") for word in self.children)
        baseline = self.y + 1.25 * max_ascent

        for word in self.children:
            word.y = baseline - word.font.metrics("ascent")
            
        max_descent = max(word.font.metrics("descent") for word in self.children)
        self.height =1.25 * (max_ascent + max_descent)

    def paint(self):
        return []
    
    def should_paint(self):
        return False