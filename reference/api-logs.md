# 빌드/실행 로그 API (WebSocket)

> 이 스킬은 **빌드 로그**와 **실행 로그** 조회에만 Cloudtype HTTP/WS API 를 사용합니다.
> 나머지 모든 인프라 작업 (배포, 시크릿, 컨텍스트) 은 `ctype` CLI 로 수행합니다.

이 문서는 `scripts/logs.py` 가 내부에서 사용하는 프로토콜을 설명합니다.
일반 사용 시에는 스크립트만 호출하면 됩니다.

```bash
python scripts/logs.py build <deployment>      # 빌드 로그
python scripts/logs.py run   <deployment>      # 실행 로그 (최근 200줄)
python scripts/logs.py run   <deployment> -f   # 실행 로그 follow
python scripts/logs.py run   <deployment> -p   # 이전 컨테이너 (재시작 직전) 로그
```

---

## CLI 가 가진 것과 못 가진 것

| 항목 | CLI (`ctype logs`) | API (WebSocket) |
|---|---|---|
| 실행 로그 (running container stdout/stderr) | ✅ | ✅ |
| 빌드 로그 (이미지 빌드/시작 시도 단계) | ❌ | ✅ |

**왜 빌드 로그가 필수인가**: `ctype apply` 가 "성공" 으로 떨어져도, 그건 요청 접수일 뿐 빌드가 끝난 게 아닙니다. 빌드 단계 실패 (`go build`, `npm install`, Dockerfile 단계 등) 는 컨테이너가 한 번도 실행되지 않으므로 `ctype logs` 가 가져올 수 있는 stdout 이 존재하지 않습니다. 이때 빌드 로그 WebSocket 이 유일한 진단 수단입니다.

---

## Endpoints

```
wss://api.cloudtype.io/project/build/logs   # 빌드 로그
wss://api.cloudtype.io/project/logs          # 실행 로그
```

---

## Handshake

브라우저 WS 가 `Authorization` 헤더를 설정할 수 없는 환경을 위해, 서버는 **prepare envelope** 으로 인증과 파라미터를 받습니다.

연결 직후 클라이언트가 보내는 첫 메시지:

```json
{
  "type": "prepare",
  "params": {
    "scope": "myspace",
    "project": "myproject",
    "stage": "main",
    "deployment": "web",
    "options": {
      "follow": true,
      "pretty": false,
      "tailLines": 200,
      "previous": false,
      "timestamps": true
    }
  },
  "headers": {
    "Authorization": "Bearer <CLOUDTYPE_APIKEY>",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*"
  }
}
```

서버는 `"accept"` (plain text) 응답 후 로그 청크 (UTF-8 텍스트) 를 스트리밍합니다.

---

## 필요한 5개 값

배포된 상태라면 이 5개는 **이미 모두 알고 있습니다** — 추가 API 조회 불필요:

| 값 | 출처 |
|---|---|
| `scope` | `ctype use` 출력의 `@<scope>/...` |
| `project` | `ctype use` 출력의 `.../<project>:...` |
| `stage` | `ctype use` 출력의 `...:<stage>` |
| `deployment` | `app.yaml` 의 `name` 필드 |
| `CLOUDTYPE_APIKEY` | 환경변수 |

`scripts/logs.py` 가 `ctype use` 를 호출해 자동 파싱합니다.

---

## 옵션

| 옵션 | 의미 | 기본 |
|---|---|---|
| `follow` | 스트리밍 지속 (false 면 일정 양 받고 닫힘) | build: `true`, run: `false` |
| `tailLines` | 시작 시 가져올 최근 줄 수 | 200 |
| `previous` | 이전 컨테이너 (재시작 직전) 로그 | false |
| `timestamps` | 각 라인 앞에 RFC3339 nano 타임스탬프 | true |
| `pretty` | (서버 측 포맷팅 — 일반적으로 false) | false |

---

## 프레임 형식

### 실행 로그 (`/project/logs`)

각 라인: `<RFC3339 nano timestamp> <stdout/stderr text>`

```
2026-05-26T07:08:01.072250947Z {"ts":"...","level":"info","msg":"listening","port":8000}
```

`timestamps: false` 면 타임스탬프 생략.

### 빌드 로그 (`/project/build/logs`)

이모지 포함 자유 형식 텍스트. 진행 단계가 사람이 읽기 쉬운 형태로 출력됩니다.

```
🏁 Deployment started ...
👉 Prepare build
🏂 Build runner(sel-1) is starting...
  ├ Build type is dockerfile
  └ Build env is {"NODE_ENV":"p*********", ...}    # 값은 마스킹됨
🚀 Deploy to a cluster
✅ Done.
```

빌드 실패 시 위 흐름 중간에 stack trace / build error 메시지가 그대로 노출됩니다.

---

## 종료 조건

- **빌드 로그**: 빌드 완료 또는 실패 시 서버가 연결을 정상 종료합니다. `scripts/logs.py build` 는 그 시점에 자동 종료됩니다.
- **실행 로그**: `follow=false` 면 `tailLines` 만큼 받고 종료. `follow=true` 면 사용자가 Ctrl+C 로 종료할 때까지 계속.

---

## 실패 응답

prepare envelope 인증 실패, 잘못된 deployment 이름 등의 경우 서버는 `"accept"` 대신 에러 텍스트를 보내고 연결을 닫습니다. 스크립트는 그 메시지를 stderr 로 출력하고 종료 코드 1 로 빠집니다.
