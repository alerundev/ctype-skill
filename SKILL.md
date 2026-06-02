---
name: ctype-skill
description: >
  Cloudtype 에 GitHub repo (또는 Docker 이미지) 를 배포합니다. app.yaml 작성 →
  ctype apply → 상태 확인 → (실패 시) 빌드/실행 로그 진단 → 재배포. 사용자가
  Cloudtype, ctype, cloudtype.app 도메인을 언급하거나 서비스/DB 배포를 요청할
  때 사용합니다. 코드 작성·수정·push 는 범위 밖입니다.
allowed-tools: Bash(ctype:*), Bash(curl:*), Bash(python:*), Bash(python3:*), Bash(npm:*), Bash(which:*)
---

# ctype-skill

GitHub repo 또는 외부 이미지를 [Cloudtype](https://cloudtype.io) 에 배포하는 일만 합니다.

**범위 안**: `app.yaml` 작성, `ctype apply`, 시크릿 등록, 빌드/실행 로그로 실패 진단, 설정 수정 후 재배포.

**범위 밖**: 코드 작성·수정, `git push`, 새 GitHub repo 생성, 디자인/아키텍처 결정. 이 스킬은 push 가 끝난 시점부터 진입합니다.

---

## 🚀 흐름 (6단계)

```
1. 인증 / 컨텍스트     ctype whoami ; ctype use
2. preset 확인         ctype presets
3. app.yaml 작성       .cloudtype/app.yaml
4. 배포                ctype apply
5. 상태 확인           ctype list ; ctype routes  (+ URL HTTP GET)
6. 실패 시 진단/재배포  → 본 문서 "실패 대응"
```

해피패스는 1~5 로 끝. 실패가 발생할 때만 6 으로 들어갑니다.

---

## 1. 인증 / 컨텍스트

```bash
which ctype                       # 설치 확인
ctype whoami                      # 인증 + 로그인 계정
ctype use                         # 현재 컨텍스트 (@scope/project:stage)
```

미설치: `npm i -g @cloudtype/cli`. 미인증: `ctype login -t "$CLOUDTYPE_APIKEY"`.

프로젝트가 없으면 생성:

```bash
# cluster 이름은 다음으로 조회 (보통 결과 1개)
curl -sS -H "Authorization: Bearer $CLOUDTYPE_APIKEY" \
  "https://api.cloudtype.io/scope/<scope>/cluster"

ctype project create <name> -s <scope> -c <cluster-name>
ctype use @<scope>/<name>:main
```

`stage` 는 명시 없으면 `main`.

---

## 2. preset 확인

```bash
ctype presets                     # 사용 가능한 preset + 버전 목록
```

사용자가 명시한 게 있으면 그게 절대 우선 ("Spring Boot", "MariaDB", "Rust" 등). 명시 없으면 묻습니다 — 이 스킬은 언어/스택을 추측하지 않습니다.

DB 가 필요한데 종류 미명시이고 사용자가 묻기 곤란한 컨텍스트면 `postgresql` 을 디폴트로 사용하고 완료 보고에 명시합니다.

---

## 3. `app.yaml` 작성

기본 위치: `.cloudtype/app.yaml`. 다른 경로는 `-f` 로 지정.

**최소 형태**:

```yaml
name: my-api
app: node@24
options:
  ports: "3000"
  start: npm start
  env:
    - name: NODE_ENV
      value: production
context:
  git:
    url: https://github.com/<owner>/<repo>
    ref: main
  preset: node
```

필드 가이드 (preset 별 옵션, 시크릿 문법, 멀티 서비스): [`reference/yaml.md`](reference/yaml.md).

**작성 원칙**:
- 사용자가 명시한 항목만 yaml 에 박습니다. 나머지는 서버 디폴트.
- `context.git.url` 은 사용자 또는 상위 에이전트가 제공합니다. 모를 경우 사용자에게 묻습니다.
- `resources:` 절은 **기본적으로 박지 않습니다** (아래 "리소스" 섹션).
- 시크릿은 `env[]` 안에서 `{secret: <KEY>}` 로 참조. **다른 자리 금지** (특히 DB preset 의 `rootpassword` 는 plain 만).

---

## 4. 배포

```bash
ctype apply                       # .cloudtype/app.yaml
ctype apply -f path/to/file.yaml  # 다른 파일
```

같은 stage 에 동일 이름 deployment 가 이미 있으면 자동 진행하지 말고 확인:

> "이미 같은 이름의 서비스(`<name>`)가 존재합니다. 재배포할까요, 새 이름으로 만들까요?"

---

## 5. 상태 확인

`ctype apply` 의 성공 출력은 **요청 접수일 뿐**입니다. 빌드 + 시작이 끝나야 완료.

```bash
ctype list                        # stage 의 deployment 상태
ctype routes                      # HTTP 라우트 + URL
```

**완료 조건 (모두 충족)**:
1. `ctype list` 의 status = `Running`
2. `ctype routes` 의 HTTP 엔드포인트 상태 = `bound`
3. 해당 URL 에 HTTP GET → 2xx / 3xx

세 조건 충족 전엔 완료로 보고하지 않습니다. 보통 수십 초 ~ 몇 분. status 가 `Stopped` / `Failed` 로 떨어지거나 `Pending`/`unknown` 이 길어지면 **6번 실패 대응**.

---

## 6. 실패 대응

### 6.1 로그 조회

**`ctype logs` 는 실행 로그만**, 빌드 단계 실패는 보여주지 않습니다. 빌드 로그는 WebSocket API 가 유일한 통로 → `scripts/logs.py` 사용.

```bash
# 빌드 로그 (이미지 빌드/시작 시도 단계)
python scripts/logs.py build <deployment>

# 실행 로그 (running container stdout, 최근 200줄)
python scripts/logs.py run <deployment>

# 실행 로그 follow
python scripts/logs.py run <deployment> -f

# 직전 컨테이너 로그 (재시작 직전)
python scripts/logs.py run <deployment> -p
```

**언제 어느 쪽?**
- `Running` 도 못 가본 (빌드/시작 실패) = **빌드 로그 먼저**
- `Running` 이었다가 떨어진 / 응답 없음 = **실행 로그 (특히 `-p` 로 직전 로그)**

스크립트는 `ctype use` 의 컨텍스트 (scope/project/stage) 와 `CLOUDTYPE_APIKEY` 환경변수를 자동으로 사용합니다. API 호출용 추가 정보 필요 없음.

API 프로토콜 세부: [`reference/api-logs.md`](reference/api-logs.md).

### 6.2 진단 및 분류

로그를 읽고 원인을 분류합니다.

| 원인 | 처리 |
|---|---|
| Cloudtype 설정 (healthz, start, env 누락, 포트 등) | 변경 사유 1줄 보고 → `app.yaml` 수정 → `ctype apply` |
| 시크릿/환경변수 누락 또는 오타 | `ctype stage secret` 또는 `ctype stage variable` 로 수정 → `ctype apply` |
| 리소스 부족 (cluster error / pool exhausted 류) | 아래 "리소스" 섹션 흐름 |
| **코드 측 문제** | 위치와 방향을 **보고만** 하고 멈춥니다 (코드 수정은 범위 밖) |

Cloudtype 환경 컨벤션 중 자주 놓치는 것: Cloudtype 은 ingress 뒤. `X-Forwarded-For` 헤더가 들어오므로 Express `trust proxy` 같은 프록시 인지 옵션이 꺼져 있으면 rate limiter 에서 validation 에러 발생 가능.

### 6.3 재배포

`app.yaml` 또는 시크릿 수정 후 `ctype apply`. spec 변경 없이 최신 커밋만 다시 빌드하고 싶으면 `ctype update <deployment>`.

재배포 후 반드시 **5번 완료 조건**을 다시 점검합니다. apply 출력만 보고 완료 처리 금지.

### 6.4 재시도 한도

동일한 처방으로 3회 연속 실패하면 자동 재시도 중단하고 사용자에게 보고:

> "동일 패턴으로 3회 실패했습니다. 코드 측 수정 또는 운영 채널 문의가 필요해 보입니다."

다른 preset 으로 갈아타기 / 새 deployment 이름 사용은 **재시도가 아닌 새 결정** → 사용자 확인 필요.

---

## 🎟️ 리소스

### 기본 동작

`app.yaml` 에 `resources:` 절을 **박지 않습니다.** Cloudtype 이 preset 별 디폴트로 자동 배분 + 풀 선택.

사용자가 명시한 경우 (`spot: true`, `cpu: 2` 등) 만 박습니다. LLM 추측 절대 금지 — 프리티어 1GB 한도를 깨고 후속 배포까지 막을 수 있음.

### 리소스 부족으로 배포 실패 시

`ctype apply` 또는 빌드 로그에서 리소스/cluster 관련 에러가 나오면:

**1단계 — 잔여 조회**:

```bash
curl -sS -H "Authorization: Bearer $CLOUDTYPE_APIKEY" \
  "https://api.cloudtype.io/scope/<scope>/resource/available"
```

응답에는 두 풀의 잔여가 들어 있음:
- 구독 풀: `cpu` / `memory` / `disk` / `running`
- 프리티어 풀: `spot.cpu` / `spot.memory` / `spot.disk` / `spot.running`

**2단계 — 사용자에게 보고하고 선택 받음**:

> "리소스 부족으로 배포 실패. 잔여 — 구독 풀: cpu N, memory N GB, ... / 프리티어 풀: cpu N, memory N GB, .... 어느 풀로 배포할까요?"

**3단계 — 사용자 명령 ("구독으로" / "프리티어로") 받은 후 yaml 패치 + 재배포**:

```yaml
resources:
  spot: false                     # "구독으로" → false
  # spot: true                    # "프리티어로" → true
```

양쪽 다 부족하면 그대로 보고하고 멈춤. 사용자가 명시적으로 사양 (cpu/memory/disk) 까지 지정하면 그것도 yaml 에 박음. **추측 금지.**

---

## 🔐 시크릿

CLI 만으로 충분 — API 호출 불필요.

```bash
ctype stage secret DB_PASSWORD "<값>"       # 저장
ctype stage variable LOG_LEVEL info          # 평문 (env 와 동일하게 참조 가능)
ctype stage secret DB_PASSWORD -r            # 삭제
```

yaml 에서 참조:

```yaml
env:
  - name: NODE_ENV
    value: production               # 평문
  - name: DB_PASSWORD
    secret: DB_PASSWORD              # 시크릿 참조
```

### 민감 값 자동 분류

다음 패턴의 env 이름은 평문 `value:` 대신 `ctype stage secret` + `secret:` 참조를 사용합니다.

| 패턴 | 처리 |
|---|---|
| `*PASSWORD*` `*SECRET*` `*TOKEN*` `*KEY*` `*PWD*` `*PRIVATE*` `*AUTH*` | 무조건 시크릿 |
| `*URL*` `*HOST*` (값에 자격증명 포함된 경우, 예: `postgresql://user:PASS@...`) | 시크릿 |
| `NODE_ENV` `LOG_LEVEL` `PORT` 등 단순 플래그 | 평문 OK |

`DATABASE_URL` 같이 자격증명 포함 URL은 전체를 한 시크릿 키로 저장 후 참조.

DB preset 의 `rootpassword` 는 **plain only** (시크릿 참조 객체 금지). 같은 값을 `ctype stage secret` 으로 저장하고 앱 서비스에서 참조하는 패턴: [`reference/yaml.md`](reference/yaml.md) 의 "DB 배포 권장 패턴".

---

## 🌐 멀티 서비스

여러 서비스가 필요하면 `.cloudtype/<name>.yaml` 로 분리하고 순서대로 apply (DB → 백엔드 → 프론트). 같은 stage 의 서비스끼리는 deployment 이름이 곧 호스트 (`postgres:5432`, `redis:6379`, `api:3000`).

자세한 패턴: [`reference/yaml.md`](reference/yaml.md).

---

## ⛔ 자동 수행 금지 — 사용자 확인 필요

- 다른 preset 으로 갈아타기 (`web` 실패 → `dockerfile` 재배포)
- 새 deployment 이름으로 별도 서비스 생성
- 리소스 사양/풀 변경 (위 "리소스" 흐름은 사용자 명령 수신 후에만 적용)
- Dockerfile 자동 생성/주입
- 시크릿 덮어쓰기 (이미 존재하는 키)
- 삭제 (`ctype remove`, 프로젝트/스테이지 삭제)
- 코드 수정 (범위 밖)

---

## 🔐 인증 — `CLOUDTYPE_APIKEY` 하나로 둘 다

- **CLI**: `ctype login -t "$CLOUDTYPE_APIKEY"` 한 번 (이후 `ctype whoami` 로 확인)
- **로그 API**: `scripts/logs.py` 가 환경변수에서 자동으로 읽음

키 발급은 Cloudtype 콘솔에서.

---

## 📚 참조 자료

본 문서 (SKILL.md) 만으로 일반 배포는 완결. 아래는 해당 상황 발생 시에만:

- [`reference/yaml.md`](reference/yaml.md) — `app.yaml` 전체 필드, preset 별 옵션, 시크릿 문법, 멀티 서비스
- [`reference/api-logs.md`](reference/api-logs.md) — 빌드/실행 로그 WebSocket API 프로토콜
- `scripts/logs.py` — 위 API 의 클라이언트
