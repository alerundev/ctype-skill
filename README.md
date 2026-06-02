# ctype-skill

[Cloudtype](https://cloudtype.io) 에 GitHub repo 를 배포하기 위한 AgentSkill.

`ctype` CLI 를 주력으로 사용하며, CLI 가 노출하지 않는 **빌드 로그·실행 로그 조회**에만 Cloudtype WebSocket API 를 사용합니다 (`scripts/logs.py`).

## 필요한 환경

- `ctype` CLI (`npm i -g @cloudtype/cli`)
- `CLOUDTYPE_API_KEY` 환경변수 (Cloudtype 콘솔에서 발급)
- Python 3 + `pip install websockets` (빌드 로그 조회용)

## 빠른 사용

```bash
# 0. 준비
npm i -g @cloudtype/cli
ctype login -t "$CLOUDTYPE_API_KEY"

# 1. .cloudtype/app.yaml 작성 (스킬이 해줌)

# 2. 배포
ctype apply

# 3. 상태 확인
ctype list
ctype routes

# 4. 실패 시 로그
python scripts/logs.py build my-api      # 빌드 단계 실패
python scripts/logs.py run my-api -f     # 실행 로그 follow
```

## 구조

```
ctype-skill/
├── SKILL.md              # 진입점 (배포 흐름 + 정책)
├── reference/
│   ├── yaml.md           # app.yaml 필드 가이드
│   └── api-logs.md       # 로그 WebSocket API
├── scripts/
│   └── logs.py           # 빌드/실행 로그 클라이언트
├── README.md
└── LICENSE
```

## 라이선스

MIT
