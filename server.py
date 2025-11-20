import socket
import urllib.parse

ENTRIES = ['Pavel was here']

s = socket.socket(
    family=socket.AF_INET,
    type=socket.SOCK_STREAM,
    proto=socket.IPPROTO_TCP,
)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 8000))
s.listen()

def handle_connection(conx):
    try:
        while True:  # keep-alive를 위한 루프
            req = conx.makefile("rb")
            reqline = req.readline().decode("utf-8")
            
            if not reqline.strip():  # 연결이 닫혔으면 종료
                break
                
            method, path, version = reqline.split(" ", 2)
            assert method in ["GET", "POST"]

            headers = {}
            while True:
                line = req.readline().decode("utf-8")
                if line == "\r\n": break
                h, v = line.split(":", 1)
                headers[h.casefold()] = v.strip()

            if 'content-length' in headers:
                length = int(headers['content-length'])
                body = req.read(length).decode("utf-8")
            else:
                body = None
            
            print(method, path, headers, body)
            status, body = do_request(method, path, headers, body)

            response = f"HTTP/1.1 {status}\r\n"
            response += f"Content-Length: {len(body)}\r\n"
            response += f"Connection: keep-alive\r\n"
            response += f"\r\n" + body
            conx.send(response.encode("utf-8"))
            req.close()  # makefile 닫기
            
            # Connection: close 요청이 있으면 연결 종료
            if headers.get("connection", "").lower() == "close":
                break
                
    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        conx.close()

def do_request(method, path, headers, body):
    if path == "/":
        return "200 OK", show_comments()
    elif path == "/add":
        params = form_decode(body)
        return "200 OK", add_comment(params)
    else:
        return "404 Not Found", not_found(path, method)

def form_decode(body):
    params = {}
    for item in body.split("&"):
        k, v = item.split("=", 1)
        k = urllib.parse.unquote(k)
        v = urllib.parse.unquote(v)
        params[k] = v
    return params

def add_comment(params):
    if "guest" in params:
        ENTRIES.append(params["guest"])
    return show_comments()

def show_comments():
    out = "<!DOCTYPE html>"
    for entry in ENTRIES:
        out += f"<p>{entry}</p>"
    out += "<form action=add method=post>"
    out +=   "<p><input name=guest></p>"
    out +=   "<p><button>Sign the book</button></p>"
    out += "</form>"
    return out

def not_found(url, method):
    out = "<!DOCTYPE html>"
    out += f"<p>The resource {url} was not found.</p>"
    out += f"<p>Method {method} is not supported.</p>"
    return out

while True:
    conx, addr = s.accept()
    handle_connection(conx)