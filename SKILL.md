---
name: ctype-skill
description: >
  사용자 요청을 받아 웹 서비스 한 벌 (백엔드 ± 프론트 ± DB) 의 코드를
  작성하고 Cloudtype 에 배포합니다. 풀스택 프레임워크 한 통을 기본 형태로
  하며, DB 가 필요하면 같은 stage 의 별도 deployment 로 띄워 서비스 이름으로
  통신합니다. 사용자가 Cloudtype, ctype, cloudtype.app 도메인을 언급하거나
  웹앱·API·DB 배포를 요청할 때 사용합니다.
allowed-tools: Bash(ctype:*), Bash(curl:*), Bash(python:*), Bash(python3:*), Bash(npm:*), Bash(which:*), Bash(git:*), Bash(gh:*)
---

# ctype-skill

웹 서비스 한 벌을 코드 작성부터 [Cloudtype](https://cloudtype.io) 배포까지 한 사이클로 처리합니다.

기본 구성: **풀스택 프레임워크 한 통 ± DB**. 사용자가 프론트/백엔드 분리를 명시하면 그 형태로 갑니다.

---

## 🚀 흐름

```
0. 사전 준비           CLI 설치 + 로그인
1. 컨텍스트 확보       scope/프로젝트
2. 설계 결정           프레임워크 + DB ± 분리 여부
3. 코드 작성           표준 진입점 + 환경변수 기반 설정
4. GitHub push         repo 확보
5. 배포                DB → 시크릿/env → 백엔드 (→ 프론트)
6. 상태 확인           Running + URL 응답
7. 실패 대응           로그 → 진단 → 수정 → 재배포
```

---

## 0. 사전 준비

스킬 진입 시 멱등적으로 한 번. 이미 되어 있으면 건너뜁니다.

```bash
# Cloudtype CLI 설치 + 인증
which ctype >/dev/null 2>&1 || npm i -g @cloudtype/cli
ctype whoami >/dev/null 2>&1 || ctype login -t "$CLOUDTYPE_API_KEY"

# GitHub 인증 (4단계 push 시 사용). 둘 중 하나만 준비.
#   - GITHUB_PAT 환경변수 (repo 스코프)
#   - 또는 gh auth login
```

로그 helper 를 사용할 환경이라면 `pip install websockets` 도 한 번 확인합니다.

`CLOUDTYPE_API_KEY` 가 비어 있으면 사용자에게 발급 (Cloudtype 콘솔) 후 export 안내. 키 하나로 CLI 와 보조 API 가 모두 인증됩니다.

GitHub 인증이 준비되지 않은 경우 4단계 push 시점에 발견되므로, 그때 사용자에게 PAT 발급 또는 `gh auth login` 을 안내해도 됩니다.

---

## 1. 컨텍스트 확보

```bash
ctype whoami -o json              # scopes 배열에 사용 가능한 scope
ctype projects                    # 기존 프로젝트 목록
```

scope 는 `ctype whoami -o json` 의 `scopes` 배열에서 얻습니다.

### 새 프로젝트가 필요할 때

`ctype projects` 가 `Create a project first with the command ...` 메시지만 출력하면 프로젝트가 없는 상태입니다. 아래 흐름으로 생성합니다.

```bash
# cluster 이름 조회 (보통 결과 1개)
curl -sS -H "Authorization: Bearer $CLOUDTYPE_API_KEY" \
  "https://api.cloudtype.io/scope/<scope>/cluster"

# 프로젝트 생성 (cluster 명시 필수)
ctype project create <name> -s <scope> -c <cluster-name>

# 컨텍스트 전환
ctype use @<scope>/<name>:main
```

`stage` 는 명시 없으면 `main`. 기존 프로젝트에 배포할 때는 마지막 한 줄만.

---

## 2. 설계 결정

사용자 요청을 다음 세 축으로 정리합니다.

### 프레임워크 + DB 선택

사용자가 언어/프레임워크 또는 DB 를 지정한 경우 그대로 따릅니다.

지정이 없으면 아래의 기본 조합을 사용하고 완료 보고에 명시합니다.

| 백엔드 | 기본 DB |
|---|---|
| 미지정 | `node` + `postgresql` |
| `java-springboot` / `kotlin` | `mariadb` |
| `python-django` / `python-flask` / `python-fastapi` | `postgresql` |

저장이 필요 없는 단순 화면/도구는 DB 를 띄우지 않습니다.

### 분리 여부

사용자가 프론트와 백엔드 분리를 명시하면 두 개의 deployment 로 갑니다 (5단계의 별도 절). 명시가 없으면 한 통으로 진행합니다.

---

## 3. 코드 작성

프레임워크의 일반적인 구조를 따르되, Cloudtype 이 자동으로 호출할 수 있도록 preset 의 표준 진입점을 유지합니다. 진입점이 표준에서 벗어나면 5.3 에서 `options.start` 로 override 합니다.

### 환경변수 기반 설정

설정값은 모두 환경변수에서 읽도록 작성합니다. 직접 작성하므로 어떤 키를 어떤 형태로 사용하는지 정확히 알고 있어야 합니다.

| 종류 | 키 예시 | 등록 방법 |
|---|---|---|
| 외부 API 인증 정보 | `OPENAI_API_KEY`, `STRIPE_SECRET_KEY` | 5.2 에서 `ctype stage secret` |
| DB 연결 자격증명 (패스워드) | `DB_PASSWORD` 등 | 5.1 의 자동 시크릿 (`<deployment>-root-password`) 참조 |
| DB 연결 메타 (호스트/포트/이름/유저) | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` | 5.3 에서 yaml `env[].value` 에 직접 |
| 동작 플래그 | `NODE_ENV`, `LOG_LEVEL`, `PORT` | 평문 (yaml `env[].value` 또는 `ctype stage variable`) |

코드에서 사용하는 모든 env 키를 정리해 두면 5단계에서 등록 누락이 없습니다.

### Cloudtype 에서 DB 를 배포하여 사용할 때 — 서비스 이름으로 통신

같은 stage 의 서비스는 deployment 이름이 곧 호스트가 됩니다. 표준 패턴:

```
deployment name: postgres   →  app 에서 host=postgres, port=5432
deployment name: redis      →  app 에서 host=redis,    port=6379
deployment name: mongo      →  app 에서 host=mongo,    port=27017
```

DB 연결 코드는 단일 환경변수 (예: `DATABASE_URL=postgresql://root:<password>@postgres:5432/<dbname>`) 를 읽는 형태로 두면 5단계에서 시크릿 등록이 단순해집니다.

---

## 4. GitHub push

작성한 코드를 GitHub repo 에 push 합니다. push 는 `GITHUB_PAT` 환경변수 (`repo` 스코프 포함) 또는 `gh auth status` 가 로그인 상태임을 전제로 합니다. 둘 다 비어 있으면 사용자에게 PAT 발급 또는 `gh auth login` 을 안내합니다.

push 후 다음을 확보합니다.

- repo URL (예: `https://github.com/<owner>/<repo>`)
- 사용한 branch (기본 `main`)

repo 가 Cloudtype 콘솔의 GitHub 연동 계정 소속이면 그대로 5단계로 진행합니다. 소속이 아니면 사용자에게 콘솔에서 연동 추가를 요청합니다.

---

## 5. 배포

배포는 **DB → 시크릿/env → 백엔드** 순서로 진행합니다. 백엔드가 DB 연결 정보를 환경변수로 받으므로 DB 가 먼저 떠 있고 그 정보가 stage 시크릿에 등록되어 있어야 합니다.

yaml 파일은 `.cloudtype/` 폴더에 컴포넌트별로 분리하여 둡니다.

### 5.1 DB 배포 (필요한 경우)

DB preset 의 디폴트 설정 (`ctype preset list -o json` 결과 활용) 을 그대로 사용하고, `rootpassword` 에 강한 패스워드를 plain 문자열로 박습니다.

`.cloudtype/postgres.yaml` 예시:

```yaml
name: postgres
app: postgresql@16
options:
  rootusername: root
  rootpassword: "<강한 패스워드>"
  database: appdb
```

```bash
ctype apply -f .cloudtype/postgres.yaml
ctype list                                # Running 도달 확인
```

배포가 완료되면 Cloudtype 이 `<deployment-name>-root-password` 형태의 시크릿을 자동 등록합니다 (위 예시면 `postgres-root-password`). 5.3 의 백엔드 yaml 에서 이 시크릿을 참조합니다.

DB 의 `rootpassword`, `rootusername`, `database` 는 첫 부팅 시점에 디스크에 저장되며 이후 yaml 값을 바꿔도 실제 자격증명은 갱신되지 않습니다. 변경하려면 deployment 를 삭제하고 새로 배포해야 하며, 기존 데이터가 함께 제거됩니다.

### 5.2 외부 시크릿/env 등록

DB 자격증명은 5.1 에서 자동 시크릿으로 처리됩니다. 그 외 외부 인증 정보 (OpenAI/Stripe 같은 API key 등) 만 직접 등록합니다.

```bash
ctype stage secret OPENAI_API_KEY "<값>"
ctype stage secret STRIPE_SECRET_KEY "<값>"
```

평문 환경변수 (`NODE_ENV`, `LOG_LEVEL` 등) 는 5.3 의 yaml `env[].value` 에 직접 박거나 `ctype stage variable` 로 등록합니다.

이미 같은 이름의 시크릿이 등록되어 있으면 덮어쓰기 전에 사용자에게 확인합니다.

### 5.3 백엔드 배포

preset 디폴트 설정 위에 `name`, `context.git`, 그리고 시크릿 참조 `env[]` 만 추가합니다.

`.cloudtype/api.yaml` 예시 (Node):

```yaml
name: api
app: node@16
options:
  ports: "3000"
  env:
    - name: NODE_ENV
      value: production
    - name: DB_HOST
      value: postgres
    - name: DB_PORT
      value: "5432"
    - name: DB_NAME
      value: appdb
    - name: DB_USER
      value: root
    - name: DB_PASSWORD
      secret: postgres-root-password
    - name: OPENAI_API_KEY
      secret: OPENAI_API_KEY
context:
  git:
    url: https://github.com/<owner>/<repo>
    ref: main
  preset: node
```

```bash
ctype apply -f .cloudtype/api.yaml
```

`app` 과 `ports` 는 preset 의 디폴트 그대로. `start` 는 코드의 진입점이 표준이면 생략합니다 (Cloudtype 이 `package.json` 의 `scripts.start` 등 표준 진입점을 자동 호출). 진입 파일명이 표준과 다르면 그때만 `options.start` 를 명시합니다.

필드 가이드 (preset 별 옵션, 시크릿 문법, DB 패턴): [`reference/yaml.md`](reference/yaml.md).

### 5.4 프론트 분리 배포 (사용자가 명시한 경우)

`.cloudtype/web.yaml` 을 추가하고 백엔드 URL 을 build-time env 또는 runtime env 로 전달합니다. 백엔드 URL 은 5.3 배포 후 `ctype routes` 로 확인할 수 있습니다.

---

## 6. 상태 확인

```bash
ctype list                        # 모든 deployment 상태
ctype routes                      # HTTP 라우트 + URL
```

완료 조건 (모두 충족):

1. 관련 deployment 의 status 가 `Running`
2. 해당 라우트의 상태가 `bound`
3. URL 에 HTTP GET 시 2xx / 3xx 응답

세 조건이 충족되기 전에는 완료로 보고하지 않습니다. 보통 수십 초에서 몇 분 걸립니다. status 가 `Stopped` / `Failed` 로 떨어지거나 `Pending` / `unknown` 이 길어지면 7단계로 진행합니다.

---

## 7. 실패 대응

### 7.1 로그 조회

로그 조회는 API 를 활용합니다 (`scripts/logs.py`).

```bash
python scripts/logs.py build <deployment>      # 빌드 단계 로그
python scripts/logs.py run <deployment>        # 실행 로그 (최근 200줄)
python scripts/logs.py run <deployment> -f     # 실행 로그 follow
python scripts/logs.py run <deployment> -p     # 직전 컨테이너 로그 (재시작 직전)
```

상태가 `Running` 에 도달하지 못한 경우는 빌드 로그를 먼저 확인하고, `Running` 이었다가 떨어졌거나 응답이 없는 경우는 실행 로그를 확인합니다. 재시작 직전 상태가 필요하면 `-p` 를 붙입니다.

스크립트는 `ctype use` 의 컨텍스트와 `CLOUDTYPE_API_KEY` 를 자동으로 사용합니다.

### 7.2 진단

| 원인 | 처리 |
|---|---|
| 브랜치 불일치 (`Couldn't find remote ref`, `branch not found` 등) | `gh api "repos/<owner>/<repo>/branches" --jq '.[].name'` 으로 실제 브랜치 목록 조회 → `context.git.ref` 수정 → 재배포 |
| 포트 불일치 (`EADDRINUSE`, connection refused, healthcheck 실패 등) | 실행 로그에서 실제 listen 포트 확인 → `options.ports` 수정 → 재배포 |
| DB 연결 실패 (`connection refused`) | 백엔드 env 의 `DB_HOST` (deployment 이름) 와 `DB_PORT` (preset 표준) 가 5.1 과 일치하는지 확인 → 수정 → 재배포 |
| DB 인증 실패 (`password authentication failed`) | 백엔드 env 의 `DB_PASSWORD` 가 DB deployment 의 자동 시크릿 (`<deployment>-root-password`) 을 가리키는지 확인. 패스워드 자체를 바꿔야 한다면 DB 재생성이 필요하며 사용자 확인 후 진행 |
| 시크릿/환경변수 누락 또는 오타 | `ctype stage secret` / `ctype stage variable` 로 수정 → 재배포 |
| 빌드 단계 실패 (`npm install`, `go build`, Dockerfile 단계 등) | 빌드 로그에서 원인 확인 → 코드 또는 yaml 수정 → 재배포 |
| 리소스 부족 (cluster error, pool exhausted 등) | 아래 "리소스" 흐름 |

Cloudtype 은 ingress 뒤에서 동작하므로 `X-Forwarded-For` 헤더가 들어옵니다. Express `trust proxy` 같은 프록시 인지 옵션을 켜지 않으면 일부 라이브러리 (rate limiter 등) 가 validation 에러를 낼 수 있습니다.

### 7.3 수정 및 재배포

원인이 코드 측이면 코드를 수정하고 다시 push 합니다. spec 변경 없이 최신 커밋만 다시 빌드하려면 `ctype update <deployment>`. yaml/시크릿 측이면 그 부분만 수정 후 `ctype apply`. 재배포 후 6단계 완료 조건을 다시 확인합니다.

동일 처방으로 3회 연속 실패하면 자동 시도를 중단하고 상황을 사용자에게 보고합니다.

---

## 🎟️ 리소스

`app.yaml` 에 `resources:` 절은 기본적으로 박지 않습니다. Cloudtype 이 preset 별 디폴트로 자동 배분합니다.

사용자가 `cpu` / `memory` / `disk` / `replicas` / `spot` 같은 값을 명시한 경우에만 그 항목을 yaml 에 박습니다. 명시 없이 임의로 박지 않습니다.

### 리소스 부족으로 배포 실패할 때

```bash
curl -sS -H "Authorization: Bearer $CLOUDTYPE_API_KEY" \
  "https://api.cloudtype.io/scope/<scope>/resource/available"
```

응답에 구독 풀과 프리티어 풀의 잔여가 들어 있습니다. 양쪽 잔여를 사용자에게 보고하고 풀 선택을 받습니다.

```yaml
resources:
  spot: false                     # "구독으로" → false
  # spot: true                    # "프리티어로" → true
```

양쪽 다 부족하면 그대로 보고하고 멈춥니다.

---

## 🔐 시크릿

3단계에서 코드를 직접 작성하므로 어떤 키가 시크릿인지, 어떤 키가 평문인지 그 자리에서 결정됩니다. 5.2 에서 등록할 때 다음 분류를 따릅니다.

| 패턴 | 처리 |
|---|---|
| `*PASSWORD*` `*SECRET*` `*TOKEN*` `*KEY*` `*PWD*` `*PRIVATE*` `*AUTH*` | `ctype stage secret` 으로 등록 후 `env[].secret` 으로 참조 |
| `*URL*` `*HOST*` 이지만 값에 자격증명 포함 (예: `postgresql://user:pass@host`) | 위와 동일 |
| `NODE_ENV` `LOG_LEVEL` `PORT` 같은 단순 플래그 | 평문. yaml `env[].value` 또는 `ctype stage variable` |

DB preset 의 `rootpassword` 는 plain 문자열만 동작합니다. 시크릿 참조 객체를 넣으면 배포 후 `[ServiceError] secret value must be a string` 으로 `stopped` 상태가 됩니다. 이 패스워드는 DB 배포 완료 시 Cloudtype 이 `<deployment>-root-password` 시크릿로 자동 등록하므로, 앱 서비스는 그 시크릿을 `env[].secret` 으로 참조합니다.

---

## ⛔ 자동 수행하지 않는 결정

다음은 사용자 확인 후에만 진행합니다.

- 다른 preset 으로 갈아타기 (예: `web` 실패 → `dockerfile` 로 재배포)
- 새 deployment 이름으로 별도 서비스 생성
- 리소스 사양/풀 변경 (위 "리소스" 흐름은 사용자 명령 수신 후에만 적용)
- 이미 존재하는 시크릿 덮어쓰기
- DB deployment 삭제 (디스크가 함께 제거되어 기존 데이터 손실)
- 그 외 삭제 (`ctype remove`, 프로젝트/스테이지 삭제)

코드 수정은 7단계의 정상 흐름 안에서 진행하되, 동일 처방 3회 실패 시 자동 시도를 중단합니다.

---

## 📚 참조 자료

- [`reference/yaml.md`](reference/yaml.md) — `app.yaml` 전체 필드, preset 별 옵션, 시크릿 문법, DB 배포 패턴
- [`reference/api.md`](reference/api.md) — 이 스킬이 호출하는 Cloudtype API: 빌드 로그 / 실행 로그
- `scripts/logs.py` — 빌드/실행 로그 클라이언트
