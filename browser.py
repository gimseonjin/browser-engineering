import tkinter
import sys
from turtle import width

from parser import HTMLParser
from url import URLFactory
from constants import SCROLL_STEP, VSTEP, HSTEP
from layout import Layout

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        
        # 메인 컨테이너 Frame 생성
        self.frame = tkinter.Frame(self.window)
        self.frame.pack(fill="both", expand=True)
        
        # Canvas 생성
        self.canvas = tkinter.Canvas(self.frame)
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Scrollbar 생성
        self.scrollbar = tkinter.Scrollbar(
            self.frame, 
            orient="vertical", 
            command=self.on_scrollbar,
            width=15,
            troughcolor="lightgray",
            bg="gray",
            activebackground="darkgray"
        )
        self.scrollbar.pack(side="right", fill="y")
        
        self.scroll = 0
        self.width = 800
        self.height = 600
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scollup)
        self.canvas.bind("<Configure>", self.on_resize)

    def get_max_y(self):
        if not hasattr(self, 'display_list') or not self.display_list:
            return 0
        return max(y for _, y, _, _ in self.display_list) + VSTEP
    
    def update_scrollbar(self):
        if not hasattr(self, 'display_list'):
            return
        
        max_y = self.get_max_y()
        if max_y <= self.height:
            # 스크롤할 내용이 없으면 스크롤바를 전체로 설정
            self.scrollbar.set(0.0, 1.0)
            return
        
        # 스크롤 가능한 최대 높이
        max_scroll = max_y - self.height
        
        # 현재 스크롤 위치를 0.0~1.0 사이의 값으로 변환
        top = self.scroll / max_scroll if max_scroll > 0 else 0.0
        
        # thumb의 크기 (화면 높이 / 전체 높이)
        thumb_size = self.height / max_y
        
        # bottom 위치
        bottom = top + thumb_size
        
        # 범위 체크
        if bottom > 1.0:
            bottom = 1.0
            top = 1.0 - thumb_size
        
        self.scrollbar.set(top, bottom)
    
    def draw(self):
        self.canvas.delete("all")
        if not hasattr(self, 'display_list'):
            return
        for x, y, c, font in self.display_list:
            if y > self.scroll + self.height: continue
            if y + VSTEP < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=c, anchor="nw", font=font)
        self.update_scrollbar()

    def scrolldown(self, e):
        print(e)
        max_y = self.get_max_y()
        max_scroll = max(0, max_y - self.height)
        self.scroll = min(self.scroll + SCROLL_STEP, max_scroll)
        self.draw()

    def scollup(self, e):
        if self.scroll <= 0:
            return
        self.scroll = max(0, self.scroll - SCROLL_STEP)
        self.draw()

    def load(self, url:str, max_redirects=10):
        if max_redirects <= 0:
            raise Exception("Too many redirects")

        try:
            url_obj = URLFactory.parse(url)
            status, headers, body = url_obj.request()
            nodes = HTMLParser(body).parse()
        except (ValueError, Exception) as e:
            # URL이 잘못된 경우 about:blank 로드
            url_obj = URLFactory.parse("about:blank")
            status, headers, body = url_obj.request()
            nodes = HTMLParser(body).parse()
        
        if 300 <= status < 400:
            location = headers.get("location")
            if location:
                return self.load(location, max_redirects - 1)
            else:
                raise Exception("Redirect without Location header")
        
        self.token = nodes
        self.display_list = Layout(self.token, self.width).display_list
        self.draw()
    
    def on_resize(self, e):
        new_width = e.width
        new_height = e.height
        
        if new_width != self.width or new_height != self.height:
            self.width = new_width
            self.height = new_height
            self.display_list = Layout(self.token, self.width).display_list
            self.draw()
    
    def on_scrollbar(self, *args):
        if not args:
            return
        
        command = args[0]
        
        if command == "moveto":
            # moveto: 스크롤바를 특정 위치로 이동
            if len(args) > 1:
                position = float(args[1])
                # 0.0~1.0 범위로 제한
                position = max(0.0, min(1.0, position))
                max_y = self.get_max_y()
                max_scroll = max(0, max_y - self.height)
                self.scroll = position * max_scroll
                self.draw()
        
        elif command == "scroll":
            # scroll: units 또는 pages 단위로 스크롤
            if len(args) >= 3:
                units = int(args[1])
                unit_type = args[2]
                max_y = self.get_max_y()
                max_scroll = max(0, max_y - self.height)
                
                if unit_type == "units":
                    self.scroll = max(0, min(self.scroll + units * SCROLL_STEP, max_scroll))
                elif unit_type == "pages":
                    self.scroll = max(0, min(self.scroll + units * self.height, max_scroll))
                
                self.draw()

if __name__ == "__main__":
    import sys
    browser = Browser()
    browser.load(sys.argv[1])
    browser.window.mainloop()