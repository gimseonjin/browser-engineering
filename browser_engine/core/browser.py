import ctypes
import sdl2
import sdl2.ext
from queue import Queue, Empty
from typing import Dict, Optional

from ..css import CSSParser
from ..common.constants import HEIGHT, SCROLL_STEP, WIDTH
from ..ui.chrome import Chrome
from ..content.tab import Tab
from ..threads.main_thread import MainThread, Event, EventType
from ..threads.commit_data import CommitData
from ..threads.compositor_thread import CompositorThread, CompositorData
from ..profiling import Tracer, set_thread_name
from ..networking import shutdown_network_thread

DEFAULT_STYLE_SHEET = CSSParser(open("Browser.css").read()).parse()


class Browser:
    """SDL 브라우저 - 이벤트 처리 전담

    Browser Thread에서 실행:
    - SDL 이벤트 루프 (유저 입력)
    - Tab들과의 통신 관리
    - CompositorThread로 렌더링 위임
    """

    def __init__(self):
        self.tabs: list[Tab] = []
        self.active_tab: Optional[Tab] = None
        self.focus = None

        # Tab -> Browser 커밋 큐 (모든 탭이 공유)
        self.commit_queue: Queue[CommitData] = Queue()

        # Tab별 MainThread 관리
        self.main_threads: Dict[int, MainThread] = {}

        # 현재 활성 탭의 커밋 데이터 (Browser Thread에서 사용)
        self.active_commit: Optional[CommitData] = None

        # SDL 초기화
        sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)

        # 윈도우 생성
        self.window = sdl2.SDL_CreateWindow(
            b"Browser (GPU Accelerated)",
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            WIDTH,
            HEIGHT,
            sdl2.SDL_WINDOW_RESIZABLE,
        )

        # 하드웨어 가속 렌더러 생성
        self.renderer = sdl2.SDL_CreateRenderer(
            self.window, -1,
            sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC
        )

        self.width = WIDTH
        self.height = HEIGHT

        # Dirty flags (Compositor로 전달)
        self.chrome_needs_raster = True
        self.tab_needs_raster = True

        # Chrome UI
        self.chrome = Chrome(self)

        # Compositor Thread 생성 및 시작
        self.compositor = CompositorThread(self.renderer, WIDTH, HEIGHT)
        self.compositor.start()

        # 프로파일링: Browser Thread 이름 설정
        set_thread_name("BrowserThread")

        # 텍스트 입력 활성화
        sdl2.SDL_StartTextInput()

    def submit_to_compositor(self):
        """CompositorThread에 렌더링 데이터 전달"""
        data = CompositorData(
            # Tab 콘텐츠
            display_list=self.active_commit.display_list if self.active_commit else [],
            document_height=self.active_commit.document_height if self.active_commit else 0.0,
            scroll=self.active_commit.scroll if self.active_commit else 0.0,
            # Chrome UI
            chrome_commands=self.chrome.paint(),
            chrome_height=self.chrome.bottom,
            # 윈도우 크기
            width=self.width,
            height=self.height,
            # 플래그
            chrome_changed=self.chrome_needs_raster,
            tab_changed=self.tab_needs_raster,
            scroll_changed=False,
        )
        self.compositor.submit(data)
        self.chrome_needs_raster = False
        self.tab_needs_raster = False

    def set_needs_draw(self):
        """화면 다시 그리기 요청 - Compositor에 데이터 전달"""
        self.submit_to_compositor()

    # === 이벤트 핸들러 (Browser Thread) ===

    def _get_active_main_thread(self) -> Optional[MainThread]:
        """활성 탭의 MainThread 반환"""
        if self.active_tab:
            return self.main_threads.get(id(self.active_tab))
        return None

    def handle_go_back(self):
        """뒤로가기 - MainThread로 이벤트 전달"""
        main_thread = self._get_active_main_thread()
        if main_thread:
            main_thread.post_event(Event(EventType.GO_BACK))

    def handle_load(self, url: str):
        """URL 로드 - MainThread로 이벤트 전달"""
        main_thread = self._get_active_main_thread()
        if main_thread:
            main_thread.post_event(Event(EventType.LOAD, url=url))

    def handle_down(self, e=None):
        """스크롤 다운 - MainThread로 이벤트 전달"""
        main_thread = self._get_active_main_thread()
        if main_thread:
            main_thread.post_event(Event(EventType.SCROLL_DOWN))

    def handle_up(self, e=None):
        """스크롤 업 - MainThread로 이벤트 전달"""
        main_thread = self._get_active_main_thread()
        if main_thread:
            main_thread.post_event(Event(EventType.SCROLL_UP))

    def handle_scroll(self, wheel_event):
        """마우스 휠 스크롤 - MainThread로 이벤트 전달"""
        main_thread = self._get_active_main_thread()
        if main_thread and self.active_commit:
            delta = wheel_event.y * SCROLL_STEP
            viewport_height = self.height - self.chrome.bottom
            max_scroll = max(0, self.active_commit.document_height - viewport_height)
            new_scroll = max(
                0, min(self.active_commit.scroll - delta, max_scroll)
            )
            main_thread.post_event(Event(EventType.SCROLL_TO, scroll=new_scroll))

    def handle_click(self, button_event):
        """마우스 클릭 처리"""

        class ClickEvent:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        e = ClickEvent(button_event.x, button_event.y)

        if e.y < self.chrome.bottom:
            self.focus = None
            self.chrome.click(e)
            self.chrome_needs_raster = True
            self.set_needs_draw()
        else:
            self.focus = "content"
            self.chrome.blur()
            e.y = e.y - self.chrome.bottom

            # MainThread로 클릭 이벤트 전달
            main_thread = self._get_active_main_thread()
            if main_thread:
                main_thread.post_event(Event(EventType.CLICK, event=e))

    def handle_keydown(self, key_event):
        """SDL 키 이벤트 처리"""
        sym = key_event.keysym.sym

        if sym == sdl2.SDLK_DOWN:
            self.handle_down()
        elif sym == sdl2.SDLK_UP:
            self.handle_up()
        elif sym == sdl2.SDLK_RETURN:
            self.handle_return()
        elif sym == sdl2.SDLK_BACKSPACE:
            self.handle_backspace()

    def handle_text_input(self, text_event):
        """텍스트 입력 처리"""
        text = text_event.text.decode("utf-8")

        for char in text:
            if not (0x20 <= ord(char) < 0x7F):
                continue
            if self.chrome.keypress(char):
                self.chrome_needs_raster = True
                self.set_needs_draw()
            elif self.focus == "content":
                # MainThread로 키 입력 전달
                main_thread = self._get_active_main_thread()
                if main_thread:
                    main_thread.post_event(Event(EventType.KEYPRESS, char=char))

    def handle_backspace(self):
        """백스페이스 처리"""
        if not self.chrome.backspace():
            if self.focus == "content":
                # MainThread로 백스페이스 전달
                main_thread = self._get_active_main_thread()
                if main_thread:
                    main_thread.post_event(Event(EventType.BACKSPACE))
        else:
            self.chrome_needs_raster = True
            self.set_needs_draw()

    def handle_return(self, e=None):
        """Enter 키 처리"""
        self.chrome.enter()
        self.chrome_needs_raster = True
        self.set_needs_draw()

    def handle_resize(self, window_event):
        """윈도우 리사이즈 처리"""
        self.width = window_event.data1
        self.height = window_event.data2

        # Compositor에 리사이즈 알림
        self.compositor.resize(self.width, self.height)

        # MainThread로 리사이즈 이벤트 전달
        main_thread = self._get_active_main_thread()
        if main_thread:
            content_height = self.height - self.chrome.bottom
            main_thread.post_event(Event(
                EventType.RESIZE,
                width=self.width,
                height=content_height
            ))

        self.chrome_needs_raster = True
        self.set_needs_draw()

    def on_tab_content_changed(self):
        """탭 콘텐츠 변경 시 호출 (Browser Thread에서)"""
        if self.active_commit:
            self.tab_needs_raster = True
            self.chrome_needs_raster = True  # URL이 변경될 수 있으므로 Chrome도 업데이트
            self.set_needs_draw()

    def on_chrome_changed(self):
        """Chrome UI 변경 시 호출"""
        self.chrome_needs_raster = True
        self.set_needs_draw()

    def new_tab(self, url):
        """새 탭 생성 및 MainThread 시작"""
        new_tab = Tab(self.chrome.bottom, DEFAULT_STYLE_SHEET)
        new_tab.browser = self

        # MainThread 생성 및 시작
        main_thread = MainThread(new_tab, self.commit_queue)
        new_tab.main_thread = main_thread
        self.main_threads[id(new_tab)] = main_thread

        self.active_tab = new_tab
        self.tabs.append(new_tab)

        # MainThread 시작
        main_thread.start()

        # URL 로드 이벤트 전송
        main_thread.post_event(Event(EventType.LOAD, url=url))

        self.chrome_needs_raster = True
        self.set_needs_draw()

    def run(self):
        """메인 이벤트 루프 (Browser Thread)"""
        running = True

        while running:
            # SDL 이벤트 처리
            event = sdl2.SDL_Event()
            while sdl2.SDL_PollEvent(ctypes.byref(event)):
                if event.type == sdl2.SDL_QUIT:
                    running = False
                elif event.type == sdl2.SDL_KEYDOWN:
                    self.handle_keydown(event.key)
                elif event.type == sdl2.SDL_TEXTINPUT:
                    self.handle_text_input(event.text)
                elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
                    self.handle_click(event.button)
                elif event.type == sdl2.SDL_MOUSEWHEEL:
                    self.handle_scroll(event.wheel)
                elif event.type == sdl2.SDL_WINDOWEVENT:
                    if event.window.event == sdl2.SDL_WINDOWEVENT_RESIZED:
                        self.handle_resize(event.window)

            # MainThread에서 보낸 커밋 데이터 처리
            self.process_commits()

            # CPU 사용량 줄이기 (렌더링은 Compositor에서 처리)
            sdl2.SDL_Delay(16)  # ~60 FPS

        self.cleanup()

    def process_commits(self):
        """MainThread에서 보낸 커밋 데이터 처리"""
        while True:
            try:
                commit_data = self.commit_queue.get_nowait()

                # 활성 탭의 커밋만 적용
                if self.active_tab and commit_data.tab_id == id(self.active_tab):
                    self.active_commit = commit_data
                    self.on_tab_content_changed()

            except Empty:
                break

    def cleanup(self):
        """리소스 정리"""
        sdl2.SDL_StopTextInput()

        # Compositor Thread 종료
        self.compositor.stop()
        self.compositor.join(timeout=1.0)
        self.compositor.cleanup()

        # 모든 MainThread 종료
        for main_thread in self.main_threads.values():
            main_thread.stop()
        for main_thread in self.main_threads.values():
            main_thread.join(timeout=1.0)

        # NetworkThread 종료
        shutdown_network_thread()

        # 프로파일링 종료 및 저장
        Tracer.get().finish()

        # SDL 리소스 정리
        sdl2.SDL_DestroyRenderer(self.renderer)
        sdl2.SDL_DestroyWindow(self.window)
        sdl2.SDL_Quit()


if __name__ == "__main__":
    import sys

    browser = Browser()
    if len(sys.argv) > 1:
        browser.new_tab(sys.argv[1])
    else:
        browser.new_tab("about:blank")
    browser.run()
