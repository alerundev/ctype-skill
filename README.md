# ctype-skill

웹 서비스 한 벌 (백엔드 ± 프론트 ± DB) 의 코드 작성부터 [Cloudtype](https://cloudtype.io) 배포까지 한 사이클로 처리하는 AgentSkill 입니다.

`ctype` CLI 를 주력으로 사용하며, CLI 가 다루지 않는 빌드 로그·실행 로그 조회에 한해 Cloudtype API 를 직접 호출합니다.

## 기본 구성

- 풀스택 프레임워크 한 통 (Next.js / SvelteKit / FastAPI 등) + 필요 시 DB
- DB 가 있는 경우 같은 stage 의 별도 deployment 로 띄워 서비스 이름으로 통신 (`postgres:5432` 등)
- 사용자가 프론트와 백엔드 분리를 명시하면 그 형태로 진행

## 필요한 환경

- `ctype` CLI (`npm i -g @cloudtype/cli`)
- `CLOUDTYPE_API_KEY` 환경변수 (Cloudtype 콘솔에서 발급)
- Python 3 + `pip install websockets` (로그 helper 사용 시)
- GitHub 액세스 (코드 push 용)

## 흐름

```
0. 사전 준비       CLI 설치 + 로그인
1. 컨텍스트 확보   scope / 프로젝트
2. 설계 결정       프레임워크 + DB ± 분리 여부
3. 코드 작성       표준 진입점 + 환경변수 기반 설정
4. GitHub push     repo 확보
5. 배포            DB → 시크릿/env → 백엔드 (→ 프론트)
6. 상태 확인       Running + URL 응답
7. 실패 대응       로그 → 진단 → 수정 → 재배포
```

## 구조

```
ctype-skill/
├── SKILL.md              # 진입점 (전체 흐름 + 정책)
├── reference/
│   ├── yaml.md           # app.yaml 필드 가이드, preset 옵션, 시크릿 문법, DB 패턴
│   └── api.md            # 빌드/실행 로그 WebSocket API
├── scripts/
│   └── logs.py           # 빌드/실행 로그 클라이언트
├── README.md
└── LICENSE
```

## 라이선스

MIT
