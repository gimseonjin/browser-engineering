import os
from .base_url import URL
from .http_url import HTTPURL
from .https_url import HTTPSURL
from .file_url import FileURL
from .about_blank_url import AboutBlankURL


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
        # 딕셔너리에서 href 또는 src 값을 추출
        url = url.get("href", url.get("src", ""))
        
        # 절대 URL인 경우 (스킴이 있는 경우) 그대로 파싱하여 반환
        if "://" in url:
            return URLFactory.parse(url)
        
        # file URL의 경우 특별 처리
        if current_url.schema == "file":
            # 파일 URL에서 상대 경로는 현재 파일의 디렉토리 기준
            base_path = os.path.dirname(current_url.path)
            # 디렉토리가 없으면 현재 디렉토리 사용
            if not base_path:
                base_path = "."
            
            # 절대 경로가 아닌 경우
            if not url.startswith("/"):
                # ./ 제거
                if url.startswith("./"):
                    url = url[2:]
                # ../ 처리
                while url.startswith("../"):
                    _, url = url.split("/", 1)
                    base_path = os.path.dirname(base_path)
                    if not base_path:
                        base_path = "."
                # 경로를 정규화하여 생성
                full_path = os.path.normpath(os.path.join(base_path, url))
                url_str = "file://" + full_path
            else:
                # 절대 경로인 경우
                url_str = "file://" + url
        else:
            # HTTP/HTTPS URL 처리
            # 상대 경로 처리: ../ 처리
            if not url.startswith("/"):
                if "/" in current_url.path:
                    dir, _ = current_url.path.rsplit("/", 1)
                else:
                    dir = current_url.path
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
        
        # file URL의 경우 특별 처리
        if current_url.schema == "file":
            # 파일 URL에서 상대 경로는 현재 파일의 디렉토리 기준
            base_path = os.path.dirname(current_url.path)
            # 디렉토리가 없으면 현재 디렉토리 사용
            if not base_path:
                base_path = "."
            
            # 절대 경로가 아닌 경우
            if not url.startswith("/"):
                # ./ 제거
                if url.startswith("./"):
                    url = url[2:]
                # ../ 처리
                while url.startswith("../"):
                    _, url = url.split("/", 1)
                    base_path = os.path.dirname(base_path)
                    if not base_path:
                        base_path = "."
                # 경로를 정규화하여 생성
                full_path = os.path.normpath(os.path.join(base_path, url))
                url_str = "file://" + full_path
            else:
                # 절대 경로인 경우
                url_str = "file://" + url
        else:
            # HTTP/HTTPS URL 처리
            if not url.startswith("/"):
                if "/" in current_url.path:
                    dir, _ = current_url.path.rsplit("/", 1)
                else:
                    dir = current_url.path
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