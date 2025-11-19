import tkinter
import sys

from parser import CSSParser, HTMLParser, style, tree_to_list
from selector import cascade_priority
from url import URLFactory
from constants import HEIGHT, SCROLL_STEP, VSTEP, HSTEP, WIDTH
from layout import BlockLayout, DocumentLayout, DrawLine, DrawOutline, DrawRect, DrawText, Element, Text, TextLayout, paint_tree, Rect
from font import get_font

DEFAULT_STYLE_SHEET = CSSParser(open("Browser.css").read()).parse()

class Chrome:
    def __init__(self, browser):
        self.browser = browser
        self.font = get_font(20, "normal", "roman")
        self.font_height = self.font.metrics("linespace")
        self.padding = 5
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2 * self.padding
        plus_width = self.font.measure("+") + 2 * self.padding
        self.newtab_rect = Rect(
            self.padding,
            self.padding,
            self.padding + plus_width,
            self.padding + self.font_height
        )
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + \
            self.font_height + 2 * self.padding
        self.bottom = self.urlbar_bottom

        back_width = self.font.measure("<") + 2 * self.padding
        self.back_rect = Rect(
            self.padding,
            self.urlbar_top + self.padding,
            self.padding + back_width,
            self.urlbar_bottom - self.padding
        )
        self.address_rect = Rect(
            self.back_rect.top + self.padding,
            self.urlbar_top + self.padding,
            WIDTH - self.padding,
            self.urlbar_bottom - self.padding
        )
        self.focus = None
        self.address_bar = ""
    
    def tab_ract(self, i):
        tabs_start = self.newtab_rect.right + self.padding
        tab_width = self.font.measure("Tab X") + 2 * self.padding
        return Rect(
            tabs_start + tab_width * i, 
            self.tabbar_top,
            tabs_start + tab_width * (i + 1),
            self.tabbar_bottom
        )

    def paint(self):
        cmds = []
        # canvas의 실제 너비 가져오기
        width = self.browser.canvas.winfo_width()

        cmds.append(DrawOutline(self.newtab_rect, "black", 1))
        cmds.append(DrawText(
            self.newtab_rect.left + self.padding, 
            self.newtab_rect.top, 
            "+", 
            self.font, 
            "black"
        ))
        cmds.append(DrawRect(
            0,
            0,
            width,
            self.bottom,
            "white"
        ))
        cmds.append(DrawLine(
            0, self.bottom, width, self.bottom, "black", 1
        ))

        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_ract(i)
            cmds.append(DrawLine(
                bounds.left, 
                0,
                bounds.left,
                bounds.bottom,
                "black",
                1
            ))
            cmds.append(DrawLine(
                bounds.left, 
                0,
                bounds.left,
                bounds.bottom,
                "black",
                1
            ))
            cmds.append(DrawText(
                bounds.left + self.padding, 
                bounds.top + self.padding,
                f"Tab {i}", 
                self.font, 
                "black"
            ))
            if tab == self.browser.active_tab:
                cmds.append(DrawLine(
                    0, bounds.bottom, bounds.left, bounds.bottom, "black", 1
                ))
                cmds.append(DrawLine(
                    bounds.right, bounds.bottom, width, bounds.bottom, "black", 1
                ))
        cmds.append(DrawOutline(self.back_rect, "black", 1))
        cmds.append(DrawText(
            self.back_rect.left + self.padding,
            self.back_rect.top,
            "<",
            self.font,
            "black"
        ))

        cmds.append(DrawOutline(self.address_rect, "black", 1))
        if self.focus == "address bar":
            cmds.append(DrawText(
                self.address_rect.left + self.padding,
                self.address_rect.top,
                self.address_bar,
                self.font,
                "black"
            ))
            w = self.font.measure(self.address_bar)
            cmds.append(DrawLine(
                self.address_rect.left + self.padding + w,
                self.address_rect.top,
                self.address_rect.left + self.padding + w,
                self.address_rect.bottom,
                "red",
                1
            ))
        else:
            url = self.browser.active_tab.url
            cmds.append(DrawText(
                self.address_rect.left + self.padding,
                self.address_rect.top,
                url,
                self.font,
                "black"
            ))
        return cmds

    def click(self, e):
        if (self.newtab_rect.containsPoint(e.x, e.y)):
            self.browser.new_tab("about:blank")

        if (self.back_rect.containsPoint(e.x, e.y)):
            self.browser.active_tab.go_back()

        if (self.address_rect.containsPoint(e.x, e.y)):
            self.focus = "address bar"
            self.address_bar = ""
        else:
            for i, tab in enumerate(self.browser.tabs):
                bounds = self.tab_ract(i)
                if (bounds.left <= e.x < bounds.right
                    and bounds.top <= e.y < bounds.bottom):
                    self.browser.active_tab = tab
                    return

    def keypress(self, char):
        if self.focus == "address bar":
            self.address_bar += char

    def backspace(self):
        if self.focus == "address bar" and len(self.address_bar) > 0:
            self.address_bar = self.address_bar[:-1]

    def enter(self):
        if self.focus == "address bar":
            self.focus = None
            self.browser.active_tab.load(self.address_bar)

