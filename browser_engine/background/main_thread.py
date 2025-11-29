"""
MainThread - Tab당 하나씩 생성되는 스레드
스크립트 실행, 레이아웃, 렌더링을 담당
"""
import threading
from queue import Queue, Empty
from typing import TYPE_CHECKING, Optional, Callable, Any
from enum import Enum, auto

from .commit_data import CommitData
from .task import Task
from ..profiling import MeasureTime, set_thread_name

if TYPE_CHECKING:
    from ..ui.tab import Tab


class EventType(Enum):
    """Browser에서 Tab으로 전달되는 이벤트 타입"""
    LOAD = auto()
    CLICK = auto()
    KEYPRESS = auto()
    BACKSPACE = auto()
    SCROLL_DOWN = auto()
    SCROLL_UP = auto()
    SCROLL_TO = auto()
    RESIZE = auto()
    GO_BACK = auto()
    STOP = auto()


class Event:
    """Browser에서 Tab으로 전달되는 이벤트"""
    def __init__(self, event_type: EventType, **kwargs):
        self.type = event_type
        self.data = kwargs


class MainThread(threading.Thread):
    """
    Tab을 위한 메인 스레드

    - Browser Thread에서 이벤트를 받아 처리
    - 렌더링 완료 후 CommitData를 Browser Thread로 전달
    """

    def __init__(self, tab: "Tab", browser_commit_queue: Queue):
        super().__init__(daemon=True)
        self.tab = tab
        self.browser_commit_queue = browser_commit_queue

        # Browser -> Tab 이벤트 큐
        self.event_queue: Queue[Event] = Queue()

        # 스레드 상태
        self.running = False
        self.lock = threading.Lock()

    def run(self):
        """메인 스레드 이벤트 루프"""
        self.running = True

        # 프로파일링: MainThread 이름 설정
        set_thread_name(f"MainThread-{id(self.tab)}")

        while self.running:
            # 이벤트 처리
            try:
                event = self.event_queue.get(timeout=0.01)
                with MeasureTime(f"handle_{event.type.name}", "event"):
                    self._handle_event(event)
            except Empty:
                pass

            # TaskRunner의 태스크 실행
            self.tab.task_runner.run()

            # 렌더링이 필요하면 렌더링 후 커밋
            if self.tab.needs_render:
                with MeasureTime("render", "render"):
                    self.tab.render()
                with MeasureTime("commit", "commit"):
                    self._commit()

    def _handle_event(self, event: Event):
        """이벤트 처리"""
        if event.type == EventType.STOP:
            self.running = False
            return

        elif event.type == EventType.LOAD:
            url = event.data.get("url")
            payload = event.data.get("payload")
            self.tab.load(url, payload)
            self._commit()

        elif event.type == EventType.CLICK:
            e = event.data.get("event")
            self.tab.click(e)
            # 클릭으로 인해 load()가 호출될 수 있으므로 항상 commit
            if self.tab.needs_render:
                self.tab.render()
            self._commit()

        elif event.type == EventType.KEYPRESS:
            char = event.data.get("char")
            self.tab.keypress(char)
            if self.tab.needs_render:
                self.tab.render()
                self._commit()

        elif event.type == EventType.BACKSPACE:
            self.tab.backspace()
            if self.tab.needs_render:
                self.tab.render()
                self._commit()

        elif event.type == EventType.SCROLL_DOWN:
            self.tab.scrolldown()
            self._commit_scroll()

        elif event.type == EventType.SCROLL_UP:
            self.tab.scollup()
            self._commit_scroll()

        elif event.type == EventType.SCROLL_TO:
            scroll = event.data.get("scroll", 0)
            self.tab.scroll = scroll
            self._commit_scroll()

        elif event.type == EventType.RESIZE:
            width = event.data.get("width")
            height = event.data.get("height")
            self.tab.width = width
            self.tab.height = height
            self.tab.set_needs_render()

        elif event.type == EventType.GO_BACK:
            self.tab.go_back()
            self._commit()

    def _commit(self):
        """렌더링 결과를 Browser Thread로 커밋"""
        commit_data = CommitData(
            display_list=self.tab.display_list.copy(),
            document_height=self.tab.get_max_y(),
            scroll=self.tab.scroll,
            url=str(self.tab.url) if self.tab.url else None,
            tab_id=id(self.tab)
        )
        self.browser_commit_queue.put(commit_data)

    def _commit_scroll(self):
        """스크롤 변경만 커밋 (렌더링 없이)"""
        commit_data = CommitData(
            display_list=self.tab.display_list.copy() if hasattr(self.tab, 'display_list') else [],
            document_height=self.tab.get_max_y() if hasattr(self.tab, 'document') else 0,
            scroll=self.tab.scroll,
            url=str(self.tab.url) if self.tab.url else None,
            tab_id=id(self.tab)
        )
        self.browser_commit_queue.put(commit_data)

    def post_event(self, event: Event):
        """Browser Thread에서 이벤트 전달"""
        self.event_queue.put(event)

    def stop(self):
        """스레드 종료"""
        self.post_event(Event(EventType.STOP))
