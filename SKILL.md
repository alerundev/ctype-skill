---
name: ctype-skill
description: "Create or update a web app and deploy it to Cloudtype with the ctype CLI. Use for Cloudtype, ctype, cloudtype.app, web app, API, DB, full-stack, or split frontend/backend deployment requests."
allowed-tools: Bash(ctype:*), Bash(curl:*), Bash(python:*), Bash(python3:*), Bash(npm:*), Bash(which:*), Bash(git:*), Bash(gh:*)
---

# ctype-skill

코드 작성부터 Cloudtype 배포까지 한 사이클로 처리합니다. 기본형은 **풀스택 한 통 ± DB**. 프론트/백엔드 분리는 사용자가 명시한 경우에만 선택합니다.

## 흐름

0. 사전 준비 — `ctype`, `CLOUDTYPE_API_KEY`, `GITHUB_TOKEN`
1. 컨텍스트 — scope / project / stage
2. 설계 — 프레임워크, DB, 한 통 vs 분리
3. 코드 — 표준 진입점, env 기반 설정
4. GitHub push — repo URL + branch 확보
5. 배포 — DB → 외부 시크릿/env → 백엔드 → 프론트
6. 확인 — route bound + URL 응답
7. 실패 대응 — 로그 → 진단 → 수정 → 재배포

## 0. 사전 준비

빈 managed-agent 환경을 기본으로 봅니다. 이미 준비되어 있으면 건너뜁니다.

```bash
which ctype >/dev/null 2>&1 || npm i -g @cloudtype/cli
ctype whoami >/dev/null 2>&1 || ctype login -t "$CLOUDTYPE_API_KEY"
: "${GITHUB_TOKEN:?set GitHub personal access token classic as GITHUB_TOKEN}"
which git >/dev/null 2>&1
python3 -c 'import websockets' >/dev/null 2>&1 || python3 -m pip install -q websockets
```

- `CLOUDTYPE_API_KEY`: Cloudtype CLI + 보조 API 인증.
- `GITHUB_TOKEN`: Cloudtype 콘솔에 OAuth 연동된 GitHub 계정에서 발급한 personal access token classic, `repo` scope.
- 로그 helper 는 `websockets` 를 사용하므로 0단계에서 한 번 준비합니다.

Cloudtype GitHub 연동 확인과 repo 생성/commit/push 명령은 [`reference/github.md`](reference/github.md)를 따릅니다.

## 1. 컨텍스트 확보

```bash
ctype whoami -o json              # scope 후보
ctype projects                    # 기존 프로젝트
```

scope 는 `ctype whoami -o json` 의 `scopes` 배열에서 얻습니다. stage 는 명시 없으면 `main`.

새 프로젝트가 필요하고 `ctype projects` 가 생성 안내만 출력하면 cluster 조회 후 생성합니다. cluster API 응답은 배열입니다.

```bash
curl -sS -H "Authorization: Bearer $CLOUDTYPE_API_KEY" \
  "https://api.cloudtype.io/scope/<scope>/cluster" \
  | python3 -c 'import json,sys; [print(c["name"]) for c in json.load(sys.stdin)]'
ctype project create <name> -s <scope> -c <cluster-name>
ctype use @<scope>/<name>:main
```

## 2. 설계 결정

- 사용자가 언어/프레임워크/DB 를 지정하면 그대로 따릅니다.
- 미지정 기본값: `node + postgresql`; `java-springboot`/`kotlin` → `mariadb`; Python 계열 → `postgresql`.
- 저장이 필요 없는 단순 화면/도구는 DB 를 띄우지 않습니다.
- 프론트/백 분리는 사용자 명시 시에만 선택합니다. 그 외는 한 통으로 진행합니다.

## 3. 코드 작성

프레임워크의 일반 구조를 따르고 Cloudtype preset 이 감지할 수 있는 표준 진입점을 유지합니다. 표준에서 벗어나면 yaml 의 `options.start` 로 override 합니다.

모든 설정은 env 에서 읽도록 작성합니다.

- 외부 인증값: `OPENAI_API_KEY`, `STRIPE_SECRET_KEY` → 5.2 에서 stage secret.
- DB 패스워드: 앱 env 에서 `<db-deployment>-root-password` 자동 시크릿 참조.
- DB 메타: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` → yaml `env[].value`.
- 일반 플래그: `NODE_ENV`, `LOG_LEVEL`, `PORT` → 평문 env.

같은 stage 의 서비스는 deployment 이름으로 통신합니다: `postgres:5432`, `redis:6379`, `mongo:27017`. DB 연결 코드는 `DATABASE_URL` 하나 또는 위 DB env 조합을 읽도록 둡니다.

DB 를 사용하는 앱은 DB 연결/초기화 실패를 숨기지 않습니다. health/readiness endpoint 는 DB 연결과 필수 초기화 상태를 반영하도록 작성합니다.

## 4. GitHub push

작성한 코드를 GitHub repo 에 push 하고 다음을 확보합니다.

- repo URL: `https://github.com/<owner>/<repo>`
- branch: 기본 `main`

