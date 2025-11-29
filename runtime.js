// ============================================
// Window 객체 및 프레임 계층 구조
// ============================================

// 모든 window 객체를 저장 (frame_id -> Window)
WINDOWS = {};

function Window(frame_id) {
    this._frame_id = frame_id;
    this._document = null;
    this._parent = null;
    this._top = null;
    this._frames = [];
    this._origin = null;
    this._name = "";

    // 전역 저장소에 등록
    WINDOWS[frame_id] = this;
}

// origin 설정 (Python에서 호출)
Window.prototype._setOrigin = function(origin) {
    this._origin = origin;
};

// parent 설정 (Python에서 호출)
Window.prototype._setParent = function(parent_frame_id) {
    if (parent_frame_id !== null && WINDOWS[parent_frame_id]) {
        this._parent = WINDOWS[parent_frame_id];
    }
};

// top 설정 (Python에서 호출)
Window.prototype._setTop = function(top_frame_id) {
    if (top_frame_id !== null && WINDOWS[top_frame_id]) {
        this._top = WINDOWS[top_frame_id];
    } else {
        this._top = this;  // 자기 자신이 top
    }
};

// 자식 프레임 추가 (Python에서 호출)
Window.prototype._addFrame = function(child_frame_id) {
    if (WINDOWS[child_frame_id]) {
        this._frames.push(WINDOWS[child_frame_id]);
    }
};

// same-origin 체크
Window.prototype._isSameOrigin = function(other_window) {
    if (!other_window || !other_window._origin) return false;
    return this._origin === other_window._origin;
};

// cross-origin 접근 시 에러 발생
Window.prototype._checkAccess = function(other_window, property) {
    if (!this._isSameOrigin(other_window)) {
        throw new Error("SecurityError: Blocked access to cross-origin frame");
    }
};

// parent 접근자
Object.defineProperty(Window.prototype, "parent", {
    get: function() {
        if (this._parent === null) return this;  // top-level은 자기 자신 반환
        // cross-origin이어도 parent 자체는 접근 가능 (제한된 속성만)
        return this._parent;
    }
});

// top 접근자
Object.defineProperty(Window.prototype, "top", {
    get: function() {
        return this._top || this;
    }
});

// frames 접근자 (HTMLCollection처럼 동작)
Object.defineProperty(Window.prototype, "frames", {
    get: function() {
        return this._frames;
    }
});

// length (frames 개수)
Object.defineProperty(Window.prototype, "length", {
    get: function() {
        return this._frames.length;
    }
});

// document 접근자 (same-origin만)
Object.defineProperty(Window.prototype, "document", {
    get: function() {
        return this._document;
    },
    set: function(doc) {
        this._document = doc;
    }
});

// name 속성
Object.defineProperty(Window.prototype, "name", {
    get: function() { return this._name; },
    set: function(val) { this._name = val; }
});

// postMessage (cross-origin 통신용)
Window.prototype.postMessage = function(message, targetOrigin) {
    // TODO: 메시지 이벤트 구현
    call_python("postMessage", this._frame_id, message, targetOrigin);
};

// 현재 활성 window (프레임별로 설정됨)
var window = null;

// window 초기화 함수 (Python에서 호출)
function __initWindow(frame_id) {
    window = new Window(frame_id);
    return window;
}

// window 가져오기
function __getWindow(frame_id) {
    return WINDOWS[frame_id] || null;
}

// ============================================
// Document 객체
// ============================================

function Document(frame_id) {
    this._frame_id = frame_id;
}

Document.prototype.querySelectorAll = function(s) {
    var nodes = call_python("querySelectorAll", this._frame_id, s);
    return nodes.map(function(handle) { return new Node(handle); });
};

Document.prototype.querySelector = function(s) {
    var nodes = this.querySelectorAll(s);
    return nodes.length > 0 ? nodes[0] : null;
};

// 전역 document 변수 (하위 호환성)
var document = null;

// document 초기화 (Python에서 호출)
function __initDocument(frame_id) {
    document = new Document(frame_id);
    if (window) {
        window._document = document;
    }
    return document;
}

// ============================================
// Console
// ============================================

console = {
    log: function(x) { call_python("log", x); },
    error: function(x) { call_python("log", "[ERROR] " + x); },
    warn: function(x) { call_python("log", "[WARN] " + x); }
};

