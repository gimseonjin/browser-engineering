import socket
import ssl
import time
import gzip
from abc import ABC, abstractmethod
from fake_useragent import UserAgent


class CacheManager:
    def __init__(self):
        self._cache = {}
    
    def get(self, url_str):
        """캐시에서 조회"""
        if url_str not in self._cache:
            return None
        
        status, headers, body, expires_at = self._cache[url_str]
        
        # 만료 체크
        if time.time() >= expires_at:
            del self._cache[url_str]
            return None
        
        return status, headers, body
    
    def set(self, url_str, status, headers, body):
        """캐시 저장"""
        cache_control = headers.get("cache-control", "").lower()
        
        # no-store면 저장 안 함
        if "no-store" in cache_control:
            return
        
        # max-age 파싱
        max_age = None
        for directive in cache_control.split(","):
            directive = directive.strip()
            if directive.startswith("max-age="):
                max_age = int(directive.split("=", 1)[1])
                break
        
        # max-age가 없으면 저장 안 함
        if max_age is None:
            return
        
        expires_at = time.time() + max_age
        self._cache[url_str] = (status, headers, body, expires_at)


# 전역 캐시 매니저
_cache_manager = CacheManager()


class URL(ABC):
    def __init__(self, raw_schema, raw_url):
        self.schema = raw_schema
        self.raw_url = raw_url
        self.host = None
        self.path = "/"
        self.port = None
        self.user_agent = UserAgent().random

        self._parse_host_and_path(raw_url)

    def __str__(self):
        port_part = ":" + str(self.port)
        if self.schema == "https" and self.port == 443:
            port_part = ""
        elif self.schema == "http" and self.port == 80:
            port_part = ""
        return f"{self.schema}://{self.host}{port_part}{self.path}"

    def _parse_host_and_path(self, raw):
        # host / path parsing
        if "/" not in raw:
            raw += "/"

        self.host, path = raw.split("/", 1)
        self.path = "/" + path

        # Optional port
        if ":" in self.host and not isinstance(self, FileURL):
            self.host, port = self.host.split(":", 1)
            self.port = int(port)

    @abstractmethod
    def request(self):
        pass


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

    def _send_http_request(self, s):
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}\r\n"
            f"User-Agent: {self.user_agent}\r\n"
            f"Connection: keep-alive\r\n"
            f"Accept-Encoding: gzip\r\n"
            f"\r\n"
        )
        s.send(req.encode("utf-8"))

    def _get_socket_key(self):
        return (self.schema, self.host, self.port)
    
    def _get_socket(self):
        key = self._get_socket_key()
        return self._socket_map.get(key)
    
    def _set_socket(self, s):
        key = self._get_socket_key()
        self._socket_map[key] = s
    
    def _remove_socket(self):
        key = self._get_socket_key()
        self._socket_map.pop(key, None)

    def _read_http_response(self, s: socket.socket):
        response = s.makefile("rb")  # 바이너리 모드로 읽기

        # status line
        status_line = response.readline().decode("utf-8")
        version, status, explanation = status_line.split(" ", 2)
        
        # headers
        headers = {}
        while True:
            line = response.readline().decode("utf-8")
            if line == "\r\n":
                break
            h, v = line.split(":", 1)
            headers[h.casefold()] = v.strip()

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
        
        return int(status), headers, body

class HTTPURL(HTTPBase):
    def __init__(self, schema, raw_url):
        super().__init__(schema, raw_url)
        if self.port is None:
            self.port = 80

    def request(self):
        url_str = f"{self.schema}://{self.raw_url}"
        
        # 캐시 확인
        cached = _cache_manager.get(url_str)
        if cached:
            return cached
        
        # 소켓 맵에서 가져오거나 새로 생성
        s = self._get_socket()
        if s is None:
            s = self._open_socket()
            s.connect((self.host, self.port))
            self._set_socket(s)
        
        self._send_http_request(s)
        status, headers, body = self._read_http_response(s)
        
        # 캐시 저장
        _cache_manager.set(url_str, status, headers, body)
        
        return status, headers, body

class HTTPSURL(HTTPBase):
    def __init__(self, schema, raw_url):
        super().__init__(schema, raw_url)
        if self.port is None:
            self.port = 443

    def request(self):
        url_str = f"{self.schema}://{self.raw_url}"
        
        # 캐시 확인
        cached = _cache_manager.get(url_str)
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
        
        self._send_http_request(s)
        status, headers, body = self._read_http_response(s)
        
        # 캐시 저장
        _cache_manager.set(url_str, status, headers, body)
        
        return status, headers, body


class FileURL(URL):
    def __init__(self, schema, raw_url):
        super().__init__(schema, raw_url)
        self.port = None  # not used

    def request(self):
        with open(self.path, "r") as f:
            body = f.read()
            return 200, {}, body


class AboutBlankURL(URL):
    def __init__(self, schema, raw_url):
        super().__init__(schema, raw_url)
        self.port = None  # not used

    def request(self):
        return 200, {}, ""


class URLFactory:
    @staticmethod
    def parse(url: str) -> URL:
        # about:blank 처리
        if url == "about:blank":
            return AboutBlankURL("about", "blank")
        
        schema, rest = url.split("://", 1)

        if schema == "http":
            return HTTPURL(schema, rest)
        elif schema == "https":
            return HTTPSURL(schema, rest)
        elif schema == "file":
            return FileURL(schema, rest)
        else:
            raise ValueError(f"Unsupported schema: {schema}")
    
    @staticmethod
    def resolve(current_url: URL, url: dict) -> URL:
        """상대 경로를 절대 URL 객체로 변환"""
        # 딕셔너리에서 href 값을 추출
        url = url.get("href", "")
        
        # 절대 URL인 경우 (스킴이 있는 경우) 그대로 파싱하여 반환
        if "://" in url:
            return URLFactory.parse(url)
        
        # 상대 경로 처리: ../ 처리
        if not url.startswith("/"):
            dir, _ = current_url.path.rsplit("/", 1)
            while url.startswith("../"):
                _, url = url.split("/", 1)
                if "/" in dir:
                    dir, _ = dir.rsplit("/", 1)
            url = dir + "/" + url
        
        # 기본 포트는 생략 (HTTP: 80, HTTPS: 443)
        default_ports = {"http": 80, "https": 443}
        default_port = default_ports.get(current_url.schema)
        
        if default_port and current_url.port == default_port:
            url_str = current_url.schema + "://" + current_url.host + url
        else:
            url_str = current_url.schema + "://" + current_url.host + \
                     ":" + str(current_url.port) + url
        
        return URLFactory.parse(url_str)

    @staticmethod
    def resolve_str(current_url: URL, url: str) -> str:
        """상대 경로를 절대 URL 문자열로 변환"""
        # 절대 URL인 경우 (스킴이 있는 경우) 그대로 반환
        if "://" in url:
            return url
        
        if not url.startswith("/"):
            dir, _ = current_url.path.rsplit("/", 1)
            while url.startswith("../"):
                _, url = url.split("/", 1)
                if "/" in dir:
                    dir, _ = dir.rsplit("/", 1)
            url = dir + "/" + url
        
        # 기본 포트는 생략 (HTTP: 80, HTTPS: 443)
        default_ports = {"http": 80, "https": 443}
        default_port = default_ports.get(current_url.schema)
        
        if default_port and current_url.port == default_port:
            url_str = current_url.schema + "://" + current_url.host + url
        else:
            url_str = current_url.schema + "://" + current_url.host + \
                     ":" + str(current_url.port) + url
        
        return url_str