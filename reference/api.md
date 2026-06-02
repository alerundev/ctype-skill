# Cloudtype API — 이 스킬이 쓰는 3개

> 이 스킬이 Cloudtype API 를 호출하는 경우는 **딱 3가지** 입니다. 그 외 모든 작업 (배포·시크릿·컨텍스트 등) 은 `ctype` CLI 로 수행합니다.

| 용도 | Endpoint | Helper |
|---|---|---|
| 빌드 로그 조회 | `wss://api.cloudtype.io/project/build/logs` | `scripts/logs.py build <deployment>` |
| 실행 로그 조회 | `wss://api.cloudtype.io/project/logs` | `scripts/logs.py run <deployment>` |
| 연동된 GitHub repo 목록/매칭 | `GET /oauth/github/*` (3개) | `scripts/find_repo.py <키워드>` |

공통 인증: `Authorization: Bearer $CLOUDTYPE_API_KEY` (WebSocket 은 prepare envelope 의 `headers` 안에 동일).

---

# 1. 빌드 로그 / 실행 로그 (WebSocket)

```bash
python scripts/logs.py build <deployment>      # 빌드 로그
python scripts/logs.py run   <deployment>      # 실행 로그 (최근 200줄)
python scripts/logs.py run   <deployment> -f   # 실행 로그 follow
python scripts/logs.py run   <deployment> -p   # 이전 컨테이너 (재시작 직전) 로그
```

## CLI 가 가진 것과 못 가진 것

| 항목 | CLI (`ctype logs`) | API (WebSocket) |
|---|---|---|
| 실행 로그 (running container stdout/stderr) | ✅ | ✅ |
| 빌드 로그 (이미지 빌드/시작 시도 단계) | ❌ | ✅ |

**왜 빌드 로그가 필수인가**: `ctype apply` 가 "성공" 으로 떨어져도, 그건 요청 접수일 뿐 빌드가 끝난 게 아닙니다. 빌드 단계 실패 (`go build`, `npm install`, Dockerfile 단계 등) 는 컨테이너가 한 번도 실행되지 않으므로 `ctype logs` 가 가져올 수 있는 stdout 이 존재하지 않습니다. 이때 빌드 로그 WebSocket 이 유일한 진단 수단입니다.

## Endpoints

```
wss://api.cloudtype.io/project/build/logs   # 빌드 로그
wss://api.cloudtype.io/project/logs          # 실행 로그
```

## Handshake — prepare envelope

브라우저 WS 가 `Authorization` 헤더를 설정할 수 없는 환경을 위해, 서버는 첫 메시지로 prepare envelope 을 받습니다.

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
    "Authorization": "Bearer <CLOUDTYPE_API_KEY>",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*"
  }
}
```

서버는 `"accept"` (plain text) 응답 후 로그 청크 (UTF-8 텍스트) 를 스트리밍합니다.

## 필요한 5개 값 — 배포된 상태면 이미 다 알고 있음

| 값 | 출처 |
|---|---|
| `scope` | `ctype use` 출력의 `@<scope>/...` |
| `project` | `ctype use` 출력의 `.../<project>:...` |
| `stage` | `ctype use` 출력의 `...:<stage>` |
| `deployment` | `app.yaml` 의 `name` 필드 |
| `CLOUDTYPE_API_KEY` | 환경변수 |

`scripts/logs.py` 가 `ctype use` 를 호출해 자동 파싱합니다.

## 옵션

| 옵션 | 의미 | 기본 |
|---|---|---|
| `follow` | 스트리밍 지속 (false 면 일정 양 받고 닫힘) | build: `true`, run: `false` |
| `tailLines` | 시작 시 가져올 최근 줄 수 | 200 |
| `previous` | 이전 컨테이너 (재시작 직전) 로그 | false |
| `timestamps` | 각 라인 앞에 RFC3339 nano 타임스탬프 | true |
| `pretty` | (서버 측 포맷팅 — 일반적으로 false) | false |

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

## 종료 조건

- **빌드 로그**: 빌드 완료 또는 실패 시 서버가 연결을 정상 종료합니다. `scripts/logs.py build` 는 그 시점에 자동 종료됩니다.
- **실행 로그**: `follow=false` 면 `tailLines` 만큼 받고 종료. `follow=true` 면 사용자가 Ctrl+C 로 종료할 때까지 계속.

## 실패 응답

prepare envelope 인증 실패, 잘못된 deployment 이름 등의 경우 서버는 `"accept"` 대신 에러 텍스트를 보내고 연결을 닫습니다. 스크립트는 그 메시지를 stderr 로 출력하고 종료 코드 1 로 빠집니다.

---

# 2. GitHub repo 조회 (HTTP)

```bash
python scripts/find_repo.py "<키워드>"           # 이름/설명 일부 일치
python scripts/find_repo.py --list                # 전체 목록 (탭 구분: name\turl\tbranch\taccount)
```

CLI 가 GitHub repo 조회를 노출하지 않아 (`ctype` v0.7.1 기준) 보조 API 를 사용합니다. **사용자가 repo URL 을 알려주지 못하고 이름/키워드만 던졌을 때**만 불러야 하며, URL 을 이미 알고 있으면 쓰지 않습니다.

## Endpoints (한 사이클에 3개)

| # | Endpoint | 역할 |
|---|---|---|
| 1 | `GET /oauth/github/has` | Cloudtype 계정에 GitHub 연동 여부 → `{has: true|false}` |
| 2 | `GET /oauth/github/accounts` | 연동된 GitHub 계정 목록 → 각각에 `installationid` |
| 3 | `GET /oauth/github/repository/<installationid>` | repo 목록 → `name`, `url`, `defaultbranch`, ... |

## 한 사이클에 오류 없이 종료되는 흐름 (`find_repo.py` 가 그대로 구현)

```
1) /oauth/github/has
   has=false           → "콘솔에서 GitHub 연동 필요" stderr + exit 1
   has=true            → 계속

2) /oauth/github/accounts
   []                  → "연동된 계정 없음" stderr + exit 1
   [..]                → 모든 계정의 installationid 수집

3) /oauth/github/repository/<installationid>  (계정마다 호출, 합침)
   repo 목록을 사용자 키워드와 매칭 (이름 일부 일치, 대소문자 무시, 공백/구분자 제거)
     후보 0개          → "매칭 없음" stderr + exit 1
     후보 1개          → stdout: url=... branch=... name=...  + exit 0
     후보 N개          → stderr: 번호 매긴 선택지 + exit 2 (호출자가 사용자에게 제시)
```

## 출력 포맷

**후보 1개 자동 확정** (exit 0, stdout):
```
url=https://github.com/<owner>/<repo>.git
branch=main
name=<repo>
```

**후보 여러 개** (exit 2, stderr):
```
AMBIGUOUS: '<키워드>' 와 매칭되는 repo 가 여러 개 있습니다. ...
  [1] <name>  <url>  (branch=main, account=<acc>)
  [2] <name>  <url>  (branch=main, account=<acc>)
  ...
```

**실패** (exit 1, stderr): `ERROR: <이유>` 수준의 명확한 메시지.

## 호출자 (에이전트) 권장 파이프라인

```bash
OUT=$(python scripts/find_repo.py "<키워드>") || {
  # exit 1 or 2 — stderr 에 명확한 메시지가 있으므로 사용자에게 그대로 보고
  exit 1  # 안전하게 중단
}
# 성공 — 파싱
GIT_URL=$(echo "$OUT" | sed -n 's/^url=//p')
GIT_BRANCH=$(echo "$OUT" | sed -n 's/^branch=//p')
```
