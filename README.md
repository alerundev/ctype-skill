# ctype-skill

[Cloudtype](https://cloudtype.io) 에 GitHub repo (또는 Docker 이미지) 를 배포하기 위한 AgentSkill.

`ctype` CLI 를 주력으로 사용하며, CLI 가 노출하지 않는 **빌드 로그·실행 로그 조회**에만 Cloudtype WebSocket API 를 사용합니다 (`scripts/logs.py`).

## 범위

**범위 안**:
- `app.yaml` 작성
- `ctype apply` 배포 + 상태 확인
- 시크릿/환경변수 등록
- 빌드/실행 로그로 실패 진단
- 설정 수정 후 재배포

**범위 밖**:
- 코드 작성·수정, `git push`, 새 GitHub repo 생성
- 디자인/아키텍처 결정
- (이 스킬은 push 가 끝난 시점부터 진입합니다)

## 필요한 환경

- `ctype` CLI (`npm i -g @cloudtype/cli`)
- `CLOUDTYPE_APIKEY` 환경변수 (Cloudtype 콘솔에서 발급)
- Python 3 + `pip install websockets` (빌드 로그 조회용)

## 빠른 사용

```bash
# 0. 컨텍스트 준비
ctype login -t "$CLOUDTYPE_APIKEY"
ctype use @<scope>/<project>:main

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
├── SKILL.md              # 진입점 (배포 6단계 + 정책)
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
