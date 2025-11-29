"""
Frame - HTML 문서에 대한 DOM/레이아웃 트리 관리

Frame은 개별 HTML 문서(iframe 포함)를 담당하며:
- DOM 트리 관리
- 레이아웃 트리 관리
- 스타일 적용
- JavaScript 컨텍스트 관리
"""
import threading
from typing import TYPE_CHECKING, Optional, List

from ..dom import HTMLParser, tree_to_list, Element, Text
from ..css import CSSParser, style, cascade_priority
from ..networking import URLFactory, get_network_thread, RequestType
from ..layout import DocumentLayout, paint_tree
from ..profiling import MeasureTime
from ..scripting import JSContext

if TYPE_CHECKING:
    from .tab import Tab


class Frame:
    """
    개별 HTML 문서를 관리하는 클래스

    책임:
    - DOM 트리 관리 (nodes)
    - 레이아웃 트리 관리 (document)
    - 스타일시트 로드 및 적용
    - JavaScript 컨텍스트 관리
    - paint 트리 생성
    - 자식 프레임 (iframe) 관리
    """
    def __init__(self, tab: "Tab", parent_frame: Optional["Frame"] = None,
                 iframe_element: Optional[Element] = None):
        self.tab = tab
        self.parent_frame = parent_frame
        self.iframe_element = iframe_element  # 이 프레임을 포함하는 iframe 요소

        # DOM 및 레이아웃 상태
        self.url = None
        self.nodes = None  # DOM 트리
        self.document = None  # 레이아웃 트리
        self.rules = []  # CSS 규칙
        self.csp = None  # Content Security Policy

        # JavaScript
        self.js_context: Optional[JSContext] = None

        # 자식 프레임 목록 (iframe)
        self.child_frames: List["Frame"] = []

        # 렌더링 상태
        self.needs_render = False
        self.display_list = []

    def set_needs_render(self):
        """렌더링 필요 플래그 설정 - Tab에게 알림"""
        self.needs_render = True
        self.tab.set_needs_render()

    def load(self, url: str, payload=None, max_redirects=10):
        """URL을 로드하고 DOM 트리 구성"""
        with MeasureTime("frame_load", "load"):
            if max_redirects <= 0:
                raise Exception("Too many redirects")

            network = get_network_thread()

            # 메인 페이지 로드
            with MeasureTime("network_request", "network"):
                try:
                    url_obj = URLFactory.parse(url)
                    response = network.request_sync(
                        url=url_obj,
                        request_type=RequestType.PAGE_LOAD,
                        referrer=self.url,
                        payload=payload,
                    )
                    if response.error:
                        raise Exception(response.error)
                    status, headers, body, csp = (
                        response.status, response.headers, response.body, response.csp
                    )
                except Exception as e:
                    url_obj = URLFactory.parse("about:blank")
                    response = network.request_sync(
                        url=url_obj,
                        request_type=RequestType.PAGE_LOAD,
                        referrer=self.url,
                    )
                    status, headers, body, csp = (
                        response.status, response.headers, response.body, response.csp
                    )

            # HTML 파싱
            with MeasureTime("parse_html", "parse"):
                try:
                    nodes = HTMLParser(body).parse()
                except Exception:
                    nodes = HTMLParser("<html><body></body></html>").parse()

            # 리다이렉트 처리
            if 300 <= status < 400:
                location = headers.get("location")
                if location:
                    return self.load(location, max_redirects=max_redirects - 1)
                else:
                    raise Exception("Redirect without Location header")

            self.url = url_obj
            self.nodes = nodes
            self.csp = csp
            self.rules = self.tab.default_style_sheet.copy()

            # 스타일시트 로드
            with MeasureTime("load_stylesheets", "network"):
                self._load_stylesheets(url_obj, network)

            # 렌더링 수행
            self.render()

            # 스크립트 로드
            with MeasureTime("load_scripts", "network"):
                self._load_scripts(url_obj, network)

            # iframe 로드 (자식 프레임 생성)
            with MeasureTime("load_iframes", "load"):
                self._load_iframes(url_obj)

    def _load_stylesheets(self, url_obj, network):
        """스타일시트를 비동기로 로드"""
        links = [node.attributes for node in tree_to_list(self.nodes, [])
                 if isinstance(node, Element)
                 and node.tag == "link"
                 and node.attributes.get("rel") == "stylesheet"
                 and "href" in node.attributes]

        if not links:
            return

        # 모든 스타일시트 요청을 동시에 시작
        pending_requests = []
        for link in links:
            style_url = URLFactory.resolve(url_obj, link)
            # CSP style-src 검사
            if self.csp and not self.csp.allows_style(str(style_url)):
                print(f"CSP blocked stylesheet: {style_url}")
                continue

            result_holder = {"response": None}
            event = threading.Event()

            def on_stylesheet_loaded(resp, holder=result_holder, evt=event):
                holder["response"] = resp
                evt.set()

            network.request(
                url=style_url,
                request_type=RequestType.STYLESHEET,
                referrer=self.url,
                callback=on_stylesheet_loaded,
            )
            pending_requests.append((event, result_holder))

        # 모든 응답 대기 및 처리
        for event, holder in pending_requests:
            event.wait(timeout=10.0)
            response = holder["response"]
            if response and not response.error:
                try:
                    self.rules.extend(CSSParser(response.body).parse())
                except Exception:
                    pass

    def _load_scripts(self, url_obj, network):
        """스크립트를 로드하고 실행"""
        from ..threads.task import Task

        scripts = [node.attributes for node in tree_to_list(self.nodes, [])
                   if isinstance(node, Element)
                   and node.tag == "script"
                   and "src" in node.attributes]

        if self.js_context:
            self.js_context.discarded = True
        self.js_context = JSContext(self)

        if not scripts:
            return

        # 스크립트는 순서대로 실행
        for script in scripts:
            script_url = URLFactory.resolve(url_obj, script)
            # CSP script-src 검사
            if self.csp and not self.csp.allows_script(str(script_url)):
                print(f"CSP blocked script: {script_url}")
                continue

            try:
                response = network.request_sync(
                    url=script_url,
                    request_type=RequestType.SCRIPT,
                    referrer=self.url,
                )
                if response.error:
                    print(f"Script load error: {response.error}")
                    continue
                task = Task(self.js_context.run, script_url, response.body)
                self.tab.task_runner.schedule_task(task)
            except Exception as e:
                print(f"Script error: {e}")

    def _load_iframes(self, url_obj):
        """iframe 태그를 찾아 자식 프레임 생성"""
        # 기존 자식 프레임 정리
        for child_frame in self.child_frames:
            self.tab.remove_frame(child_frame)
        self.child_frames = []

        # iframe 요소 찾기
        iframes = [node for node in tree_to_list(self.nodes, [])
                   if isinstance(node, Element)
                   and node.tag == "iframe"
                   and "src" in node.attributes]

        for iframe_element in iframes:
            try:
                # iframe URL 해석
                iframe_src = iframe_element.attributes.get("src", "")
                if not iframe_src:
                    continue

                iframe_url = URLFactory.resolve_str(url_obj, iframe_src)

                # CSP frame-src 검사 (있는 경우)
                if self.csp and hasattr(self.csp, 'allows_frame'):
                    if not self.csp.allows_frame(iframe_url):
                        print(f"CSP blocked iframe: {iframe_url}")
                        continue

                # 자식 프레임 생성
                child_frame = Frame(
                    tab=self.tab,
                    parent_frame=self,
                    iframe_element=iframe_element
                )

                # iframe 요소에 프레임 참조 저장 (레이아웃에서 사용)
                iframe_element.frame = child_frame

                # 자식 프레임 로드
                child_frame.load(iframe_url)

                # 프레임 목록에 추가
                self.child_frames.append(child_frame)
                self.tab.add_frame(child_frame)

                # 프레임 계층 구조 설정
                if child_frame.js_context:
                    child_frame.js_context.setup_frame_hierarchy()

                # 부모 프레임의 window.frames에 자식 추가
                if self.js_context:
                    self.js_context.add_child_frame(child_frame)

            except Exception as e:
                print(f"iframe load error: {e}")

    def render(self):
        """스타일 적용 및 레이아웃 계산"""
        with MeasureTime("style", "style"):
            style(self.nodes, sorted(self.rules, key=cascade_priority))
        with MeasureTime("layout", "layout"):
            self.document = DocumentLayout(self.nodes, self.tab.width)
            self.document.layout()
        with MeasureTime("paint", "paint"):
            self.display_list = []
            paint_tree(self.document, self.display_list)
        self.needs_render = False

    def get_display_list(self) -> List:
        """프레임의 display list 반환 (자식 프레임 포함)"""
        result = self.display_list.copy()

        # 자식 프레임의 display list도 추가
        for child_frame in self.child_frames:
            result.extend(child_frame.get_display_list())

        return result

    def dispatch_event(self, type, elt):
        """JavaScript 이벤트 디스패치"""
        if self.js_context:
            return self.js_context.dispatch_event(type, elt)
        return False
