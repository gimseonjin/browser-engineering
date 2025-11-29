#!/usr/bin/env python3
"""
Browser Practice - 웹 브라우저 구현 (SDL + Skia)
사용법: python main.py <URL>
예시: python main.py https://example.com
"""
import sys
from browser_engine import Browser


def main():
    if len(sys.argv) < 2:
        url = "about:blank"
    else:
        url = sys.argv[1]

    browser = Browser()
    browser.new_tab(url)
    browser.run()


if __name__ == "__main__":
    main()