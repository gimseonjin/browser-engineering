"""
Chrome Tracing Format 프로파일러

사용법:
    # 컨텍스트 매니저로 사용
    with MeasureTime("raster"):
        do_raster()

    # 데코레이터로 사용
    @MeasureTime.trace("layout")
    def do_layout():
        pass

    # 프로그램 종료 시 JSON 파일 저장
    Tracer.get().finish()

결과 파일은 chrome://tracing 에서 열 수 있습니다.
"""
import json
import threading
import time
import atexit
from typing import Optional, List, Dict, Any, Callable
from functools import wraps


class TraceEvent:
    """Chrome Trace Event Format의 단일 이벤트"""

    def __init__(
        self,
        name: str,
        category: str,
        phase: str,
        timestamp: float,
        thread_id: int,
        process_id: int,
        args: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.cat = category
        self.ph = phase  # 'B' = begin, 'E' = end, 'X' = complete, 'i' = instant
        self.ts = timestamp  # microseconds
        self.tid = thread_id
        self.pid = process_id
        self.args = args or {}

    def to_dict(self) -> Dict[str, Any]:
        event = {
            "name": self.name,
            "cat": self.cat,
            "ph": self.ph,
            "ts": self.ts,
            "tid": self.tid,
            "pid": self.pid,
        }
        if self.args:
            event["args"] = self.args
        return event


class Tracer:
    """싱글톤 트레이서 - 모든 이벤트를 수집"""

    _instance: Optional["Tracer"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.events: List[TraceEvent] = []
        self.lock = threading.Lock()
        self.enabled = True
        self.start_time = time.perf_counter()
        self.output_file = "trace.json"

        # 스레드 이름 매핑
        self.thread_names: Dict[int, str] = {}

        # 프로세스 메타데이터
        self.process_name = "Browser"
        self.process_id = 1

    @classmethod
    def get(cls) -> "Tracer":
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = Tracer()
                    atexit.register(cls._instance.finish)
        return cls._instance

    def set_output_file(self, filename: str):
        """출력 파일명 설정"""
        self.output_file = filename

    def set_thread_name(self, name: str, thread_id: Optional[int] = None):
        """현재 스레드에 이름 설정 (트레이스에 표시됨)"""
        if thread_id is None:
            thread_id = threading.get_ident()
        self.thread_names[thread_id] = name

    def get_timestamp(self) -> float:
        """시작 시점 기준 마이크로초 반환"""
        return (time.perf_counter() - self.start_time) * 1_000_000

    def add_event(self, event: TraceEvent):
        """이벤트 추가"""
        if not self.enabled:
            return
        with self.lock:
            self.events.append(event)

    def begin(self, name: str, category: str = "function", args: Optional[Dict] = None):
        """Duration 이벤트 시작"""
        self.add_event(
            TraceEvent(
                name=name,
                category=category,
                phase="B",
                timestamp=self.get_timestamp(),
                thread_id=threading.get_ident(),
                process_id=self.process_id,
                args=args,
            )
        )

    def end(self, name: str, category: str = "function", args: Optional[Dict] = None):
        """Duration 이벤트 종료"""
        self.add_event(
            TraceEvent(
                name=name,
                category=category,
                phase="E",
                timestamp=self.get_timestamp(),
                thread_id=threading.get_ident(),
                process_id=self.process_id,
                args=args,
            )
        )

    def instant(self, name: str, category: str = "instant", scope: str = "t", args: Optional[Dict] = None):
        """인스턴트 이벤트 (특정 시점 마킹)

        scope: 't' = thread, 'p' = process, 'g' = global
        """
        event = TraceEvent(
            name=name,
            category=category,
            phase="i",
            timestamp=self.get_timestamp(),
            thread_id=threading.get_ident(),
            process_id=self.process_id,
            args=args,
        )
        # instant 이벤트에는 's' (scope) 필드 추가
        event_dict = event.to_dict()
        event_dict["s"] = scope

        if not self.enabled:
            return
        with self.lock:
            self.events.append(event)

    def _generate_metadata_events(self) -> List[Dict]:
        """메타데이터 이벤트 생성 (프로세스/스레드 이름)"""
        metadata = []

        # 프로세스 이름
        metadata.append({
            "name": "process_name",
            "ph": "M",
            "pid": self.process_id,
            "args": {"name": self.process_name}
        })

        # 스레드 이름들
        for tid, name in self.thread_names.items():
            metadata.append({
                "name": "thread_name",
                "ph": "M",
                "pid": self.process_id,
                "tid": tid,
                "args": {"name": name}
            })

        return metadata

    def finish(self):
        """트레이스 종료 및 JSON 파일 저장"""
        if not self.enabled:
            return

        self.enabled = False

        with self.lock:
            # 메타데이터 + 이벤트
            trace_data = {
                "traceEvents": (
                    self._generate_metadata_events() +
                    [e.to_dict() for e in self.events]
                ),
                "displayTimeUnit": "ms",
                "systemTraceEvents": "SystemTraceData",
                "otherData": {
                    "version": "Browser Profiler v1.0"
                }
            }

            with open(self.output_file, "w") as f:
                json.dump(trace_data, f)

            print(f"Trace saved to {self.output_file}")
            print(f"Open chrome://tracing and load the file to view")

    def clear(self):
        """이벤트 초기화"""
        with self.lock:
            self.events.clear()
            self.start_time = time.perf_counter()


class MeasureTime:
    """
    시간 측정 컨텍스트 매니저 / 데코레이터

    사용법:
        # 컨텍스트 매니저
        with MeasureTime("render"):
            do_render()

        # 데코레이터
        @MeasureTime.trace("layout")
        def do_layout():
            pass

        # 카테고리 지정
        with MeasureTime("parse_html", category="parsing"):
            parse()
    """

    def __init__(self, name: str, category: str = "function", args: Optional[Dict] = None):
        self.name = name
        self.category = category
        self.args = args
        self.tracer = Tracer.get()

    def __enter__(self):
        self.tracer.begin(self.name, self.category, self.args)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tracer.end(self.name, self.category)
        return False

    @staticmethod
    def trace(name: str, category: str = "function") -> Callable:
        """데코레이터로 사용"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                with MeasureTime(name, category):
                    return func(*args, **kwargs)
            return wrapper
        return decorator


# 편의 함수들
def trace_begin(name: str, category: str = "function", args: Optional[Dict] = None):
    """Duration 이벤트 시작"""
    Tracer.get().begin(name, category, args)


def trace_end(name: str, category: str = "function"):
    """Duration 이벤트 종료"""
    Tracer.get().end(name, category)


def trace_instant(name: str, category: str = "instant", args: Optional[Dict] = None):
    """인스턴트 이벤트"""
    Tracer.get().instant(name, category, args=args)


def set_thread_name(name: str):
    """현재 스레드 이름 설정"""
    Tracer.get().set_thread_name(name)
