import time


class CacheManager:
    def __init__(self):
        self._cache = {}
    
    def get(self, url_str):
        """캐시에서 조회"""
        if url_str not in self._cache:
            return None

        status, headers, body, csp, expires_at = self._cache[url_str]

        # 만료 체크
        if time.time() >= expires_at:
            del self._cache[url_str]
            return None

        return status, headers, body, csp

    def set(self, url_str, status, headers, body, csp=None):
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
        self._cache[url_str] = (status, headers, body, csp, expires_at)


# 전역 캐시 매니저
cache_manager = CacheManager()