기본 경로는 `GITHUB_TOKEN` 이 환경에 주입된 상태에서 표준 git 흐름을 사용하는 방식입니다. credential helper 가 없는 샌드박스에서는 토큰이 포함된 HTTPS remote 를 임시로 사용할 수 있고, push 후 remote 를 깨끗한 URL 로 되돌립니다. 샌드박스의 author/signing 오류를 피하기 위해 repo local git user 와 signing 을 설정하고 `--no-gpg-sign` 으로 commit 합니다. 세부 명령은 [`reference/github.md`](reference/github.md).

Cloudtype scope 이름과 GitHub owner 이름은 다를 수 있습니다. `context.git.url` 과 repo 생성 owner 는 scope 가 아니라 Cloudtype GitHub 연동 계정의 `name` 을 사용합니다. token owner 는 GitHub `/user` 로 확인합니다. 연동 목록이 비어 있거나 owner 가 맞지 않으면 사용자에게 콘솔에서 GitHub 연동을 추가하도록 요청합니다.

## 5. 배포

yaml 은 `.cloudtype/` 아래 컴포넌트별로 둡니다. 자세한 필드와 예시는 [`reference/yaml.md`](reference/yaml.md).

### 5.1 DB 배포

DB 가 필요하면 먼저 DB yaml 을 apply 합니다. DB preset 의 `rootpassword` / `rootusername` / `database` 는 plain 문자열입니다. `rootpassword` 는 영어 소문자와 숫자만 사용합니다.

```bash
ctype apply -f .cloudtype/postgres.yaml
```

PostgreSQL 같은 DB preset 은 정상 흐름에서 Running polling 없이 다음 단계로 갑니다. 앱은 yaml 에 적은 접속 정보와 Cloudtype 이 생성하는 `<deployment>-root-password` 자동 시크릿을 사용합니다. DB 쪽 오류가 실제로 발생했을 때만 상태와 로그를 확인합니다.

DB 초기값은 첫 부팅 시 디스크에 저장됩니다. 바꾸려면 DB deployment 삭제 후 재배포가 필요하며 데이터가 제거됩니다.

### 5.2 외부 시크릿/env

DB 자격증명은 자동 시크릿으로 처리합니다. 외부 인증 정보만 직접 등록합니다.

```bash
ctype stage secret OPENAI_API_KEY "<값>"
ctype stage secret STRIPE_SECRET_KEY "<값>"
```

평문 env 는 yaml `env[].value` 또는 `ctype stage variable`. 기존 시크릿 덮어쓰기는 사용자 확인 후 진행합니다.

### 5.3 백엔드 배포

백엔드 yaml 은 `name`, `app`, `context.git`, 필요한 `options.env[]` 만 추가합니다. DB 패스워드는 `secret: <db-deployment>-root-password` 로 참조합니다.

```bash
ctype apply -f .cloudtype/api.yaml
```

`install`, `build`, `start` 는 preset 디폴트를 우선하고, 소스코드 구조상 필요한 경우에만 명시합니다.

### 5.4 프론트 분리 배포

분리 배포는 URL 의존성이 순환됩니다.

1. 백엔드 배포 → `ctype routes` 로 백엔드 URL 확보.
2. 프론트엔드 배포 → `PUBLIC_API_BASE_URL` / `VITE_API_URL` 같은 public env 에 백엔드 URL 주입.
3. 프론트엔드 URL 확보 → 백엔드 `CORS_ORIGIN` 을 프론트엔드 URL 로 갱신 후 재배포.

인증 없는 프로토타입이나 공개 API 는 `CORS_ORIGIN=*` 가능. 쿠키/세션/사용자 데이터가 있으면 `*` 대신 프론트엔드 origin 을 명시합니다.

## 6. 상태 확인

HTTP deployment 는 `ctype apply` 직후 `ctype routes` 에 보이지 않을 수 있습니다. 빌드가 끝나고 서비스가 시작 단계로 넘어간 뒤 HTTP route 가 생성됩니다.

상태는 30초 주기로 확인합니다. deployment status 는 `stat.status` 이며 소문자로 정규화해서 판단합니다.

```bash
NODE_NO_WARNINGS=1 ctype list -o json
```

상태별 흐름:

- `pending` / `building` / `deploying` 등 진행 상태: 계속 대기. build log 를 먼저 follow 하지 않습니다.
- `stopped` / `failed`: 빌드 실패로 보고 build log 확인 → 오류 메시지 기준으로 수정 후 재배포.
- `starting`: 빌드 성공, 서버 시작 단계. run log 확인. 이상 로그가 있으면 설정/코드 수정 후 재배포, 이상이 없으면 계속 대기.
- `running`: `ctype routes` 와 URL 테스트로 진행.

```bash
ctype routes
```

완료 조건:

