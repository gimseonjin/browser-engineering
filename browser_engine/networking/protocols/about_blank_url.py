"""about:blank URL implementation"""
from .base_url import URL


class AboutBlankURL(URL):
    def __init__(self, schema, raw_url):
        super().__init__(schema, raw_url)
        self.port = None  # not used

    def request(self, referrer=None, payload=None):
        return 200, {}, "", None
