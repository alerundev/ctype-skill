# GitHub 작업 가이드

기본 인증은 `GITHUB_TOKEN` 하나입니다. GitHub personal access token classic 에 `repo` scope 를 부여해 환경변수로 제공합니다. `gh` 가 이미 로그인되어 있으면 써도 되지만 기본 전제는 아닙니다.

## 새 repo 생성

```bash
curl -fsS -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/user/repos \
  -d '{"name":"<repo>","private":false}'
```

응답의 `html_url`, `clone_url`, `default_branch`, `owner.login` 을 확인합니다.

## commit / push

토큰을 remote URL 에 넣지 말고 push 시 HTTP header 로만 전달합니다. 샌드박스의 commit signing 오류를 피하기 위해 repo local signing 을 끕니다.

```bash
git config --local commit.gpgsign false || true
git add .
git commit --no-gpg-sign -m "Initial Cloudtype deployment"
git branch -M main
git remote add origin https://github.com/<owner>/<repo>.git
git -c http.https://github.com/.extraheader="Authorization: Bearer $GITHUB_TOKEN" push -u origin main
```

이미 remote 가 있으면 `git remote set-url origin https://github.com/<owner>/<repo>.git`.

## branch 목록 조회

```bash
curl -fsS \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<owner>/<repo>/branches"
```

`context.git.ref` 는 실제 존재하는 branch 또는 commit SHA 로 맞춥니다.
