"""
CompositorThread - Raster, Composite, Blit를 담당하는 스레드

Browser Thread에서 분리되어 화면 그리기만 전담
"""
import threading
import ctypes
import sdl2
import skia
from queue import Queue, Empty
from typing import TYPE_CHECKING, Optional, List, Any
from dataclasses import dataclass, field

from ..profiling import MeasureTime, set_thread_name

if TYPE_CHECKING:
    from .commit_data import CommitData


@dataclass
class CompositorData:
    """Compositor에 전달되는 렌더링 데이터"""
    # Tab 콘텐츠
    display_list: List[Any] = field(default_factory=list)
    document_height: float = 0.0
    scroll: float = 0.0

    # Chrome UI
    chrome_commands: List[Any] = field(default_factory=list)
    chrome_height: float = 0.0

    # 윈도우 크기
    width: int = 800
    height: int = 600

    # 플래그
    chrome_changed: bool = False
    tab_changed: bool = False
    scroll_changed: bool = False


class CompositorThread(threading.Thread):
    """
    Compositor Thread - 화면 그리기 전담

    - Raster: DrawCmd를 픽셀로 변환
    - Composite: 여러 Surface 합성
    - Blit: SDL 텍스처로 출력
    """

    def __init__(self, renderer, window_width: int, window_height: int):
        super().__init__(daemon=True)
        self.renderer = renderer

        # 데이터 큐 (Browser -> Compositor)
        self.data_queue: Queue[CompositorData] = Queue()

        # 현재 렌더링 데이터
        self.current_data: Optional[CompositorData] = None

        # 크기
        self.width = window_width
        self.height = window_height

        # Skia Surfaces
        self.root_surface: Optional[skia.Surface] = None
        self.chrome_surface: Optional[skia.Surface] = None
        self.tab_surface: Optional[skia.Surface] = None

        # SDL 텍스처
        self.sdl_texture = None

        # Dirty flags
        self.chrome_needs_raster = True
        self.tab_needs_raster = True

        # 스레드 상태
        self.running = False
        self.lock = threading.Lock()

        # VSync 타겟 (~60fps)
        self.frame_interval = 1.0 / 60.0

    def run(self):
        """Compositor 메인 루프"""
        self.running = True
        set_thread_name("CompositorThread")

        # Surface 및 텍스처 초기화
        self._init_surfaces()

        import time
        last_frame_time = time.perf_counter()

        while self.running:
            # 새 데이터 확인
            self._process_data_queue()

            # 렌더링
            if self.current_data:
                with MeasureTime("compositor_frame", "compositor"):
                    self._render_frame()

            # VSync 대기 (~60fps)
            current_time = time.perf_counter()
            elapsed = current_time - last_frame_time
            if elapsed < self.frame_interval:
                time.sleep(self.frame_interval - elapsed)
            last_frame_time = time.perf_counter()

    def _init_surfaces(self):
        """Surface 및 텍스처 초기화"""
        self.root_surface = skia.Surface(self.width, self.height)
        self.sdl_texture = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA32,
            sdl2.SDL_TEXTUREACCESS_STREAMING,
            self.width,
            self.height,
        )

    def _process_data_queue(self):
        """데이터 큐에서 새 데이터 가져오기"""
        try:
            # 최신 데이터만 사용 (이전 프레임 스킵)
            latest_data = None
            while True:
                try:
                    latest_data = self.data_queue.get_nowait()
                except Empty:
                    break

            if latest_data:
                self._apply_data(latest_data)
        except Exception:
            pass

    def _apply_data(self, data: CompositorData):
        """새 데이터 적용"""
        with self.lock:
            # 크기 변경 확인
            if data.width != self.width or data.height != self.height:
                self.width = data.width
                self.height = data.height
                self._resize_surfaces()

            # Chrome 변경
            if data.chrome_changed:
                self.chrome_needs_raster = True
                if data.chrome_height > 0:
                    self._ensure_chrome_surface(int(data.chrome_height))

            # Tab 변경
            if data.tab_changed:
                self.tab_needs_raster = True
                if data.document_height > 0:
                    self._ensure_tab_surface(int(data.document_height))

            self.current_data = data

    def _ensure_chrome_surface(self, height: int):
        """Chrome Surface 생성/재생성"""
        height = max(1, height)
        if self.chrome_surface is None or self.chrome_surface.height() != height:
            self.chrome_surface = skia.Surface(self.width, height)
            self.chrome_needs_raster = True

    def _ensure_tab_surface(self, document_height: int):
        """Tab Surface 생성/재생성"""
        chrome_height = self.current_data.chrome_height if self.current_data else 0
        viewport_height = self.height - chrome_height
        height = max(int(document_height), int(viewport_height), 1)

        if self.tab_surface is None or self.tab_surface.height() != height:
            self.tab_surface = skia.Surface(self.width, height)
            self.tab_needs_raster = True

    def _resize_surfaces(self):
        """윈도우 크기 변경 시 Surface 재생성"""
        self.root_surface = skia.Surface(self.width, self.height)

        # SDL 텍스처 재생성
        if self.sdl_texture:
            sdl2.SDL_DestroyTexture(self.sdl_texture)
        self.sdl_texture = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA32,
            sdl2.SDL_TEXTUREACCESS_STREAMING,
            self.width,
            self.height,
        )

        self.chrome_needs_raster = True
        self.tab_needs_raster = True

    def _render_frame(self):
        """한 프레임 렌더링"""
        self._raster_chrome()
        self._raster_tab()
        self._composite()
        self._blit_to_sdl()

    def _raster_chrome(self):
        """Chrome UI 래스터화"""
        if not self.chrome_needs_raster or not self.chrome_surface:
            return
        if not self.current_data or not self.current_data.chrome_commands:
            return

        with MeasureTime("raster_chrome", "raster"):
            canvas = self.chrome_surface.getCanvas()
            canvas.clear(skia.ColorWHITE)

            for cmd in self.current_data.chrome_commands:
                cmd.execute(0, canvas)

            self.chrome_needs_raster = False

    def _raster_tab(self):
        """Tab 콘텐츠 래스터화"""
        if not self.tab_needs_raster or not self.tab_surface:
            return
        if not self.current_data or not self.current_data.display_list:
            return

        with MeasureTime("raster_tab", "raster"):
            canvas = self.tab_surface.getCanvas()
            canvas.clear(skia.ColorWHITE)

            for cmd in self.current_data.display_list:
                cmd.execute(0, canvas)

            self.tab_needs_raster = False

    def _composite(self):
        """Surface 합성"""
        if not self.current_data:
            return

        with MeasureTime("composite", "composite"):
            canvas = self.root_surface.getCanvas()
            canvas.clear(skia.ColorWHITE)

            chrome_height = self.current_data.chrome_height

            # 1. Tab Surface 합성 (스크롤 적용)
            if self.tab_surface:
                tab_image = self.tab_surface.makeImageSnapshot()
                scroll = self.current_data.scroll
                viewport_height = self.height - chrome_height

                src_rect = skia.Rect(0, scroll, self.width, scroll + viewport_height)
                dst_rect = skia.Rect(0, chrome_height, self.width, self.height)

                canvas.drawImageRect(tab_image, src_rect, dst_rect)

            # 2. Chrome Surface 합성
            if self.chrome_surface:
                chrome_image = self.chrome_surface.makeImageSnapshot()
                canvas.drawImage(chrome_image, 0, 0)

            # 3. 스크롤바
            self._draw_scrollbar(canvas, chrome_height)

    def _draw_scrollbar(self, canvas, chrome_height: float):
        """스크롤바 그리기"""
        if not self.current_data:
            return

        max_y = self.current_data.document_height
        viewport_height = self.height - chrome_height

        if max_y <= viewport_height:
            return

        track_x = self.width - 12
        track_y = chrome_height
        track_height = viewport_height

        paint = skia.Paint()
        paint.setColor(skia.Color(220, 220, 220, 255))
        canvas.drawRect(
            skia.Rect(track_x, track_y, track_x + 12, track_y + track_height),
            paint,
        )

        thumb_height = max(30, viewport_height * viewport_height / max_y)
        max_scroll = max_y - viewport_height
        scroll_ratio = (
            self.current_data.scroll / max_scroll if max_scroll > 0 else 0
        )
        thumb_y = track_y + scroll_ratio * (track_height - thumb_height)

        paint.setColor(skia.Color(150, 150, 150, 255))
        canvas.drawRect(
            skia.Rect(track_x + 2, thumb_y, track_x + 10, thumb_y + thumb_height),
            paint,
        )

    def _blit_to_sdl(self):
        """SDL 텍스처로 출력"""
        with MeasureTime("blit", "blit"):
            image = self.root_surface.makeImageSnapshot()
            pixels = image.tobytes()

            sdl2.SDL_UpdateTexture(
                self.sdl_texture, None, pixels, self.width * 4
            )

            sdl2.SDL_RenderClear(self.renderer)
            sdl2.SDL_RenderCopy(self.renderer, self.sdl_texture, None, None)
            sdl2.SDL_RenderPresent(self.renderer)

    def submit(self, data: CompositorData):
        """렌더링 데이터 제출 (Browser Thread에서 호출)"""
        self.data_queue.put(data)

    def resize(self, width: int, height: int):
        """윈도우 크기 변경 알림"""
        with self.lock:
            self.width = width
            self.height = height
            self._resize_surfaces()

    def stop(self):
        """스레드 종료"""
        self.running = False

    def cleanup(self):
        """리소스 정리"""
        if self.sdl_texture:
            sdl2.SDL_DestroyTexture(self.sdl_texture)
        self.root_surface = None
        self.chrome_surface = None
        self.tab_surface = None
