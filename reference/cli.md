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
      "status": "Running"
    }
  },
  {
    "name": "api",
    "stat": {
      "status": "Building"
    }
  }
]
```

상태 파싱:

```bash
ctype list -o json | python3 -c '
import json, sys

data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get("deployments", [])
for d in items:
    name = d.get("name")
    status = (d.get("stat") or {}).get("status") or "unknown"
    print(f"{name}: {status}")
'
```

판단 규칙:

- `Running`: HTTP deployment 라면 route/URL 확인으로 진행
- `Failed` / `Stopped`: 기다리지 말고 빌드 로그 또는 실행 로그 진단
- `Pending` / `Building` / `Deploying`: 필요한 경우에만 제한된 횟수로 재확인
- `unknown`: JSON 경로를 추측하지 말고 원본을 출력해서 구조 확인

PostgreSQL 같은 DB preset 은 정상 흐름에서 별도 Running polling 하지 않습니다. 백엔드 연결 실패나 인증 실패가 발생했을 때만 `ctype list -o json` 과 로그로 확인합니다.
