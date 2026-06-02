# GitHub 작업 가이드

기본 인증은 `GITHUB_TOKEN` 하나입니다. 사전 준비는 Cloudtype 콘솔에서 GitHub 계정을 OAuth 로 연동하고, 그 GitHub 계정에서 personal access token classic (`repo` scope) 을 발급해 `GITHUB_TOKEN` 으로 제공하는 것입니다. `gh` 가 이미 로그인되어 있으면 써도 되지만 기본 전제는 아닙니다.

Cloudtype scope 이름과 GitHub owner 이름은 다를 수 있습니다. repo owner 는 Cloudtype 에 연동된 GitHub 계정 기준으로 맞춥니다.

## 새 repo 생성

```bash
curl -fsS -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/user/repos \
  -d '{"name":"<repo>","private":false}'
```

응답의 `html_url`, `clone_url`, `default_branch`, `owner.login` 을 확인합니다.

## Cloudtype GitHub 연동 확인

```bash
curl -fsS -H "Authorization: Bearer $CLOUDTYPE_API_KEY"   "https://api.cloudtype.io/oauth/github/has"

curl -fsS -H "Authorization: Bearer $CLOUDTYPE_API_KEY"   "https://api.cloudtype.io/oauth/github/accounts"
```

`/oauth/github/accounts` 응답은 배열입니다.

```json
[
  {
    "name": "<github-owner>",
    "installationid": 123,
    "type": "user"
  }
]
```

repo owner 는 가능하면 이 `name` 과 맞춥니다. 배열이 비어 있으면 Cloudtype 콘솔에서 GitHub 연동을 추가해야 합니다.

## commit / push

`GITHUB_TOKEN` 은 환경이 git 에 사용할 수 있게 주입한다고 가정합니다. 스킬은 표준 git 흐름을 사용하고 인증 전달 방식은 환경에 맡깁니다. 샌드박스의 commit signing 오류를 피하기 위해 repo local signing 을 끕니다.

```bash
git config --local commit.gpgsign false || true
git add .
git commit --no-gpg-sign -m "Initial Cloudtype deployment"
git branch -M main
git remote add origin https://github.com/<owner>/<repo>.git
GIT_TERMINAL_PROMPT=0 git push -u origin main
```

이미 remote 가 있으면 `git remote set-url origin https://github.com/<owner>/<repo>.git`. `git push` 가 timeout 되면 같은 명령을 길게 반복하지 말고 인증 프롬프트/hang 여부와 환경의 git credential 주입을 확인합니다. Contents API 나 zip 업로드를 기본 fallback 으로 사용하지 않습니다.

## branch 목록 조회

```bash
curl -fsS \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<owner>/<repo>/branches"
```

`context.git.ref` 는 실제 존재하는 branch 또는 commit SHA 로 맞춥니다.