class Browser:
    def __init__(self):
        self.tabs = []
        self.active_tab: Tab = None

        self.window = tkinter.Tk()
        
        self.window.bind("<Down>", self.handle_down)
        self.window.bind("<Up>", self.handle_up)
        self.window.bind("<Button-1>", self.handle_click)
        self.window.bind("<Key>", self.handle_key)
        self.window.bind("<Return>", self.handle_return)
        
        # 메인 컨테이너 Frame 생성
        self.frame = tkinter.Frame(self.window)
        self.frame.pack(fill="both", expand=True)

        # Scrollbar 생성
        self.scrollbar = tkinter.Scrollbar(
            self.frame, 
            orient="vertical", 
            command=self.handle_scrollbar,
            width=15,
            troughcolor="lightgray",
            bg="gray",
            activebackground="darkgray"
        )
        self.scrollbar.pack(side="right", fill="y")
        
        # Canvas 생성
        self.canvas = tkinter.Canvas(self.frame, bg="white")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self.handle_resize)

        self.chrome = Chrome(self)

    def handle_down(self, e):
        if self.active_tab:
            self.active_tab.scrolldown()
            self.draw()
    
    def handle_up(self, e):
        if self.active_tab:
            self.active_tab.scollup()
            self.draw()
    
    def handle_click(self, e):
        # TODO: 차후 좌표만
        if e.y < self.chrome.bottom:
            self.chrome.click(e)
        else:
            e.y = e.y - self.chrome.bottom
            self.active_tab.click(e)
        self.draw()
    
    def handle_resize(self, e):
        if self.active_tab:
            self.active_tab.on_resize(e)
            self.draw()
    
    def handle_scrollbar(self, *args):
        if self.active_tab:
            self.active_tab.on_scrollbar(*args)
            self.draw()

    def draw(self):
        if not self.active_tab:
            return
        self.canvas.delete("all")
        self.active_tab.draw(self.canvas, self.chrome.bottom)
        self.update_scrollbar()
        for cmd in self.chrome.paint():
            cmd.execute(0, self.canvas)
    
    def update_scrollbar(self):
        if not self.active_tab or not hasattr(self.active_tab, 'display_list'):
            return
        
        document_height = self.active_tab.get_max_y()
        if document_height <= self.active_tab.height:
            # 스크롤할 내용이 없으면 스크롤바를 전체로 설정
            self.scrollbar.set(0.0, 1.0)
            return
        
        # 스크롤 가능한 최대 높이
        max_scroll = document_height - self.active_tab.height
        
        # 현재 스크롤 위치를 0.0~1.0 사이의 값으로 변환
        top = self.active_tab.scroll / max_scroll if max_scroll > 0 else 0.0
        
        # thumb의 크기 (화면 높이 / 전체 높이)
        thumb_size = self.active_tab.height / document_height
        
        # bottom 위치
        bottom = top + thumb_size
        
        # 범위 체크
        if bottom > 1.0:
            bottom = 1.0
            top = 1.0 - thumb_size
        
        self.scrollbar.set(top, bottom)

    def new_tab(self, url):
        new_tab = Tab(HEIGHT - self.chrome.bottom)
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.draw()

    def handle_key(self, e):
        if e.keysym == "BackSpace":
            self.chrome.backspace()
            self.draw()
            return
        if len(e.char) == 0: return
        if not (0x20 <= ord(e.char) < 0x7f): return
        self.chrome.keypress(e.char)
        self.draw()

    def handle_return(self, e):
        self.chrome.enter()
        self.draw()

