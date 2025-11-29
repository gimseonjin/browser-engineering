import socket
import gzip
from .base_url import URL
from .cookie_jar import COOKIE_JAR
from .csp import ContentSecurityPolicy


class HTTPBase(URL):
    _socket_map = {}  # (schema, host, port) -> socket
    
    def __init__(self, raw_schema, raw_url):
        super().__init__(raw_schema, raw_url)

    def _open_socket(self):
        """HTTP 와 HTTPS 공통 소켓 생성"""
        s = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
        return s

    def _send_http_request(self, s, referrer=None, payload=None):
        method = "POST" if payload else "GET"
        req = (
            f"{method} {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}\r\n"
            f"User-Agent: {self.user_agent}\r\n"
            f"Connection: keep-alive\r\n"
            f"Accept-Encoding: gzip\r\n"
        )
        if referrer:
            req += f"Referer: {referrer}\r\n"
        if self.host in COOKIE_JAR:
            cookie, params = COOKIE_JAR[self.host]

            allow_cookie = True
            if referrer and params.get("samesite", "none") == "lax":
                if method != "GET":
                    allow_cookie = self.host == referrer.host
            if allow_cookie:
                req += f"Cookie: {cookie}\r\n"
                
        if payload:
            req += f"Content-Type: application/x-www-form-urlencoded\r\n"
            req += f"Content-Length: {len(payload.encode('utf-8'))}\r\n"
            req += f"\r\n"
            req += payload
        else:
            req += f"\r\n"
        s.send(req.encode("utf-8"))

    def _get_socket_key(self):
        return (self.schema, self.host, self.port)
    
    def _get_socket(self):
        key = self._get_socket_key()
        s = self._socket_map.get(key)
        if s and s.fileno() == -1:  # 소켓이 닫혔는지 확인
            self._socket_map.pop(key, None)
            return None
        return s
    
    def _set_socket(self, s):
        key = self._get_socket_key()
        self._socket_map[key] = s
    
    def _remove_socket(self):
        key = self._get_socket_key()
        self._socket_map.pop(key, None)

    def _read_http_response(self, s: socket.socket, referrer=None, payload=None):
        response = s.makefile("rb")  # 바이너리 모드로 읽기

        # status line
        status_line = response.readline().decode("utf-8")
        
        # 빈 줄이나 연결이 끊긴 경우 처리
        if not status_line or status_line.strip() == "":
            response.close()
            s.close()
            self._remove_socket()
            # 새 연결로 재시도
            s = self._open_socket()
            s.connect((self.host, self.port))
            self._set_socket(s)
            self._send_http_request(s, referrer, payload)
            response = s.makefile("rb")
            status_line = response.readline().decode("utf-8")
        
        status_parts = status_line.split(" ", 2)
        if len(status_parts) != 3:
            raise ValueError(f"Invalid HTTP status line: {repr(status_line)}")
        version, status, explanation = status_parts
        
        # headers
        headers = {}
        while True:
            line = response.readline().decode("utf-8")
            if line == "\r\n":
                break
            h, v = line.split(":", 1)
            headers[h.casefold()] = v.strip()

        # Set-Cookie 처리 (Body 읽기 전에 처리)
        if "set-cookie" in headers:
            cookie = headers["set-cookie"]
            params = {}
            if ';' in cookie:
                cookie, rest = cookie.split(";", 1)
                for param in rest.split(";"):
                    if '=' in param:
                        param, value = param.split("=", 1)
                    else:
                        value = "true"
                    params[param.strip().casefold()] = value.casefold()
            COOKIE_JAR[self.host] = (cookie, params)

        # Body 읽기
        if headers.get("transfer-encoding", "").lower() == "chunked":
            # Chunked transfer encoding
            body_bytes = b""
            while True:
                chunk_size_line = response.readline().decode("utf-8").strip()
                chunk_size = int(chunk_size_line, 16)  # 16진수로 파싱

                if chunk_size == 0:
                    response.readline()  # 마지막 \r\n 읽기
                    break

                chunk_data = response.read(chunk_size)
                body_bytes += chunk_data
                response.readline()  # \r\n 읽기

            body = body_bytes
        elif "content-length" in headers:
            # Content-Length가 있으면 정확히 그만큼만 읽기
            content_length = int(headers["content-length"])
            body = response.read(content_length)
        else:
            # 둘 다 없으면 끝까지 읽기
            body = response.read()
        
        # makefile 닫기 (소켓 재사용을 위해 필수)
        response.close()
        
        # gzip 압축 해제
        if headers.get("content-encoding", "").lower() == "gzip":
            body = gzip.decompress(body)
        
        # 바이트를 문자열로 변환
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="ignore")
        
        # 서버가 Connection: close를 보내면 소켓 닫기
        if headers.get("connection", "").lower() == "close":
            s.close()
            self._remove_socket()

        # CSP 헤더 파싱
        csp = None
        csp_header = headers.get("content-security-policy")
        if csp_header:
            csp = ContentSecurityPolicy(csp_header)

        return int(status), headers, body, csp