1. HTTP deployment 의 route 가 `bound`.
2. URL GET 이 2xx / 3xx.
3. DB 를 사용하는 앱은 DB-backed endpoint 또는 대표 사용자 흐름 하나가 작성한 코드의 기대 응답과 일치.

200 OK 라도 응답 내용이 예상과 다르면 완료로 보지 않고 실행 로그를 확인합니다. DB preset 은 정상 흐름에서 polling 하지 않습니다. JSON 파싱과 status 예시는 [`reference/cli.md`](reference/cli.md).

## 7. 실패 대응

### 7.1 로그

```bash
python3 /workspace/skills/ctype-skill/scripts/logs.py build <deployment>
python3 /workspace/skills/ctype-skill/scripts/logs.py run <deployment>
python3 /workspace/skills/ctype-skill/scripts/logs.py run <deployment> -f
python3 /workspace/skills/ctype-skill/scripts/logs.py run <deployment> -p
```

HTTP deployment 는 apply 후 30초 주기로 상태를 봅니다. `stopped` / `failed` 는 빌드 로그, `starting` 은 실행 로그, `running` 은 route/URL 테스트입니다. `running` 이후 응답 실패/재시작도 실행 로그를 봅니다. DB deployment 는 백엔드 연결/인증 실패가 있을 때 확인합니다.

### 7.2 흔한 진단

- 브랜치 불일치: GitHub branch 목록 조회 → `context.git.ref` 수정. 명령은 [`reference/github.md`](reference/github.md).
- 포트/헬스체크 실패: `starting` 에 머무르거나 route 가 안 붙음 → 실행 로그의 listen 포트 확인 → `options.ports` / `healthz` 수정.
- DB connection refused: `DB_HOST` deployment 이름, `DB_PORT` preset 포트 확인.
- DB auth failed: `DB_PASSWORD` 가 `<db-deployment>-root-password` 자동 시크릿을 가리키는지 확인. 패스워드 변경은 DB 재생성 필요.
- HTTP 200 이지만 응답 내용이 예상과 다름: 실행 로그에서 DB 초기화/마이그레이션 오류 확인.
- 시크릿/env 누락: stage secret/variable 또는 yaml env 수정.
- 빌드 실패: 빌드 로그 확인 → 코드/yaml 수정.
- 리소스 부족: 아래 리소스 흐름.

Cloudtype 은 ingress 뒤에서 동작합니다. Express `trust proxy` 같은 프록시 인지 옵션이 필요한 라이브러리가 있습니다.

### 7.3 수정/재배포

코드 문제면 수정 후 push. spec 변경 없이 최신 커밋만 다시 빌드하려면 `ctype update <deployment>`. yaml/시크릿 문제면 수정 후 `ctype apply`. 동일 처방 3회 연속 실패하면 멈추고 보고합니다.

## 리소스

`resources:` 는 기본적으로 생략합니다. 사용자가 `cpu` / `memory` / `disk` / `replicas` / `spot` 을 명시했거나 리소스 부족 실패 후 사용자가 풀을 선택한 경우에만 박습니다.

리소스 부족 시:

```bash
curl -sS -H "Authorization: Bearer $CLOUDTYPE_API_KEY" \
  "https://api.cloudtype.io/scope/<scope>/resource/available"
```

구독 풀/프리티어 풀 잔여를 보고하고 선택을 받습니다. 양쪽 다 부족하면 멈춥니다.

## 시크릿

- `*PASSWORD*`, `*SECRET*`, `*TOKEN*`, `*KEY*`, `*PWD*`, `*PRIVATE*`, `*AUTH*` → `ctype stage secret`, yaml 에서는 `env[].secret`.
- 자격증명이 포함된 URL/HOST 도 시크릿.
- `NODE_ENV`, `LOG_LEVEL`, `PORT` 같은 플래그는 평문.
- DB preset 의 `rootpassword` 는 plain only 이며 영어 소문자와 숫자만 사용합니다. 앱은 자동 생성된 `<deployment>-root-password` 를 `env[].secret` 으로 참조합니다.

## 사용자 확인 후 진행

- 다른 preset 으로 전환.
- 새 deployment 이름으로 별도 서비스 생성.
- 리소스 사양/풀 변경.
- 기존 시크릿 덮어쓰기.
- DB deployment 삭제.
- 그 외 삭제 (`ctype remove`, 프로젝트/스테이지 삭제).

## 참조

- [`reference/github.md`](reference/github.md) — GitHub token 기반 repo 생성/commit/push/branch 조회
- [`reference/yaml.md`](reference/yaml.md) — app.yaml 필드, preset 옵션, 시크릿 문법, DB 패턴
- [`reference/api.md`](reference/api.md) — 빌드/실행 로그 WebSocket API
- [`reference/cli.md`](reference/cli.md) — `ctype` JSON 출력 구조와 상태 파싱
- `scripts/logs.py` — 빌드/실행 로그 클라이언트
