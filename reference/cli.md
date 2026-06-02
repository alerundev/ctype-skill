# `ctype` CLI 출력 가이드

`ctype` 명령의 사람이 읽는 출력은 버전과 상태에 따라 바뀔 수 있습니다. 자동 판단이 필요할 때는 `-o json` 을 사용합니다.

## `ctype list -o json`

Deployment 상태는 최상위 `status` 가 아니라 `stat.status` 에 있습니다.

예시:

```json
[
  {
    "name": "postgres",
    "stat": {
      "status": "running"
    }
  },
  {
    "name": "api",
    "stat": {
      "status": "starting"
    }
  }
]
```

상태 파싱:

```bash
NODE_NO_WARNINGS=1 ctype list -o json | python3 -c '
import json, sys

data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get("deployments", [])
for d in items:
    name = d.get("name")
    status = ((d.get("stat") or {}).get("status") or "unknown").lower()
    print(name + ": " + status)
'
```

판단 규칙:

`stat.status` 는 소문자로 정규화해서 비교합니다. 현재 직접 확인된 값은 `stopped` 입니다. 배포 중 값은 버전/타이밍에 따라 달라질 수 있으므로 아래처럼 처리합니다.

- `running`: HTTP deployment 라면 route/URL 확인으로 진행
- `stopped` / `failed`: 빌드 실패로 보고 build log 확인
- `starting`: 빌드 성공 후 서버 시작 단계. run log 확인 후 이상 없으면 계속 대기
- `pending` / `building` / `deploying` 등 진행 상태: 30초 주기로 재확인
- `unknown`: JSON 경로를 추측하지 말고 원본을 출력해서 구조 확인

Node.js deprecation warning 이 JSON 앞에 섞이면 파싱이 실패할 수 있으므로 `NODE_NO_WARNINGS=1` 을 붙입니다. 그래도 파싱이 실패하면 `ctype list` 텍스트 출력으로 상태를 확인합니다.

Python inline one-liner 에서는 JSON key quoting 때문에 `f"{d[\"key\"]}"` 같은 패턴을 쓰지 않습니다. Python 3.11 이하에서 f-string expression 안의 backslash 때문에 SyntaxError 가 날 수 있으므로 값을 변수로 빼거나 `print("key:", value)` 패턴을 씁니다.

PostgreSQL 같은 DB preset 은 정상 흐름에서 별도 Running polling 하지 않습니다. 백엔드 연결 실패나 인증 실패가 발생했을 때만 `NODE_NO_WARNINGS=1 ctype list -o json` 과 로그로 확인합니다.
