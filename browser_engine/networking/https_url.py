import ssl
from .http_base import HTTPBase
from .cache_manager import cache_manager


class HTTPSURL(HTTPBase):
    def __init__(self, schema, raw_url):
        super().__init__(schema, raw_url)
        if self.port is None:
            self.port = 443

    def request(self, referrer=None, payload=None):
        url_str = f"{self.schema}://{self.raw_url}"

        # 캐시 확인
        cached = cache_manager.get(url_str)
        if cached:
            return cached

        # 소켓 맵에서 가져오거나 새로 생성
        s = self._get_socket()
        if s is None:
            s = self._open_socket()
            # SSL
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)
            s.connect((self.host, self.port))
            self._set_socket(s)

        self._send_http_request(s, referrer, payload)
        status, headers, body, csp = self._read_http_response(s, referrer, payload)

        # 서버가 Connection: close를 보내면 소켓 닫기
        if headers.get("connection", "").lower() == "close":
            s.close()
            self._remove_socket()

        # 캐시 저장
        cache_manager.set(url_str, status, headers, body, csp)

        return status, headers, body, csp