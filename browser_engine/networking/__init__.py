"""
Networking package for browser engine

Subpackages:
- protocols: URL protocol implementations (HTTP, HTTPS, file, about:blank)
- security: Security components (CSP, cookies)
"""
# Re-export from protocols subpackage for backward compatibility
from .protocols import (
    URL,
    HTTPBase,
    HTTPURL,
    HTTPSURL,
    FileURL,
    AboutBlankURL,
    URLFactory,
)

# Re-export from security subpackage for backward compatibility
from .security import ContentSecurityPolicy, COOKIE_JAR

# Cache manager (not in subpackage as it's commonly used)
from .cache_manager import CacheManager, cache_manager

# Network thread
from .network_thread import (
    NetworkThread,
    NetworkRequest,
    NetworkResponse,
    RequestType,
    get_network_thread,
    shutdown_network_thread,
)

__all__ = [
    # Protocols
    'URL',
    'HTTPBase',
    'HTTPURL',
    'HTTPSURL',
    'FileURL',
    'AboutBlankURL',
    'URLFactory',
    # Security
    'ContentSecurityPolicy',
    'COOKIE_JAR',
    # Cache
    'CacheManager',
    'cache_manager',
    # Network thread
    'NetworkThread',
    'NetworkRequest',
    'NetworkResponse',
    'RequestType',
    'get_network_thread',
    'shutdown_network_thread',
]