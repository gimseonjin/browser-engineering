"""
NetworkThread - 비동기 네트워크 요청 처리

네트워크 요청을 별도 스레드에서 처리하여 Main Thread 블로킹 방지
"""
import threading
from queue import Queue, Empty
from typing import TYPE_CHECKING, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from enum import Enum, auto
from concurrent.futures import ThreadPoolExecutor

from ..profiling import MeasureTime, set_thread_name

if TYPE_CHECKING:
    from .base_url import BaseURL


class RequestType(Enum):
    """네트워크 요청 타입"""
    PAGE_LOAD = auto()      # 메인 페이지 로드
    STYLESHEET = auto()     # CSS 스타일시트
    SCRIPT = auto()         # JavaScript
    XHR = auto()            # XMLHttpRequest
    IMAGE = auto()          # 이미지 (미래 확장용)


@dataclass
class NetworkRequest:
    """네트워크 요청 데이터"""
    request_id: int
    url: "BaseURL"
    request_type: RequestType
    referrer: Optional["BaseURL"] = None
    payload: Optional[str] = None
    callback: Optional[Callable] = None
    # 추가 메타데이터
    priority: int = 0  # 높을수록 우선


@dataclass
class NetworkResponse:
    """네트워크 응답 데이터"""
    request_id: int
    request_type: RequestType
    status: int
    headers: dict
    body: str
    csp: Any  # ContentSecurityPolicy
    url: "BaseURL"
    error: Optional[str] = None


class NetworkThread:
    """
    비동기 네트워크 요청 처리 스레드

    - ThreadPoolExecutor로 여러 요청 동시 처리
    - 요청 완료 시 콜백으로 Main Thread에 알림
    """

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="NetworkWorker")
        self.request_queue: Queue[NetworkRequest] = Queue()
        self.response_queue: Queue[NetworkResponse] = Queue()

        self._request_id_counter = 0
        self._lock = threading.Lock()

        # 진행 중인 요청 추적
        self.pending_requests: dict[int, NetworkRequest] = {}

        self.running = False
        self._dispatcher_thread: Optional[threading.Thread] = None

    def start(self):
        """네트워크 스레드 시작"""
        self.running = True
        self._dispatcher_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatcher_thread.start()

    def stop(self):
        """네트워크 스레드 종료"""
        self.running = False
        self.executor.shutdown(wait=False)
        if self._dispatcher_thread:
            self._dispatcher_thread.join(timeout=1.0)

    def _get_next_request_id(self) -> int:
        """고유 요청 ID 생성"""
        with self._lock:
            self._request_id_counter += 1
            return self._request_id_counter

    def _dispatch_loop(self):
        """요청 디스패치 루프"""
        set_thread_name("NetworkDispatcher")

        while self.running:
            try:
                request = self.request_queue.get(timeout=0.01)
                self._submit_request(request)
            except Empty:
                pass

    def _submit_request(self, request: NetworkRequest):
        """요청을 ThreadPool에 제출"""
        self.pending_requests[request.request_id] = request
        self.executor.submit(self._do_request, request)

    def _do_request(self, request: NetworkRequest):
        """실제 네트워크 요청 수행 (워커 스레드에서)"""
        with MeasureTime(f"network_{request.request_type.name}", "network"):
            try:
                result = request.url.request(
                    referrer=request.referrer,
                    payload=request.payload
                )
                status, headers, body, csp = result

                response = NetworkResponse(
                    request_id=request.request_id,
                    request_type=request.request_type,
                    status=status,
                    headers=headers,
                    body=body,
                    csp=csp,
                    url=request.url,
                )
            except Exception as e:
                response = NetworkResponse(
                    request_id=request.request_id,
                    request_type=request.request_type,
                    status=0,
                    headers={},
                    body="",
                    csp=None,
                    url=request.url,
                    error=str(e),
                )

            # 응답 큐에 추가
            self.response_queue.put(response)

            # pending에서 제거
            self.pending_requests.pop(request.request_id, None)

            # 콜백이 있으면 호출 (Main Thread에서 처리하도록 Task로)
            if request.callback:
                request.callback(response)

    def request(
        self,
        url: "BaseURL",
        request_type: RequestType = RequestType.PAGE_LOAD,
        referrer: Optional["BaseURL"] = None,
        payload: Optional[str] = None,
        callback: Optional[Callable[[NetworkResponse], None]] = None,
        priority: int = 0,
    ) -> int:
        """
        비동기 네트워크 요청

        Returns:
            request_id: 요청 추적용 ID
        """
        request_id = self._get_next_request_id()

        request = NetworkRequest(
            request_id=request_id,
            url=url,
            request_type=request_type,
            referrer=referrer,
            payload=payload,
            callback=callback,
            priority=priority,
        )

        self.request_queue.put(request)
        return request_id

    def request_sync(
        self,
        url: "BaseURL",
        request_type: RequestType = RequestType.PAGE_LOAD,
        referrer: Optional["BaseURL"] = None,
        payload: Optional[str] = None,
    ) -> NetworkResponse:
        """
        동기 네트워크 요청 (블로킹)

        초기 페이지 로드 등 반드시 동기가 필요한 경우 사용
        """
        event = threading.Event()
        result: list[NetworkResponse] = []

        def on_complete(response: NetworkResponse):
            result.append(response)
            event.set()

        self.request(
            url=url,
            request_type=request_type,
            referrer=referrer,
            payload=payload,
            callback=on_complete,
        )

        event.wait()  # 응답 대기
        return result[0]

    def get_pending_count(self) -> int:
        """진행 중인 요청 수"""
        return len(self.pending_requests)

    def poll_responses(self) -> list[NetworkResponse]:
        """완료된 응답들 가져오기 (non-blocking)"""
        responses = []
        while True:
            try:
                response = self.response_queue.get_nowait()
                responses.append(response)
            except Empty:
                break
        return responses


# 전역 싱글톤 (선택적)
_network_thread: Optional[NetworkThread] = None


def get_network_thread() -> NetworkThread:
    """전역 NetworkThread 인스턴스 반환"""
    global _network_thread
    if _network_thread is None:
        _network_thread = NetworkThread()
        _network_thread.start()
    return _network_thread


def shutdown_network_thread():
    """전역 NetworkThread 종료"""
    global _network_thread
    if _network_thread:
        _network_thread.stop()
        _network_thread = None
