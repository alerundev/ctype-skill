# ctype-skill

[Cloudtype](https://cloudtype.io) 에 GitHub repo 를 배포하기 위한 AgentSkill.

`ctype` CLI 를 주력으로 사용하며, CLI 가 노출하지 않는 3가지 용도에만 Cloudtype API 를 사용합니다:

- 빌드 로그 조회 (`scripts/logs.py build`)
- 실행 로그 조회 (`scripts/logs.py run`)
- 연동된 GitHub repo 목록/매칭 (`scripts/find_repo.py`)

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
│   └── api.md            # 이 스킬이 쓰는 3개 API (로그 WS + repo 조회)
├── scripts/
│   ├── logs.py           # 빌드/실행 로그 클라이언트
│   └── find_repo.py      # 연동된 GitHub repo 조회/매칭
├── README.md
└── LICENSE
```

## 라이선스

MIT
