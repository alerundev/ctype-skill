# GitHub 작업 가이드

기본 인증은 `GITHUB_TOKEN` 하나입니다. 사전 준비는 Cloudtype 콘솔에서 GitHub 계정을 OAuth 로 연동하고, 그 GitHub 계정에서 personal access token classic (`repo` scope) 을 발급해 `GITHUB_TOKEN` 으로 제공하는 것입니다. `gh` 가 이미 로그인되어 있으면 써도 되지만 기본 전제는 아닙니다.

Cloudtype scope 이름과 GitHub owner 이름은 다를 수 있습니다. repo owner 와 `context.git.url` 의 owner 는 Cloudtype 에 연동된 GitHub 계정 기준으로 맞춥니다. Cloudtype scope 를 GitHub owner 로 추측하지 않습니다.

## Cloudtype GitHub 연동 확인

```bash
curl -fsS \
  -H "Authorization: Bearer $CLOUDTYPE_API_KEY" \
  "https://api.cloudtype.io/oauth/github/accounts"
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

```yaml
# context.git.url 의 owner 는 Cloudtype scope 가 아니라 위 name
context:
  git:
    url: https://github.com/<github-owner>/<repo>
    ref: main
```


`GITHUB_TOKEN` 을 발급한 GitHub 사용자명과 commit email 은 GitHub API 로 확인합니다. public email 이 없으면 GitHub noreply 주소를 사용합니다.

```bash
curl -fsS \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/user \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["login"]); print(d.get("email") or (str(d["id"])+"+"+d["login"]+"@users.noreply.github.com"))'
```

일반 경로에서는 Cloudtype 연동 계정 `name` 과 token owner `login` 이 같아야 합니다. 다르면 어느 계정/owner 에 repo 를 만들지 사용자에게 확인합니다.

## 새 repo 생성

Cloudtype 연동 계정 `name` 과 token owner `login` 이 같은 개인 계정이면 `/user/repos` 로 생성합니다.

```bash
curl -fsS -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/user/repos \
  -d '{"name":"<repo>","private":false}'
```

응답의 `html_url`, `clone_url`, `default_branch`, `owner.login` 을 확인합니다. `context.git.url` 에는 이 `html_url` 의 owner/repo 를 사용합니다.

## commit / push

managed-agent 샌드박스에는 보통 credential helper 와 전역 git author/signing 설정이 없습니다. repo local 설정 후 토큰이 포함된 HTTPS remote 를 임시로 사용합니다. `<github-username>` 은 위 GitHub `/user` 응답의 `login`, `<owner>` 는 repo owner 입니다. push 후 remote 를 깨끗한 URL 로 되돌립니다.

```bash
git config --local user.name "<github-username>"
git config --local user.email "<github-email-or-noreply>"
git config --local commit.gpgsign false || true
git add .
git commit --no-gpg-sign -m "Initial Cloudtype deployment"
git branch -M main
git remote add origin https://github.com/<owner>/<repo>.git
git remote set-url origin "https://<github-username>:${GITHUB_TOKEN}@github.com/<owner>/<repo>.git"
GIT_TERMINAL_PROMPT=0 git push -u origin main
git remote set-url origin https://github.com/<owner>/<repo>.git
```

`git branch -M main` 은 remote 설정/push 전에 실행합니다. 그래야 `context.git.ref: main` 과 실제 branch 가 어긋나지 않습니다. Contents API 나 zip 업로드를 기본 fallback 으로 사용하지 않습니다.

## branch 목록 조회

```bash
curl -fsS \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<owner>/<repo>/branches"
```

`context.git.ref` 는 실제 존재하는 branch 또는 commit SHA 로 맞춥니다.
