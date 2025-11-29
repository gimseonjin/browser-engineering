# Browser Practice - 웹 브라우저 구현

Python으로 구현한 멀티스레드 웹 브라우저입니다. 브라우저의 내부 동작 원리를 이해하기 위한 교육용 프로젝트입니다.

## 프로젝트 소개

[Web Browser Engineering](https://browser.engineering/) 책을 기반으로 브라우저를 직접 구현하면서 웹 기술의 핵심 개념을 학습했습니다.

### 학습 목표

```mermaid
mindmap
  root((Browser<br/>학습))
    스레드 아키텍처
      Browser Thread
      Main Thread
      Compositor Thread
      Network Thread
      Queue 기반 통신
    웹 보안
      Same-Origin Policy
      Frame/Window 계층
      CSP
      Cookie SameSite
    렌더링 파이프라인
      HTML/CSS 파싱
      DOM Tree
      Layout
      Paint
      Raster/Composite
    네트워킹
      HTTP/HTTPS
      Connection Pool
      Cache
```

### 주요 학습 내용

| 분야 | 학습 내용 | 관련 파일 |
|------|----------|-----------|
| **스레드** | Chrome 스타일 멀티스레드 아키텍처, Queue 기반 IPC | `threads/`, `core/browser.py` |
| **보안** | SOP, CSP, iframe 보안, Cookie 정책 | `networking/security/`, `scripting/js_context.py` |
| **렌더링** | DOM → Style → Layout → Paint → Composite | `layout/`, `rendering/`, `css/` |
| **JS 엔진** | DOM 바인딩, 이벤트, XHR, setTimeout | `scripting/`, `runtime.js` |

## 실행 방법

```bash
python main.py <URL>
python main.py https://example.com
python server.py  # 테스트 서버
```

---

# Part 1: 전체 구조

## 시스템 아키텍처 개요

```mermaid
graph TB
    subgraph "Browser Application"
        subgraph UI["User Interface"]
            Window[SDL Window]
            Chrome[Chrome UI<br/>주소창, 탭바]
        end

        subgraph Engine["Browser Engine"]
            Tab[Tab Manager]
            Frame[Frame/DOM]
            Layout[Layout Engine]
            JS[JavaScript Engine]
        end

        subgraph Render["Rendering Engine"]
            Paint[Paint]
            Raster[Raster - Skia]
            Composite[Compositor]
        end

        subgraph Net["Network"]
            HTTP[HTTP/HTTPS]
            Cache[Cache]
            Cookie[Cookie Jar]
        end
    end

    Window --> Tab
    Tab --> Frame
    Frame --> Layout --> Paint --> Raster --> Composite --> Window
    Frame --> JS
    Frame --> HTTP
    HTTP --> Cache
    HTTP --> Cookie
```

## 데이터 흐름 요약

```mermaid
flowchart LR
    URL[URL 입력] --> Network[Network<br/>HTML 다운로드]
    Network --> Parse[Parse<br/>DOM Tree]
    Parse --> Style[Style<br/>CSS 적용]
    Style --> Layout[Layout<br/>위치/크기 계산]
    Layout --> Paint[Paint<br/>Draw 명령 생성]
    Paint --> Raster[Raster<br/>픽셀 변환]
    Raster --> Display[Display<br/>화면 출력]
```

## 클래스 다이어그램 (Core)

```mermaid
classDiagram
    class Browser {
        -tabs: List~Tab~
        -active_tab: Tab
        -main_threads: Dict
        -commit_queue: Queue
        -compositor: CompositorThread
        +new_tab(url)
        +run()
        +handle_click()
        +process_commits()
    }

    class Tab {
        -root_frame: Frame
        -frames: List~Frame~
        -scroll: float
        -history: List~str~
        -task_runner: TaskRunner
        +load(url)
        +render()
        +click(e)
    }

    class Frame {
        -url: BaseURL
        -nodes: Element
        -document: DocumentLayout
        -rules: List
        -js_context: JSContext
        -csp: CSP
        -child_frames: List~Frame~
        -parent_frame: Frame
        +load(url)
        +render()
        +dispatch_event()
    }

    class JSContext {
        -frame: Frame
        -frame_id: int
        -interp: dukpy
        -node_to_handle: Dict
        +run(script, code)
        +querySelectorAll()
        +XMLHttpRequest_send()
        +is_same_origin()
    }

    Browser "1" --> "*" Tab
    Tab "1" --> "1..*" Frame
    Frame "1" --> "0..1" JSContext
    Frame "1" --> "*" Frame : child_frames
```

## 페이지 로드 전체 시퀀스

```mermaid
sequenceDiagram
    participant User
    participant BT as BrowserThread
    participant MT as MainThread
    participant Frame
    participant Net as NetworkThread
    participant JS as JSContext
    participant CT as CompositorThread

    User->>BT: URL 입력 + Enter
    BT->>MT: Event(LOAD, url)

    rect rgb(200, 230, 200)
        Note over Frame: Loading Phase
        MT->>Frame: load(url)
        Frame->>Net: request_sync(HTML)
        Net-->>Frame: HTML body
        Frame->>Frame: HTMLParser.parse()
        Frame->>Net: request(CSS files)
        Net-->>Frame: stylesheets
    end

    rect rgb(230, 230, 200)
        Note over Frame: Rendering Phase
        Frame->>Frame: style()
        Frame->>Frame: layout()
        Frame->>Frame: paint()
    end

    rect rgb(200, 200, 230)
        Note over JS: Scripting Phase
        Frame->>Net: request(JS files)
        Net-->>Frame: scripts
        Frame->>JS: JSContext.run()
        JS->>JS: Execute
        JS-->>Frame: DOM changes?
    end

    Frame->>Frame: _load_iframes()
    Note over Frame: 각 iframe에 대해 재귀적 load

    MT->>BT: CommitData
    BT->>CT: CompositorData
    CT->>CT: Raster → Composite → Blit
    CT-->>User: 화면 출력
```

## 프로젝트 구조

```
browser_engine/
├── core/           # Browser 메인 루프
├── content/        # Tab, Frame (문서 관리)
├── threads/        # MainThread, CompositorThread
├── networking/     # NetworkThread, URL 프로토콜
│   ├── protocols/  # HTTP, HTTPS, File, AboutBlank
│   └── security/   # CSP, Cookie
├── scripting/      # JSContext (dukpy)
├── layout/         # DocumentLayout, BlockLayout...
├── rendering/      # DrawText, DrawRect...
├── css/            # CSS 파싱, 스타일 적용
├── dom/            # Element, Text, HTMLParser
└── profiling/      # 성능 측정 (trace.json)
```

---

# Part 2: 스레드 아키텍처

## 전체 스레드 구조

Chrome과 유사한 멀티스레드 아키텍처를 구현합니다.

```mermaid
graph TB
    subgraph "Process (Python)"
        subgraph BT["🔵 Browser Thread"]
            SDL["SDL Event Loop<br/>(유저 입력)"]
            Chrome["Chrome UI<br/>(주소창, 탭바)"]
            CommitRecv["Commit 수신<br/>(commit_queue)"]
        end

        subgraph MT["🟢 MainThread (Tab별)"]
            EventQ["Event Queue"]
            Frame["Frame 로딩"]
            JS["JavaScript<br/>(dukpy)"]
            Layout["Layout/Paint"]
            TaskRunner["TaskRunner<br/>(비동기 콜백)"]
        end

        subgraph CT["🟡 CompositorThread"]
            DataQ["Data Queue"]
            Raster["Raster<br/>(Skia Surface)"]
            Composite["Composite<br/>(레이어 합성)"]
            Blit["Blit<br/>(SDL Texture)"]
        end

        subgraph NT["🔴 NetworkThread"]
            ReqQ["Request Queue"]
            Pool["ThreadPoolExecutor"]
            W1["Worker"]
            W2["Worker"]
            W3["Worker"]
            W4["Worker"]
        end
    end

    SDL -->|"Event(CLICK, LOAD...)"| EventQ
    Frame -->|"request_sync/async"| ReqQ
    Layout -->|"CommitData"| CommitRecv
    CommitRecv -->|"CompositorData"| DataQ
    Pool --> W1 & W2 & W3 & W4

    style BT fill:#e3f2fd
    style MT fill:#e8f5e9
    style CT fill:#fff9c4
    style NT fill:#ffebee
```

## 왜 스레드를 분리하는가?

```mermaid
graph LR
    subgraph "❌ 단일 스레드 (blocking)"
        A1[유저 클릭] --> A2[네트워크 요청<br/>3초 대기...] --> A3[파싱] --> A4[렌더링] --> A5[화면 출력]
    end
```

```mermaid
graph LR
    subgraph "✅ 멀티 스레드 (non-blocking)"
        B1[유저 클릭]
        B2[네트워크<br/>백그라운드]
        B3[렌더링 계속]
        B4[60fps 유지]

        B1 --> B2
        B1 --> B3
        B3 --> B4
    end
```

| 스레드 | 역할 | 블로킹 시 문제 |
|--------|------|---------------|
| **Browser Thread** | SDL 이벤트, UI 반응 | 클릭/스크롤 무응답 |
| **MainThread** | DOM, JS, Layout | 페이지 먹통 |
| **CompositorThread** | 픽셀 렌더링 | 화면 멈춤 |
| **NetworkThread** | HTTP 요청 | 모든 로딩 지연 |

## 스레드 간 통신 방식

```mermaid
sequenceDiagram
    box Browser Thread
        participant BT as Browser
    end
    box MainThread (Tab)
        participant MT as Main
        participant Tab
    end
    box CompositorThread
        participant CT as Compositor
    end

    Note over BT,CT: Queue 기반 비동기 통신

    BT->>MT: event_queue.put(Event)
    Note right of BT: LOAD, CLICK, SCROLL...

    MT->>Tab: handle event
    Tab->>Tab: render()

    MT->>BT: commit_queue.put(CommitData)
    Note left of MT: display_list, scroll, url

    BT->>CT: data_queue.put(CompositorData)
    Note right of BT: chrome_cmds, tab_cmds

    CT->>CT: raster → composite → blit
```

## MainThread 이벤트 루프 상세

```mermaid
flowchart TB
    subgraph "MainThread.run()"
        Start([시작]) --> CheckEvent{event_queue<br/>비어있음?}

        CheckEvent -->|No| GetEvent[event = queue.get]
        GetEvent --> HandleEvent[_handle_event]

        HandleEvent --> |LOAD| Load[tab.load url]
        HandleEvent --> |CLICK| Click[tab.click]
        HandleEvent --> |SCROLL| Scroll[tab.scroll]
        HandleEvent --> |KEYPRESS| Key[tab.keypress]

        Load & Click & Scroll & Key --> CheckRender

        CheckEvent -->|Yes| RunTasks[task_runner.run]
        RunTasks --> CheckRender

        CheckRender{needs_render?}
        CheckRender -->|Yes| Render[tab.render]
        Render --> Commit[_commit]
        Commit --> CheckEvent

        CheckRender -->|No| CheckEvent
    end
```

## CommitData & CompositorData 구조

```mermaid
classDiagram
    class CommitData {
        +display_list: List[DrawCmd]
        +document_height: float
        +scroll: float
        +url: str
        +tab_id: int
    }

    class CompositorData {
        +display_list: List[DrawCmd]
        +chrome_commands: List[DrawCmd]
        +scroll: float
        +document_height: float
        +chrome_height: float
        +width: int
        +height: int
        +chrome_changed: bool
        +tab_changed: bool
    }

    class DrawCmd {
        <<interface>>
        +rect: Rect
        +execute(scroll, canvas)
    }

    class DrawText {
        +x, y: float
        +text: str
        +font: Font
        +color: str
    }

    class DrawRect {
        +x1, y1, x2, y2: float
        +color: str
    }

    CommitData --> DrawCmd
    CompositorData --> DrawCmd
    DrawCmd <|-- DrawText
    DrawCmd <|-- DrawRect
```

## Compositor 렌더링 파이프라인

```mermaid
flowchart LR
    subgraph "Raster Phase"
        DL[Display List] --> CS[Chrome Surface<br/>Skia]
        DL --> TS[Tab Surface<br/>Skia]
    end

    subgraph "Composite Phase"
        CS --> RS[Root Surface]
        TS -->|scroll 적용| RS
    end

    subgraph "Blit Phase"
        RS --> Pixels[Pixel Buffer]
        Pixels --> SDL[SDL Texture]
        SDL --> Present[SDL_RenderPresent]
    end
```

---

# Part 3: 프레임 & 윈도우 보안

## Frame 계층 구조

```mermaid
graph TB
    subgraph "Tab"
        RF[Root Frame<br/>https://a.com]

        subgraph "iframes"
            IF1[Child Frame 1<br/>https://a.com/page]
            IF2[Child Frame 2<br/>https://b.com]
            IF3[Nested Frame<br/>https://c.com]
        end

        RF --> IF1
        RF --> IF2
        IF2 --> IF3
    end

    style RF fill:#90EE90
    style IF1 fill:#90EE90
    style IF2 fill:#FFB6C1
    style IF3 fill:#FFD700
```

## Window 객체 계층

```mermaid
classDiagram
    class Window {
        +_frame_id: int
        +_origin: string
        +_parent: Window
        +_top: Window
        +_frames: Window[]
        +_document: Document
        +postMessage(msg, targetOrigin)
        +_isSameOrigin(other) bool
        +_checkAccess(other, property)
    }

    class Document {
        +_frame_id: int
        +querySelectorAll(selector)
        +querySelector(selector)
    }

    Window "1" --> "1" Document : contains
    Window "1" --> "*" Window : frames
    Window --> Window : parent
    Window --> Window : top
```

## Same-Origin Policy (SOP)

### Origin이란?

```
https://www.example.com:443/path/page.html
└─┬──┘ └───────┬───────┘└┬┘
scheme       host      port

Origin = scheme + host + port
```

```mermaid
graph LR
    subgraph "Same Origin ✅"
        A1["https://a.com/page1"]
        A2["https://a.com/page2"]
        A3["https://a.com:443/other"]
    end

    subgraph "Different Origin ❌"
        B1["http://a.com"]
        B2["https://b.com"]
        B3["https://a.com:8080"]
    end

    A1 <-->|"접근 가능"| A2
    A2 <-->|"접근 가능"| A3

    A1 x-.-x|"차단"| B1
    A1 x-.-x|"차단"| B2
    A1 x-.-x|"차단"| B3
```

### SOP 적용 범위

```mermaid
flowchart TB
    subgraph "Same-Origin이면 허용"
        DOM["DOM 접근<br/>iframe.contentDocument"]
        Cookie["Cookie 읽기"]
        Storage["localStorage/sessionStorage"]
        XHR["XMLHttpRequest"]
    end

    subgraph "Cross-Origin도 허용"
        Embed["리소스 임베드<br/>img, script, css"]
        Form["폼 제출"]
        Link["링크 이동"]
        PostMsg["postMessage"]
    end

    subgraph "항상 차단"
        Read["Cross-origin 응답 읽기<br/>(CORS 없이)"]
    end
```

## Cross-Origin 접근 시퀀스

```mermaid
sequenceDiagram
    participant Parent as Parent Frame<br/>(https://a.com)
    participant Child as Child Frame<br/>(https://b.com)
    participant JSCtx as JSContext

    Note over Parent,Child: ❌ Cross-Origin DOM 접근 시도

    Parent->>JSCtx: iframe.contentDocument
    JSCtx->>JSCtx: is_same_origin(a.com, b.com)?
    JSCtx-->>Parent: SecurityError!

    Note over Parent,Child: ✅ postMessage는 허용

    Parent->>JSCtx: iframe.postMessage("hi", "*")
    JSCtx->>Child: MessageEvent(data="hi", origin="https://a.com")
    Child->>Child: event.origin 검증
    Child->>JSCtx: parent.postMessage("reply", "https://a.com")
    JSCtx->>Parent: MessageEvent(data="reply")
```

## window.parent / window.top 접근

```mermaid
flowchart TB
    subgraph "Frame 계층"
        Top["window (top)<br/>https://a.com"]
        Mid["iframe<br/>https://b.com"]
        Bot["nested iframe<br/>https://c.com"]

        Top --> Mid --> Bot
    end

    subgraph "Bot에서 접근 시"
        BotW["window"]
        BotP["window.parent<br/>(https://b.com)"]
        BotT["window.top<br/>(https://a.com)"]

        BotW -->|"parent"| BotP
        BotW -->|"top"| BotT
    end

    subgraph "접근 가능 여부"
        P1["parent.location ❌<br/>(cross-origin)"]
        P2["parent.postMessage ✅"]
        P3["top.document ❌<br/>(cross-origin)"]
    end
```

## XHR Same-Origin Policy

```mermaid
sequenceDiagram
    participant JS as JavaScript
    participant XHR as XMLHttpRequest
    participant JSCtx as JSContext<br/>(Python)
    participant Net as NetworkThread
    participant Server as External Server

    JS->>XHR: new XMLHttpRequest()
    JS->>XHR: open("GET", "https://api.other.com/data")
    JS->>XHR: send()

    XHR->>JSCtx: XMLHttpRequest_send(frame_id, method, url, ...)

    JSCtx->>JSCtx: Check origin
    Note over JSCtx: frame.url.origin() vs url.origin()

    alt Same Origin
        JSCtx->>Net: request(url)
        Net->>Server: HTTP GET
        Server-->>Net: Response
        Net-->>JSCtx: body
        JSCtx-->>XHR: responseText
    else Cross Origin
        JSCtx-->>XHR: "403 Forbidden"
        Note over JS: SecurityError
    end
```

## Content Security Policy (CSP)

### CSP 헤더 파싱

```mermaid
flowchart LR
    Header["Content-Security-Policy:<br/>default-src 'self';<br/>script-src 'self' https://cdn.com;<br/>style-src 'unsafe-inline'"]

    Header --> Parser[CSP Parser]

    Parser --> Dict["directives = {<br/>  'default-src': ['self'],<br/>  'script-src': ['self', 'https://cdn.com'],<br/>  'style-src': ['unsafe-inline']<br/>}"]
```

### CSP 검증 흐름

```mermaid
flowchart TB
    subgraph "리소스 로드 시"
        Script["&lt;script src='...'&gt;"]
        Style["&lt;link rel='stylesheet'&gt;"]
        XHR["XMLHttpRequest"]
        IFrame["&lt;iframe src='...'&gt;"]
    end

    Script --> CheckScript{csp.allows_script?}
    Style --> CheckStyle{csp.allows_style?}
    XHR --> CheckConnect{csp.allows_connect?}
    IFrame --> CheckFrame{csp.allows_frame?}

    CheckScript -->|Yes| LoadScript[로드]
    CheckScript -->|No| BlockScript[차단 + 로그]

    CheckStyle -->|Yes| LoadStyle[로드]
    CheckStyle -->|No| BlockStyle[차단]

    CheckConnect -->|Yes| Send[요청]
    CheckConnect -->|No| BlockXHR[차단]

    CheckFrame -->|Yes| LoadFrame[프레임 생성]
    CheckFrame -->|No| BlockFrame[차단]
```

### CSP Directive 우선순위

```mermaid
flowchart TB
    Check["allows_source('script-src', url)"]

    Check --> HasDirective{script-src<br/>정의됨?}
    HasDirective -->|Yes| UseScript[script-src 값 사용]
    HasDirective -->|No| HasDefault{default-src<br/>정의됨?}
    HasDefault -->|Yes| UseDefault[default-src 값 사용]
    HasDefault -->|No| Allow[허용]

    UseScript --> Match{패턴 매칭}
    UseDefault --> Match

    Match -->|매치| Allow[✅ 허용]
    Match -->|불일치| Block[❌ 차단]
```

## Cookie 보안 (SameSite)

```mermaid
flowchart TB
    subgraph "SameSite=Strict"
        S1["Cross-site 요청 시<br/>쿠키 전송 ❌"]
        S2["링크 클릭해서 이동해도 ❌"]
    end

    subgraph "SameSite=Lax (기본값)"
        L1["Cross-site POST ❌"]
        L2["Cross-site GET (top-level) ✅"]
        L3["iframe/img 요청 ❌"]
    end

    subgraph "SameSite=None"
        N1["Cross-site 모두 허용"]
        N2["Secure 필수"]
    end
```