import socket
import urllib.parse
import random
import html

ENTRIES = [
    ('Pavel was here', 'admin'),
]
SESSIONS = {}

LOGINS = {
    "admin": "1234",
    "user": "1234",
}


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
            if "cookie" in headers:
                token = headers["cookie"].split("=")[1]
            else:
                token = str(random.random())[2:]

            session = SESSIONS.setdefault(token, {})
            print(session)
            status, body = do_request(session, method, path, headers, body)

            response = f"HTTP/1.1 {status}\r\n"
            response += f"Content-Length: {len(body)}\r\n"
            response += f"Connection: keep-alive\r\n"
            response += f"Content-Security-Policy: default-src http://localhost:8000\r\n"
            if "cookie" not in headers:
                response += f"Set-Cookie: token={token}; SameSite=Lax\r\n"
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

def do_request(session, method, path, headers, body):
    if method == "GET" and path == "/":
        return "200 OK", show_comments(session)

    elif method == "GET" and path == "/login":
        return "200 OK", login_form(session)

    elif method == "POST" and path == "/":
        print("do_login")
        params = form_decode(body)
        return do_login(session, params)

    elif method == "POST" and path == "/add":
        params = form_decode(body)
        add_entry(session, params)
        return "200 OK", show_comments(session)

    elif method == "GET" and path == "/comment.js":
        with open("comment.js", "r") as f:
            content = f.read()
            return "200 OK", content

    elif method == "GET" and path == "/comment.css":
        with open("comment.css", "r") as f:
            return "200 OK", f.read()
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

def add_entry(session, params):
    if "user" not in session: return
    if 'nonce' not in params or params['nonce'] != session['nonce']: return
    if 'guest' in params and len(params['guest']) <= 10:
        ENTRIES.append((params['guest'], session['user']))
    return show_comments(session)

def add_comment(params):
    if "guest" in params:
        ENTRIES.append(params["guest"])
    return show_comments()

def show_comments(session):
    out = "<!DOCTYPE html>"
    if "user" in session:
        nonce = str(random.random())[2:]
        session['nonce'] = nonce
        for entry, who in ENTRIES:
            out += f"<p>{html.escape(entry)}</p>"
            out += f"<p>by {html.escape(who)}</p>"
        out += "<form action=add method=post>"
        out +=   f"<input type=hidden name=nonce value={nonce}>"
        out +=   "<p><input name=guest></p>"
        out +=   "<p><button>Sign the book</button></p>"
        out +=   "<strong></strong>"
        out +=   "<script src=/comment.js></script>"
        out += "</form>"
        out += "<link rel=stylesheet href=/comment.css>"
    else:
        out += "<p>Please login to sign the book.</p>"
        out += "<a href=/login>Login</a>"
    return out

def not_found(url, method):
    out = "<!DOCTYPE html>"
    out += f"<p>The resource {url} was not found.</p>"
    out += f"<p>Method {method} is not supported.</p>"
    return out

def login_form(session):
    body = "<!DOCTYPE html>"
    body += "<form action=/ method=post>"
    body +=   "<p>Username: <input name=username></p>"
    body +=   "<p>Password: <input name=password></p>"
    body +=   "<p><button>Login</button></p>"
    body += "</form>"
    return body

def do_login(session, params):
    username = params['username']
    password = params['password']
    if username in LOGINS and LOGINS[username] == password:
        session['user'] = username
        return "200 OK", show_comments(session)
    else:
        return "401 Unauthorized", login_form(session)

while True:
    conx, addr = s.accept()
    handle_connection(conx)