"""Base URL class"""
from abc import ABC, abstractmethod
from fake_useragent import UserAgent


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
        elif self.schema == "file":
            return f"{self.schema}://{self.path}"
        return f"{self.schema}://{self.host}{port_part}{self.path}"

    def _parse_host_and_path(self, raw):
        # host / path parsing
        if "/" not in raw:
            raw += "/"

        self.host, path = raw.split("/", 1)
        self.path = "/" + path

        # Optional port
        if ":" in self.host and not self.__class__.__name__ == 'FileURL':
            self.host, port = self.host.split(":", 1)
            self.port = int(port)

    def origin(self):
        if self.port is None:
            return f"{self.schema}://{self.host}"
        else:
            return f"{self.schema}://{self.host}:{self.port}"

    @abstractmethod
    def request(self, referrer=None, payload=None):
        pass
