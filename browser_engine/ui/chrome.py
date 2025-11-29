from ..rendering import DrawLine, DrawOutline, DrawRect, DrawText, Rect, get_font
from ..core.constants import WIDTH


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
        # browser의 너비 가져오기
        width = self.browser.width

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
            # active_commit에서 URL 가져오기 (Browser Thread에서 안전하게 접근)
            url = ""
            if self.browser.active_commit and self.browser.active_commit.url:
                url = str(self.browser.active_commit.url)
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
            return

        if (self.back_rect.containsPoint(e.x, e.y)):
            # MainThread로 GO_BACK 이벤트 전달
            self.browser.handle_go_back()
            return

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
            return True
        return False

    def backspace(self):
        if self.focus == "address bar" and len(self.address_bar) > 0:
            self.address_bar = self.address_bar[:-1]
            return True
        return False

    def enter(self):
        if self.focus == "address bar":
            self.focus = None
            # MainThread로 LOAD 이벤트 전달
            self.browser.handle_load(self.address_bar)

    def blur(self):
        self.focus = None