// ============================================
// Node 객체
// ============================================

function Node(handle) { this.handle = handle; }

Node.prototype.getAttribute = function(name) {
    return call_python("getAttribute", this.handle, name);
};

// ============================================
// Event Listeners
// ============================================

LISTENERS = {};

Node.prototype.addEventListener = function(type, listener) {
    if (!LISTENERS[this.handle]) LISTENERS[this.handle] = {};
    var dict = LISTENERS[this.handle];
    if (!dict[type]) dict[type] = [];
    var list = dict[type];
    list.push(listener);
};

Node.prototype.removeEventListener = function(type, listener) {
    if (!LISTENERS[this.handle]) return;
    var dict = LISTENERS[this.handle];
    if (!dict[type]) return;
    var list = dict[type];
    var idx = list.indexOf(listener);
    if (idx > -1) list.splice(idx, 1);
};

Node.prototype.dispatchEvent = function(evt) {
    var type = evt.type;
    var handle = this.handle;
    var list = (LISTENERS[handle] && LISTENERS[handle][type]) || [];
    for (var i = 0; i < list.length; i++) {
        list[i].call(this, evt);
    }
    return evt.do_default;
};

Object.defineProperty(Node.prototype, "innerHTML", {
    set: function(value) {
        call_python("innerHTML_set", this.handle, value.toString());
    }
});

// ============================================
// Event 객체
// ============================================

function Event(type) {
    this.type = type;
    this.do_default = true;
    this.target = null;
    this.currentTarget = null;
}

Event.prototype.preventDefault = function() {
    this.do_default = false;
};

Event.prototype.stopPropagation = function() {
    // TODO: 이벤트 전파 중단
};

// MessageEvent (postMessage용)
function MessageEvent(type, data, origin, source) {
    Event.call(this, type);
    this.data = data;
    this.origin = origin;
    this.source = source;
}
MessageEvent.prototype = Object.create(Event.prototype);

// ============================================
// setTimeout / setInterval
// ============================================

SET_TIMEOUT_REQUESTS = {};

function setTimeout(callback, time_delta) {
    var handle = Object.keys(SET_TIMEOUT_REQUESTS).length;
    SET_TIMEOUT_REQUESTS[handle] = callback;
    call_python("setTimeout", handle, time_delta || 0);
    return handle;
}

function clearTimeout(handle) {
    delete SET_TIMEOUT_REQUESTS[handle];
}

function __runSetTimeout(handle) {
    var callback = SET_TIMEOUT_REQUESTS[handle];
    if (callback) {
        delete SET_TIMEOUT_REQUESTS[handle];
        callback();
    }
}

// ============================================
// XMLHttpRequest
// ============================================

XHR_REQUESTS = {};

function XMLHttpRequest() {
    this.handle = Object.keys(XHR_REQUESTS).length;
    XHR_REQUESTS[this.handle] = this;
    this.readyState = 0;
    this.status = 0;
    this.responseText = "";
}

XMLHttpRequest.prototype.open = function(method, url, is_async) {
    this.is_async = is_async !== false;  // 기본값 true
    this.method = method;
    this.url = url;
    this.readyState = 1;
};

XMLHttpRequest.prototype.send = function(data) {
    var frame_id = window ? window._frame_id : 0;
    this.responseText = call_python("XMLHttpRequest_send", frame_id, this.method, this.url, data, this.is_async, this.handle);
};

function __runXHROnload(body, handle) {
    var obj = XHR_REQUESTS[handle];
    if (obj) {
        obj.readyState = 4;
        obj.status = 200;
        obj.responseText = body;
        var evt = new Event("load");
        if (obj.onload) obj.onload(evt);
    }
}

// ============================================
// Location 객체
// ============================================

function Location(frame_id) {
    this._frame_id = frame_id;
}

Object.defineProperty(Location.prototype, "href", {
    get: function() {
        return call_python("getLocationHref", this._frame_id);
    },
    set: function(url) {
        call_python("setLocationHref", this._frame_id, url);
    }
});

// window.location 추가
Object.defineProperty(Window.prototype, "location", {
    get: function() {
        if (!this._location) {
            this._location = new Location(this._frame_id);
        }
        return this._location;
    }
});
