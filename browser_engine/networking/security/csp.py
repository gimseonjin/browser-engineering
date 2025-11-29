"""Content Security Policy implementation"""


class ContentSecurityPolicy:
    """Content-Security-Policy 헤더 파서 및 검증기"""

    DIRECTIVES = [
        "default-src",
        "script-src",
        "style-src",
        "img-src",
        "font-src",
        "connect-src",
        "media-src",
        "object-src",
        "frame-src",
        "child-src",
        "worker-src",
        "frame-ancestors",
        "form-action",
        "base-uri",
        "manifest-src",
    ]

    def __init__(self, csp_header: str = None):
        self.directives = {}
        if csp_header:
            self.parse(csp_header)

    def parse(self, csp_header: str):
        """CSP 헤더를 파싱하여 디렉티브별로 저장"""
        self.directives = {}

        # 세미콜론으로 분리하여 각 디렉티브 파싱
        parts = csp_header.split(";")
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 공백으로 분리하여 디렉티브 이름과 값들 추출
            tokens = part.split()
            if not tokens:
                continue

            directive_name = tokens[0].lower()
            directive_values = tokens[1:] if len(tokens) > 1 else []

            self.directives[directive_name] = directive_values

    def allows_source(self, directive: str, source: str) -> bool:
        """특정 디렉티브에서 소스가 허용되는지 확인"""
        # 해당 디렉티브가 없으면 default-src 확인
        values = self.directives.get(directive)
        if values is None:
            values = self.directives.get("default-src")

        # CSP가 없거나 해당 디렉티브가 없으면 허용
        if values is None:
            return True

        return self._check_source_against_values(source, values)

    def _check_source_against_values(self, source: str, values: list) -> bool:
        """소스가 값 리스트에 허용되는지 확인"""
        source_lower = source.lower()

        for value in values:
            value_lower = value.lower()

            # 'none' - 모든 소스 차단
            if value_lower == "'none'":
                return False

            # '*' - 모든 소스 허용 (data:, blob: 제외)
            if value_lower == "*":
                if not source_lower.startswith("data:") and not source_lower.startswith("blob:"):
                    return True

            # 'self' - 동일 출처만 허용
            if value_lower == "'self'":
                # 실제 구현에서는 현재 페이지의 origin과 비교 필요
                continue

            # 'unsafe-inline' - 인라인 스크립트/스타일 허용
            if value_lower == "'unsafe-inline'":
                if source_lower == "inline":
                    return True

            # 'unsafe-eval' - eval() 허용
            if value_lower == "'unsafe-eval'":
                if source_lower == "eval":
                    return True

            # data: 스킴
            if value_lower == "data:" and source_lower.startswith("data:"):
                return True

            # blob: 스킴
            if value_lower == "blob:" and source_lower.startswith("blob:"):
                return True

            # 호스트 소스 매칭
            if self._match_host_source(source_lower, value_lower):
                return True

        return False

    def _match_host_source(self, source: str, pattern: str) -> bool:
        """호스트 소스 패턴 매칭"""
        # 프로토콜 제거
        source_host = source
        if "://" in source:
            source_host = source.split("://", 1)[1].split("/")[0]

        pattern_host = pattern
        if "://" in pattern:
            pattern_host = pattern.split("://", 1)[1].split("/")[0]

        # 정확히 일치
        if source_host == pattern_host:
            return True

        # 와일드카드 매칭 (*.example.com)
        if pattern_host.startswith("*."):
            domain = pattern_host[2:]
            if source_host == domain or source_host.endswith("." + domain):
                return True

        return False

    def allows_script(self, source: str) -> bool:
        """스크립트 소스 허용 여부"""
        return self.allows_source("script-src", source)

    def allows_style(self, source: str) -> bool:
        """스타일 소스 허용 여부"""
        return self.allows_source("style-src", source)

    def allows_image(self, source: str) -> bool:
        """이미지 소스 허용 여부"""
        return self.allows_source("img-src", source)

    def allows_connect(self, source: str) -> bool:
        """연결(fetch/XHR) 소스 허용 여부"""
        return self.allows_source("connect-src", source)

    def allows_frame(self, source: str) -> bool:
        """프레임 소스 허용 여부"""
        return self.allows_source("frame-src", source)

    def allows_inline_script(self) -> bool:
        """인라인 스크립트 허용 여부"""
        return self.allows_source("script-src", "inline")

    def allows_inline_style(self) -> bool:
        """인라인 스타일 허용 여부"""
        return self.allows_source("style-src", "inline")

    def allows_eval(self) -> bool:
        """eval() 허용 여부"""
        return self.allows_source("script-src", "eval")

    def __repr__(self):
        return f"ContentSecurityPolicy({self.directives})"