class Tab:
    def __init__(self, tab_height):
        self.scroll = 0
        self.width = 800
        self.height = 600

        self.url = None
        self.tab_height = tab_height

        self.history = []

    def get_max_y(self):
        # 문서의 전체 높이 반환 (상단 여백 포함)
        return self.document.height + 2 * VSTEP - self.tab_height
    
    def draw(self, canvas, offset):
        for cmd in self.display_list:
            if cmd.rect.top > self.scroll + self.height: continue
            if cmd.rect.bottom < self.scroll: continue
            cmd.execute(self.scroll - offset, canvas)

    def scrolldown(self):
        document_height = self.get_max_y()
        max_scroll = max(0, document_height - self.height)
        self.scroll = min(self.scroll + SCROLL_STEP, max_scroll)

    def scollup(self):
        if self.scroll <= 0:
            return
        self.scroll = max(0, self.scroll - SCROLL_STEP)

    def load(self, url:str, max_redirects=10):
        self.history.append(url)
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
        
        self.url = url_obj
        self.nodes = nodes
        rules = DEFAULT_STYLE_SHEET.copy()
        style(nodes,sorted(rules, key=cascade_priority))

        links = [node.attributes for node in tree_to_list(self.nodes, [])
                if isinstance(node, Element)
                and node.tag == "link"
                and node.attributes.get("rel") == "stylesheet"
                and "href" in node.attributes]

        for link in links:
            style_url = URLFactory.resolve(url_obj, link)
            try:
                body = style_url.request()
            except:
                continue
            rules.extend(CSSParser(body).parse())
            
        self.document = DocumentLayout(self.nodes, self.width)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
    
    def on_resize(self, e):
        new_width = e.width
        new_height = e.height
        
        if new_width != self.width or new_height != self.height:
            self.width = new_width
            self.height = new_height

            self.document = DocumentLayout(self.nodes, self.width)
            self.document.layout()
            self.display_list = []
            paint_tree(self.document, self.display_list)
    
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
                document_height = self.get_max_y()
                max_scroll = max(0, document_height - self.height)
                self.scroll = position * max_scroll
        
        elif command == "scroll":
            # scroll: units 또는 pages 단위로 스크롤
            if len(args) >= 3:
                units = int(args[1])
                unit_type = args[2]
                document_height = self.get_max_y()
                max_scroll = max(0, document_height - self.height)
                
                if unit_type == "units":
                    self.scroll = max(0, min(self.scroll + units * SCROLL_STEP, max_scroll))
                elif unit_type == "pages":
                    self.scroll = max(0, min(self.scroll + units * self.height, max_scroll))

    def click(self, e):
        x, y = e.x, e.y
        y += self.scroll
        objs = [obj for obj in tree_to_list(self.document, []) 
                if obj.x <= x < obj.x + obj.width
                and obj.y <= y < obj.y + obj.height]

        if not objs:
            return
        
        elt = objs[-1].node

        while elt:
            if isinstance(elt, Text):
                pass

            elif elt.tag == "a" and "href" in elt.attributes:
                url = URLFactory.resolve_str(self.url, elt.attributes["href"])
                self.load(url)
            
            elt = elt.parent

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back_url = self.history[-1]
            self.load(back_url)

if __name__ == "__main__":
    import sys
    browser = Browser()
    browser.new_tab(sys.argv[1])
    browser.window.mainloop()