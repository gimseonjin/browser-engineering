"""
Tab - Browser와 Frame 사이의 중재자

Tab은 다음을 담당합니다:
- Browser와 Frame 사이의 이벤트 처리
- 프레임 간의 통신 중계
- 렌더링 시작 및 탭 내 모든 프레임의 display list 관리
- 브라우저 스레드에 커밋
"""
import urllib
from typing import TYPE_CHECKING, Optional, List

from ..dom import tree_to_list, Element, Text
from ..networking import URLFactory
from ..common.constants import HEIGHT, SCROLL_STEP, VSTEP, WIDTH
from ..threads.task import Task, TaskRunner
from ..profiling import MeasureTime
from .frame import Frame

if TYPE_CHECKING:
    from ..threads.main_thread import MainThread


class Tab:
    """
    탭을 관리하는 클래스

    책임:
    - Browser와 Frame 사이의 이벤트 처리
    - 프레임 간 통신 중계
    - 렌더링 시작 및 display list 관리
    - 브라우저 스레드에 커밋
    """
    def __init__(self, tab_height, default_style_sheet=None):
        self.task_runner = TaskRunner(self)
        self.scroll = 0
        self.width = WIDTH
        self.height = HEIGHT - tab_height

        self.tab_height = tab_height
        self.default_style_sheet = default_style_sheet or []

        self.history = []
        self.focus = None
        self.needs_render = False

        # MainThread 연결 (Browser에서 설정)
        self.main_thread: Optional["MainThread"] = None
        self.browser = None

        # 루트 프레임 (메인 문서)
        self.root_frame: Optional[Frame] = None
        self.frames: List[Frame] = []  # 모든 프레임 목록 (iframe 포함)

        # 합성된 display_list
        self.display_list = []

    def set_needs_render(self):
        """렌더링 필요 플래그 설정"""
        self.needs_render = True

    @property
    def url(self):
        """현재 탭의 URL (루트 프레임의 URL)"""
        return self.root_frame.url if self.root_frame else None

    @property
    def nodes(self):
        """루트 프레임의 DOM 노드"""
        return self.root_frame.nodes if self.root_frame else None

    @property
    def document(self):
        """루트 프레임의 레이아웃 문서"""
        return self.root_frame.document if self.root_frame else None

    @property
    def csp(self):
        """루트 프레임의 CSP"""
        return self.root_frame.csp if self.root_frame else None

    @property
    def js_context(self):
        """루트 프레임의 JavaScript 컨텍스트"""
        return self.root_frame.js_context if self.root_frame else None

    def get_max_y(self):
        """문서의 전체 높이 반환"""
        if self.root_frame and self.root_frame.document:
            return self.root_frame.document.height + 2 * VSTEP
        return 0

    def draw(self, canvas, offset):
        """모든 프레임의 display list를 화면에 그림"""
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

    def load(self, url: str, payload=None, max_redirects=10):
        """페이지 로드 - 새로운 Frame을 생성하고 로드"""
        with MeasureTime("tab_load", "load"):
            self.history.append(url)

            # 새 루트 프레임 생성
            self.root_frame = Frame(self)
            self.frames = [self.root_frame]

            # 프레임에서 실제 로드 수행
            self.root_frame.load(url, payload, max_redirects)

            # display list 합성
            self._composite_display_list()

    def _composite_display_list(self):
        """모든 프레임의 display list를 합성"""
        self.display_list = []
        for frame in self.frames:
            self.display_list.extend(frame.get_display_list())

    def render(self):
        """모든 프레임의 렌더링 수행"""
        for frame in self.frames:
            if frame.needs_render:
                frame.render()
        self._composite_display_list()
        self.needs_render = False

    def on_resize(self, e):
        pass

    def on_scrollbar(self, *args):
        if not args:
            return

        command = args[0]

        if command == "moveto":
            if len(args) > 1:
                position = float(args[1])
                position = max(0.0, min(1.0, position))
                document_height = self.get_max_y()
                max_scroll = max(0, document_height - self.height)
                self.scroll = position * max_scroll

        elif command == "scroll":
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
        """클릭 이벤트 처리 - Frame에 위임"""
        self.focus = None
        x, y = e.x, e.y
        y += self.scroll

        if not self.root_frame or not self.root_frame.document:
            return

        objs = [obj for obj in tree_to_list(self.root_frame.document, [])
                if obj.x <= x < obj.x + obj.width
                and obj.y <= y < obj.y + obj.height]

        if not objs:
            return

        elt = objs[-1].node

        while elt:
            if isinstance(elt, Text):
                pass

            elif elt.tag == "a" and "href" in elt.attributes:
                if self.root_frame.dispatch_event("click", elt): return
                url = URLFactory.resolve_str(self.root_frame.url, elt.attributes["href"])
                self.load(url)

            elif elt.tag == "input":
                if self.root_frame.dispatch_event("click", elt): return
                elt.attributes["value"] = ""
                if self.focus:
                    self.focus.is_focus = False
                self.focus = elt
                elt.is_focus = True
                self.set_needs_render()
                return

            elif elt.tag == "button":
                if self.root_frame.dispatch_event("click", elt): return
                while elt:
                    if elt.tag == "form" and "action" in elt.attributes:
                        return self.submit_form(elt)
                    elt = elt.parent

            elt = elt.parent

    def submit_form(self, elt):
        """폼 제출 처리"""
        if self.root_frame.dispatch_event("submit", elt): return
        inputs = [node for node in tree_to_list(elt, [])
                  if isinstance(node, Element)
                  and node.tag == "input"
                  and "name" in node.attributes
        ]

        body = ""
        for input in inputs:
            name = input.attributes["name"]
            value = input.attributes.get("value", "")
            name = urllib.parse.quote(name)
            value = urllib.parse.quote(value)
            body += f"{name}={value}&"
        body = body[:-1]
        url = URLFactory.resolve_str(self.root_frame.url, elt.attributes["action"])
        self.load(url, body)

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back_url = self.history[-1]
            self.load(back_url)

    def keypress(self, char):
        """키 입력 처리"""
        if self.focus:
            if self.root_frame.dispatch_event("keydown", self.focus): return
            self.focus.attributes["value"] += char
            self.set_needs_render()

    def backspace(self):
        if self.focus and "value" in self.focus.attributes:
            current_value = self.focus.attributes["value"]
            if len(current_value) > 0:
                self.focus.attributes["value"] = current_value[:-1]
                self.set_needs_render()

    def commit_to_browser(self):
        """렌더링 결과를 브라우저 스레드에 커밋"""
        if self.browser:
            # 브라우저에 렌더링 완료 알림
            self.browser.on_tab_commit(self)

    def add_frame(self, frame: Frame):
        """새 프레임 추가 (iframe 등)"""
        self.frames.append(frame)

    def remove_frame(self, frame: Frame):
        """프레임 제거"""
        if frame in self.frames:
            self.frames.remove(frame)
