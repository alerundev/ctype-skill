# Cloudtype API — 이 스킬이 호출하는 3가지

이 스킬은 다음 3가지 작업에 한해 Cloudtype API 를 직접 호출합니다. 나머지 모든 작업은 `ctype` CLI 로 수행합니다.

| 용도 | Helper | Endpoint |
|---|---|---|
| 빌드 로그 조회 | `scripts/logs.py build <deployment>` | `wss://api.cloudtype.io/project/build/logs` |
| 실행 로그 조회 | `scripts/logs.py run <deployment>` | `wss://api.cloudtype.io/project/logs` |
| 연동된 GitHub repo 조회/매칭 | `scripts/find_repo.py <키워드>` | `GET /oauth/github/*` (3개) |

공통 인증: `CLOUDTYPE_API_KEY` 환경변수.

---

## 1. 빌드 / 실행 로그

빌드 단계 로그는 WebSocket API 로만 조회할 수 있습니다. 컨테이너가 실행되기 전 단계 (이미지 빌드, 시작 시도) 에서 실패하면 `ctype logs` 가 가져올 stdout 이 없기 때문입니다.

```bash
python scripts/logs.py build <deployment>      # 빌드 로그
python scripts/logs.py run   <deployment>      # 실행 로그 (최근 200줄)
python scripts/logs.py run   <deployment> -f   # 실행 로그 follow
python scripts/logs.py run   <deployment> -p   # 이전 컨테이너 (재시작 직전)
```

배포된 상태에서 helper 호출에 필요한 값 (`scope`, `project`, `stage`) 은 `ctype use` 출력에서 자동 파싱됩니다. `deployment` 만 인자로 전달하면 됩니다.

### 종료 조건

- 빌드 로그: 빌드 완료 또는 실패 시 자동 종료.
- 실행 로그 (기본): `tailLines` 만큼 받고 종료.
- 실행 로그 (`-f`): Ctrl+C 까지 지속.

### 실패 응답

인증 오류 / 잘못된 deployment 이름 등은 stderr 로 명확한 메시지가 출력되고 종료 코드 1 로 빠집니다.

---

## 2. GitHub repo 조회

연동된 GitHub 계정의 repo 목록을 조회하여 사용자 키워드와 매칭합니다.

```bash
python scripts/find_repo.py "<키워드>"          # 이름/설명 일부 일치
python scripts/find_repo.py --list               # 전체 목록 (탭 구분)
```

### 호출 흐름

```
1) GET /oauth/github/has
   has=false  → "콘솔에서 GitHub 연동 필요" + exit 1
   has=true   → 계속

2) GET /oauth/github/accounts
   []         → "연동된 계정 없음" + exit 1
   [...]      → 모든 계정의 installationid 수집

3) GET /oauth/github/repository/<installationid>  (계정마다 호출, 합침)
   키워드와 매칭 (이름 일부 일치, 대소문자 무시, 공백/구분자 제거)
     후보 0   → "매칭 없음" + exit 1
     후보 1   → stdout: url/branch/name + exit 0
     후보 N   → stderr: 번호 매긴 선택지 + exit 2
```

### 출력 포맷

**후보 1개** (exit 0, stdout):

```
url=https://github.com/<owner>/<repo>.git
branch=main
name=<repo>
```

**후보 여러 개** (exit 2, stderr): 번호 매긴 선택지. 호출자가 사용자에게 그대로 제시합니다.

**실패** (exit 1, stderr): `ERROR: <이유>` 형태의 명확한 메시지.

### 호출자 권장 패턴

```bash
OUT=$(python scripts/find_repo.py "<키워드>") || exit 1
GIT_URL=$(echo "$OUT" | sed -n 's/^url=//p')
GIT_BRANCH=$(echo "$OUT" | sed -n 's/^branch=//p')
```
