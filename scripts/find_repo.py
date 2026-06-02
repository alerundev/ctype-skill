#!/usr/bin/env python3
"""
Cloudtype 콘솔에 연동된 GitHub repo 목록에서 사용자 발화 키워드로 매칭.

CLI 가 노출하지 않는 기능이라 보조 API 사용:
  GET /oauth/github/has              연동 여부
  GET /oauth/github/accounts          연동된 GitHub 계정 (installationid)
  GET /oauth/github/repository/<inst> repo 목록 (이름, URL, defaultbranch, ...)

사용법:
    python scripts/find_repo.py <키워드>          # 사용자 발화 단어 (예: "주소 축약기")
    python scripts/find_repo.py --list            # 그냥 전체 목록만 (이름·URL·기본브랜치)
    python scripts/find_repo.py --branches <URL>  # 특정 repo 의 전체 브랜치 목록

종료 코드:
    0  → 후보 1개 자동 확정. stdout: "url=<URL> branch=<BRANCH> name=<NAME>"
    2  → 후보 여러 개. stderr: 번호 매긴 선택지. 호출자가 사용자에게 제시.
    1  → 그 외 모든 실패 (미연동, 검색 결과 없음, 인증 실패 등). stderr 에 명확한 메시지.

필요한 환경:
    CLOUDTYPE_API_KEY 환경변수
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.cloudtype.io"


def die(code: int, msg: str):
    print(msg, file=sys.stderr)
    sys.exit(code)


def get_apikey() -> str:
    key = os.environ.get("CLOUDTYPE_API_KEY", "").strip()
    if not key:
        die(1, "ERROR: CLOUDTYPE_API_KEY 환경변수가 비어 있습니다.")
    return key


def api_get(path: str, key: str):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        die(1, f"ERROR: GET {path} → HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        die(1, f"ERROR: GET {path} → {e}")
    except json.JSONDecodeError as e:
        die(1, f"ERROR: GET {path} → JSON decode 실패: {e}")


def fetch_accounts(key: str):
    """연동 여부 + 계정 목록을 한 번에. 한 함수에서 분기까지 정리."""
    has = api_get("/oauth/github/has", key)
    if not isinstance(has, dict) or not has.get("has"):
        die(1, "ERROR: Cloudtype 콘솔에 GitHub 가 연동돼 있지 않습니다. 콘솔에서 연동 후 다시 시도하세요.")

    accounts = api_get("/oauth/github/accounts", key)
    if not isinstance(accounts, list) or not accounts:
        die(1, "ERROR: 연동된 GitHub 계정이 없습니다. 콘솔에서 GitHub 계정을 추가하세요.")
    return accounts


def fetch_all_repos(accounts, key: str):
    """모든 계정의 repo 합쳐서 반환. 계정 한 개든 여러 개든 호출자 입장에서 동일."""
    all_repos = []
    for acc in accounts:
        inst = acc.get("installationid")
        if not inst:
            continue
        repos = api_get(f"/oauth/github/repository/{inst}", key)
        if isinstance(repos, list):
            for r in repos:
                # account 이름은 매칭/표시에 유용해서 같이 박음
                r["_account"] = acc.get("name", "")
            all_repos.extend(repos)
    if not all_repos:
        die(1, "ERROR: 연동된 GitHub 계정에 접근 가능한 repo 가 없습니다.")
    return all_repos


def normalize(s: str) -> str:
    """매칭용 정규화: 소문자 + 영숫자/한글만 남김 + 공백 제거."""
    s = s.lower()
    s = re.sub(r"[\s_\-./]+", "", s)
    return s


def match_repos(repos, keyword: str):
    """이름/풀이름/설명에 키워드 부분일치하는 repo 만 추림."""
    kw = normalize(keyword)
    if not kw:
        return repos
    hits = []
    for r in repos:
        name = normalize(r.get("name", ""))
        full = normalize(r.get("fullname") or r.get("full_name") or "")
        desc = normalize(r.get("description") or "")
        if kw in name or kw in full or kw in desc:
            hits.append(r)
    return hits


def emit_choice_one(r):
    """후보 1개 — stdout 으로 url/branch/name 출력 후 exit 0."""
    url = r.get("url") or r.get("htmlurl") or r.get("html_url")
    branch = r.get("defaultbranch") or r.get("default_branch") or "main"
    name = r.get("name", "")
    if not url:
        die(1, f"ERROR: 매칭된 repo '{name}' 에 URL 이 없습니다. (서버 응답 형식 변동 가능성)")
    print(f"url={url}")
    print(f"branch={branch}")
    print(f"name={name}")
    sys.exit(0)


def emit_choice_many(hits, keyword: str):
    """후보 여러 개 — stderr 로 번호 매긴 선택지. exit 2."""
    print(f"AMBIGUOUS: '{keyword}' 와 매칭되는 repo 가 여러 개 있습니다. 사용자에게 어떤 걸 선택할지 확인하세요.", file=sys.stderr)
    for i, r in enumerate(hits, 1):
        url = r.get("url") or r.get("htmlurl") or r.get("html_url") or ""
        branch = r.get("defaultbranch") or r.get("default_branch") or "main"
        acc = r.get("_account", "")
        print(f"  [{i}] {r.get('name','?'):30s}  {url}  (branch={branch}, account={acc})", file=sys.stderr)
    sys.exit(2)


def list_all(repos):
    """--list: 전체 목록을 stdout 으로 (호출자가 사용자에게 직접 보여줄 때)."""
    for r in repos:
        url = r.get("url") or r.get("htmlurl") or r.get("html_url") or ""
        branch = r.get("defaultbranch") or r.get("default_branch") or "main"
        acc = r.get("_account", "")
        print(f"{r.get('name','?')}\t{url}\t{branch}\t{acc}")
    sys.exit(0)


def extract_owner_repo(url: str):
    """GitHub URL 에서 (owner, repo) 추출. .git 제거, 대소문자 유지."""
    m = re.match(r"^(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/?#]+?)(?:\.git)?/?$", url.strip())
    if not m:
        die(1, f"ERROR: GitHub URL 경로를 인식하지 못했습니다: {url}")
    return m.group(1), m.group(2)


def branches_for_url(target_url: str, key: str):
    """--branches <URL>: 해당 repo 의 전체 브랜치 목록을 stdout 에 한 줄씩."""
    owner, name = extract_owner_repo(target_url)
    accounts = fetch_accounts(key)

    # owner 와 계정명이 맞는 installation 우선, 못 찾으면 모든 계정을 순회
    candidates = [a for a in accounts if a.get("name", "").lower() == owner.lower()] or accounts

    last_err = None
    for acc in candidates:
        inst = acc.get("installationid")
        if not inst:
            continue
        try:
            req = urllib.request.Request(
                API + f"/oauth/github/repository/{inst}/{name}/branch",
                headers={"Authorization": f"Bearer {key}"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, list):
                for b in data:
                    print(b)
                sys.exit(0)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} {e.reason}"
            continue
        except urllib.error.URLError as e:
            last_err = str(e)
            continue

    die(1, f"ERROR: repo '{owner}/{name}' 의 브랜치 목록을 조회하지 못했습니다. ({last_err or 'no candidate'})")


def main():
    p = argparse.ArgumentParser(description="Cloudtype 연동 GitHub repo 매칭")
    p.add_argument("keyword", nargs="?", help="매칭할 키워드 (사용자 발화 단어)")
    p.add_argument("--list", action="store_true", help="전체 목록 출력 (탭 구분, 매칭 안 함)")
    p.add_argument("--branches", metavar="URL", help="특정 repo URL 의 전체 브랜치 목록")
    args = p.parse_args()

    key = get_apikey()

    # --branches 는 자체 흐름 (repo 목록 전체 fetch 의존 X)
    if args.branches:
        branches_for_url(args.branches, key)

    accounts = fetch_accounts(key)
    repos = fetch_all_repos(accounts, key)

    if args.list:
        list_all(repos)

    if not args.keyword:
        die(1, "ERROR: 키워드가 필요합니다. 사용법: find_repo.py <키워드> 또는 --list 또는 --branches <URL>")

    hits = match_repos(repos, args.keyword)

    if len(hits) == 0:
        die(1, f"ERROR: '{args.keyword}' 와 매칭되는 repo 가 없습니다. --list 로 전체 목록을 확인하거나 콘솔에서 연동 추가 후 재시도.")
    if len(hits) == 1:
        emit_choice_one(hits[0])
    else:
        emit_choice_many(hits, args.keyword)


if __name__ == "__main__":
    main()
