from .base_url import URL


class FileURL(URL):
    def __init__(self, schema, raw_url):
        super().__init__(schema, raw_url)
        self.port = None  # not used

    def _parse_host_and_path(self, raw):
        # FileURL의 경우 raw_url이 바로 파일 경로
        self.host = None
        self.path = raw

    def request(self, referrer=None, payload=None):
        with open(self.path, "r") as f:
            body = f.read()
            return 200, {}, body, None