# Cloudtype API

이 스킬이 Cloudtype API 를 직접 호출하는 작업은 빌드 로그와 실행 로그 조회 두 가지입니다. 나머지 작업은 `ctype` CLI 로 수행합니다.

| 용도 | Helper | Endpoint |
|---|---|---|
| 빌드 로그 조회 | `scripts/logs.py build <deployment>` | `wss://api.cloudtype.io/project/build/logs` |
| 실행 로그 조회 | `scripts/logs.py run <deployment>` | `wss://api.cloudtype.io/project/logs` |

인증: `CLOUDTYPE_API_KEY` 환경변수.

---

## 빌드 / 실행 로그

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
