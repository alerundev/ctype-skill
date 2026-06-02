# `.cloudtype/app.yaml` 가이드

`ctype apply` 가 받는 deployment 파일. 이 문서는 SKILL.md 의 예시에서 다루지 않는 옵션을 설명합니다.

## 최소 필수 필드

```yaml
name: <deployment-name>           # 필수. stage 안에서 고유
app: <preset>@<version>           # 필수. 예: node@24, postgresql@16, redis@7
```

## 전체 구조

```yaml
name: my-api
app: node@24

options:                          # preset 별 옵션 (필드는 preset 마다 다름)
  ports: "3000"                   # 노출 포트 (string 으로 권장)
  install: npm ci                 # 빌드 명령
  start: npm start                # 시작 명령
  buildenv: []                    # 빌드 시점 환경변수
  env:                            # 런타임 환경변수
    - name: NODE_ENV
      value: production
    - name: DB_PASSWORD
      secret: DB_PASSWORD         # stage secret store 의 키 참조
  healthz: /                      # 헬스체크 경로
  initialDelaySeconds: 30         # 헬스체크 시작 전 대기 (기본 0)

context:                          # repo 연결 / preset 메타
  git:
    url: https://github.com/<owner>/<repo>
    ref: main                     # branch 또는 commit SHA
  preset: node                    # preset 이름
```

`resources:` 절은 **기본적으로 생략**합니다. 사용자가 풀(`spot`)이나 사양을 명시한 경우, 또는 리소스 부족으로 배포 실패 후 사용자가 풀을 지정한 경우에만 박습니다 (SKILL.md "리소스" 섹션 참조).

---

## Preset 별 핵심 옵션

### Node.js / Python / Go 등 framework preset

```yaml
options:
  ports: "3000"
  install: npm ci                 # 또는 pip install -r requirements.txt
  start: npm start                # 또는 python app.py
  healthz: /health
  env:
    - name: NODE_ENV
      value: production
```

### PostgreSQL / MariaDB / MySQL / MongoDB

```yaml
options:
  rootusername: root              # plain string only
  rootpassword: "<plain-password>"  # plain string only — secret 객체 X
  database: mydb                  # 초기 DB 이름 (선택)
  # tz: Asia/Seoul                # 시간대 (선택)
```

> ⚠️ DB preset 의 `rootpassword` 같은 옵션 필드는 **반드시 plain 문자열**. `{secret: ...}` 객체를 넣으면 배포 후 `[ServiceError] secret value must be a string` 으로 stopped 됩니다. **시크릿 참조는 오직 `env[]` 안에서만 동작.**

### Redis

```yaml
options:
  password: ""                    # 비우면 인증 없음 (내부망 전용 권장)
  # password: "<plain>"           # 인증 사용 시 plain string
```

### Dockerfile

```yaml
options:
  ports: "8080"
  # dockerfile: ./Dockerfile      # 위치 명시 (기본은 repo root)
context:
  preset: dockerfile
```

## 시크릿 참조 규칙

`{secret: <KEY>}` 형태의 참조는 **오직 다음 자리에서만** 동작합니다:

- `options.env[]` 항목
- `options.buildenv[]` 항목

그 외 모든 `options.*` 필드에는 plain 값 (string / number / boolean) 만 허용됩니다.

올바른 예:
```yaml
options:
  rootpassword: "Lp7zXq..."       # plain ✅
  env:
    - name: DB_PASSWORD
      secret: DB_PASSWORD         # ✅ env[] 안에서 참조
```

잘못된 예:
```yaml
options:
  rootpassword:                   # ❌ object in plain-only field
    secret: DB_PASSWORD
```

### 시크릿 등록 (CLI)

```bash
ctype stage secret DB_PASSWORD "Lp7zXq..."     # 저장
ctype stage variable LOG_LEVEL info             # 평문 (env 와 동일하게 참조)
ctype stage secret DB_PASSWORD -r               # 삭제
```

### DB 배포 권장 패턴

1. 강한 패스워드 생성 → DB preset 의 `rootpassword` 에 **plain** 으로 박고 `ctype apply`. PostgreSQL 같은 DB preset 은 정상 흐름에서 별도 Running polling 없이 다음 단계로 진행합니다. Cloudtype 이 `<deployment-name>-root-password` 시크릿을 자동 등록합니다.
2. 앱 서비스의 `env[]` 에서 다음을 박습니다.
   - `DB_HOST` = deployment 이름 (평문)
   - `DB_PORT` = preset 표준 포트 (평문)
   - `DB_NAME` = yaml 의 `database` (평문)
   - `DB_USER` = yaml 의 `rootusername` (평문)
   - `DB_PASSWORD` → `<deployment-name>-root-password` 자동 시크릿 참조

수동으로 `ctype stage secret` 을 디디면 채워넣은 필요는 없습니다. `rootpassword` `rootusername` `database` 는 첫 부팅 시점에 디스크에 박히므로 이후 yaml 값을 바꿔도 실제 자격증명은 갱신되지 않으며, 바꾸려면 deployment 삭제 후 재배포가 필요합니다 (기존 데이터 손실).

---

## 리소스 명시 (사용자가 요청했을 때만)

```yaml
resources:
  spot: true                      # 풀: true=프리티어, false=구독
  cpu: 1                          # 사용자 명시 시
  memory: 0.5                     # GB 단위
  disk: 1                         # GB 단위. DB 는 보통 명시 필요.
  replicas: 1
```

리소스 부족으로 배포 실패 시 흐름은 SKILL.md "리소스" 섹션 참조.

---

## healthz / initialDelaySeconds

```yaml
options:
  healthz: /                      # 응답 시 서비스 정상으로 판정
  initialDelaySeconds: 60         # 시작 시간 긴 앱 (Spring 등)
```

`healthz` 가 빈 문자열이면 헬스체크 비활성화.

---

## 멀티 서비스

여러 서비스가 필요하면 각각 `.cloudtype/<name>.yaml` 로 분리하고 순서대로 `apply` (DB → 백엔드 → 프론트). 같은 stage 의 서비스끼리는 deployment 이름이 곧 호스트 (`postgres:5432`, `redis:6379` 등) 로 자동 연결됩니다.

```bash
ctype apply -f .cloudtype/postgres.yaml
ctype apply -f .cloudtype/api.yaml
ctype apply -f .cloudtype/web.yaml
```

프론트/백엔드 분리 배포에서는 백엔드 URL 을 프론트엔드 public env 에 넣고, 프론트엔드 URL 을 백엔드 `CORS_ORIGIN` 에 넣습니다. URL 순환이 있으므로 정석 흐름은 백엔드 → 프론트엔드 → 백엔드 CORS 갱신입니다. 인증 없는 프로토타입이나 공개 API 는 `CORS_ORIGIN=*` 을 쓸 수 있고, 쿠키/세션/사용자 데이터가 있으면 origin 을 명시합니다.

---

## 자주 헷갈리는 것

- `ports` 는 **string** (`"3000"`). 숫자도 받지만 일관성 위해 string 권장.
- `app:` 의 버전 (`node@24`) 은 `ctype presets` 으로 확인. 명시 안 하면 최신 안정 버전.
- `env[].value` 는 항상 string. 숫자라도 `"production"` 같이 따옴표.
- DB preset 의 `rootpassword` 는 **plain only** — 시크릿 참조 객체 금지.
