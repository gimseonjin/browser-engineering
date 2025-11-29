"""
JSContext - JavaScript 실행 컨텍스트

각 Frame은 자신만의 JSContext를 가지며:
- 고유한 frame_id를 가짐
- 자신만의 window 객체를 가짐
- same-origin이면 다른 프레임의 window에 접근 가능
"""
import threading
from typing import TYPE_CHECKING, Optional
import dukpy

from ..css import CSSParser
from ..dom import HTMLParser, tree_to_list, Element
from ..networking import URLFactory

if TYPE_CHECKING:
    from ..content.frame import Frame

RUNTIME_JS = open("runtime.js").read()
EVENT_DISPATCH_JS = \
    "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type));"
SET_TIMEOUT_JS = "__runSetTimeout(dukpy.handle);"
XHR_ONLOAD_JS = "__runXHROnload(dukpy.out, dukpy.handle);"

# 프레임 ID 생성기
_frame_id_counter = 0


def _generate_frame_id():
    global _frame_id_counter
    _frame_id_counter += 1
    return _frame_id_counter


class JSContext:
    """
    JavaScript 실행 컨텍스트

    각 Frame은 자신만의 JSContext를 가지며, 각 JSContext는:
    - 고유한 frame_id를 가짐
    - 자신만의 window 객체를 가짐
    - same-origin이면 다른 프레임의 window에 접근 가능
    """
    def __init__(self, frame: "Frame"):
        self.frame = frame
        self.frame_id = _generate_frame_id()
        self.interp = dukpy.JSInterpreter()

        # Python 함수 export
        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll", self.querySelectorAll)
        self.interp.export_function("getAttribute", self.get_attribute)
        self.interp.export_function("innerHTML_set", self.innerHTML_set)
        self.interp.export_function("XMLHttpRequest_send", self.XMLHttpRequest_send)
        self.interp.export_function("setTimeout", self.setTimeout)
        self.interp.export_function("postMessage", self.postMessage)
        self.interp.export_function("getLocationHref", self.getLocationHref)
        self.interp.export_function("setLocationHref", self.setLocationHref)

        # runtime.js 로드
        self.interp.evaljs(RUNTIME_JS)

        # window와 document 초기화
        self._init_window()

        self.discarded = False
        self.node_to_handle = {}
        self.handle_to_node = {}

    def _init_window(self):
        """window 객체 초기화 및 프레임 계층 구조 설정"""
        # window 초기화
        self.interp.evaljs(f"__initWindow({self.frame_id});")

        # origin 설정
        origin = self.frame.url.origin() if self.frame.url else ""
        self.interp.evaljs(f"window._setOrigin('{origin}');")

        # document 초기화
        self.interp.evaljs(f"__initDocument({self.frame_id});")

    def setup_frame_hierarchy(self):
        """프레임 계층 구조 설정 (iframe 로드 후 호출)"""
        # parent 설정
        if self.frame.parent_frame and self.frame.parent_frame.js_context:
            parent_id = self.frame.parent_frame.js_context.frame_id
            self.interp.evaljs(f"window._setParent({parent_id});")
        else:
            self.interp.evaljs("window._setParent(null);")

        # top 설정
        top_frame = self._get_top_frame()
        if top_frame and top_frame.js_context:
            top_id = top_frame.js_context.frame_id
            self.interp.evaljs(f"window._setTop({top_id});")
        else:
            self.interp.evaljs("window._setTop(null);")

    def _get_top_frame(self) -> Optional["Frame"]:
        """최상위 프레임 반환"""
        frame = self.frame
        while frame.parent_frame:
            frame = frame.parent_frame
        return frame

    def add_child_frame(self, child_frame: "Frame"):
        """자식 프레임을 frames 배열에 추가"""
        if child_frame.js_context:
            child_id = child_frame.js_context.frame_id
            self.interp.evaljs(f"window._addFrame({child_id});")

    def is_same_origin(self, other_frame: "Frame") -> bool:
        """다른 프레임과 same-origin인지 확인"""
        if not self.frame.url or not other_frame.url:
            return False
        return self.frame.url.origin() == other_frame.url.origin()

    def run(self, script, code):
        try:
            return self.interp.evaljs(code)
        except Exception as e:
            print(f"Script {script} error: {e}")

    def get_handle(self, elt):
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
            return handle
        return self.node_to_handle[elt]

    def get_attribute(self, handle, attr):
        elt = self.handle_to_node[handle]
        attr_val = elt.attributes.get(attr, None)
        return attr_val if attr_val else ""

    def querySelectorAll(self, frame_id, selector_text):
        """프레임별 querySelectorAll (same-origin 체크)"""
        # frame_id로 프레임 찾기
        target_frame = self._find_frame_by_id(frame_id)
        if not target_frame:
            target_frame = self.frame

        # same-origin 체크
        if target_frame != self.frame and not self.is_same_origin(target_frame):
            print(f"SecurityError: Blocked cross-origin access")
            return []

        selector = CSSParser(selector_text).selector()
        nodes = [node for node in tree_to_list(target_frame.nodes, [])
                if isinstance(node, Element) and selector.matches(node)]
        return [self.get_handle(node) for node in nodes]

    def _find_frame_by_id(self, frame_id: int) -> Optional["Frame"]:
        """frame_id로 프레임 찾기"""
        # 현재 프레임 확인
        if self.frame_id == frame_id:
            return self.frame

        # Tab의 모든 프레임에서 찾기
        for frame in self.frame.tab.frames:
            if frame.js_context and frame.js_context.frame_id == frame_id:
                return frame
        return None

    def dispatch_event(self, type, elt):
        handle = self.node_to_handle.get(elt, -1)
        do_default = self.interp.evaljs(
            EVENT_DISPATCH_JS, type=type, handle=handle
        )
        return not do_default

    def innerHTML_set(self, handle, value):
        doc = HTMLParser("<html><body>" + value + "</body></html>").parse()
        new_nodes = doc.children[0].children
        elt = self.handle_to_node[handle]
        elt.children = new_nodes
        for child in elt.children:
            child.parent = elt
        self.frame.set_needs_render()

    def dispatch_xhr_onload(self, body, handle):
        if self.discarded: return
        self.interp.evaljs(XHR_ONLOAD_JS, out=body, handle=handle)

    def XMLHttpRequest_send(self, frame_id, method, url, data, is_async, handle):
        from ..threads.task import Task

        # frame_id로 프레임 찾기 (요청을 보낸 프레임)
        request_frame = self._find_frame_by_id(frame_id) or self.frame

        url_obj = URLFactory.parse(url)

        if url_obj.origin() != request_frame.url.origin():
            return "403 Forbidden"

        # CSP connect-src 검사
        if request_frame.csp and not request_frame.csp.allows_connect(url):
            print(f"CSP blocked XMLHttpRequest to: {url}")
            return "403 Forbidden"

        def run_load():
            result = url_obj.request(referrer=request_frame.url, payload=data)
            status, headers, body, csp = result
            task = Task(self.dispatch_xhr_onload, body, handle)
            self.frame.tab.task_runner.schedule_task(task)
            return body

        if not is_async:
            return run_load()
        else:
            threading.Thread(target=run_load).start()

    def dispatch_setTimeout(self, handle):
        if self.discarded: return
        self.interp.evaljs(SET_TIMEOUT_JS, handle=handle)

    def setTimeout(self, handle, time):
        from ..threads.task import Task
        def run_callback():
            task = Task(self.dispatch_setTimeout, handle)
            self.frame.tab.task_runner.schedule_task(task)
        threading.Timer(time / 1000.0, run_callback).start()

    def postMessage(self, target_frame_id, message, target_origin):
        """cross-origin 메시지 전송"""
        target_frame = self._find_frame_by_id(target_frame_id)
        if not target_frame or not target_frame.js_context:
            return

        # targetOrigin 검사
        if target_origin != "*":
            if target_frame.url and target_frame.url.origin() != target_origin:
                return

        # 메시지 이벤트 전달 (TODO: MessageEvent 구현)
        source_origin = self.frame.url.origin() if self.frame.url else ""
        # target_frame.js_context.dispatch_message_event(message, source_origin, self.frame_id)

    def getLocationHref(self, frame_id):
        """window.location.href 가져오기"""
        target_frame = self._find_frame_by_id(frame_id) or self.frame
        if target_frame.url:
            return str(target_frame.url)
        return ""

    def setLocationHref(self, frame_id, url):
        """window.location.href 설정 (페이지 이동)"""
        target_frame = self._find_frame_by_id(frame_id) or self.frame
        # same-origin 체크
        if target_frame != self.frame and not self.is_same_origin(target_frame):
            print(f"SecurityError: Blocked cross-origin navigation")
            return
        target_frame.load(url)
