#!/usr/bin/env python3
"""
Cloudtype 빌드/실행 로그 스트리밍 헬퍼.

CLI 는 실행 로그 (running container stdout) 도 보여주지만,
빌드 단계 로그 (이미지 빌드/시작 시도 중 실패) 는 보여주지 않는다.
이 스크립트는 두 종류 로그를 모두 WebSocket 으로 가져온다.

사용법:
    python scripts/logs.py build <deployment>      # 빌드 로그 (1회성, 완료 시 종료)
    python scripts/logs.py run <deployment>        # 실행 로그 (기본 1회성, 최근 200줄)
    python scripts/logs.py run <deployment> -f     # 실행 로그 follow

필요한 환경:
    CLOUDTYPE_API_KEY 환경변수
    CLOUDTYPE_WS_BASE 환경변수 (선택, 기본 wss://api.cloudtype.io)
    ctype 가 PATH 에 있고 `ctype use` 로 컨텍스트 설정됨
    pip install websockets
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from typing import Tuple

try:
    import websockets
except ImportError:
    print("ERROR: websockets 라이브러리가 필요합니다. `pip install websockets`", file=sys.stderr)
    sys.exit(2)


DEFAULT_WS_BASE = "wss://api.cloudtype.io"
ENDPOINTS = {
    "build": "/project/build/logs",
    "run":   "/project/logs",
}


def get_context() -> Tuple[str, str, str]:
    """`ctype use` 출력에서 scope/project/stage 파싱."""
    try:
        out = subprocess.check_output(["ctype", "use"], text=True, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR: `ctype use` 실패: {e}", file=sys.stderr)
        sys.exit(2)

    # 출력 예: "@myspace/myproject:main on cluster-X"
    m = re.search(r"@([^/]+)/([^:]+):(\S+)", out)
    if not m:
        print(f"ERROR: `ctype use` 출력에서 컨텍스트를 찾지 못했습니다:\n{out}", file=sys.stderr)
        print("`ctype use @<scope>/<project>:<stage>` 로 먼저 설정하세요.", file=sys.stderr)
        sys.exit(2)
    return m.group(1), m.group(2), m.group(3)


def get_apikey() -> str:
    key = os.environ.get("CLOUDTYPE_API_KEY", "").strip()
    if not key:
        print("ERROR: CLOUDTYPE_API_KEY 환경변수가 비어 있습니다.", file=sys.stderr)
        sys.exit(2)
    return key


def get_ws_base() -> str:
    return (os.environ.get("CLOUDTYPE_WS_BASE") or DEFAULT_WS_BASE).strip().rstrip("/")


async def stream(kind: str, deployment: str, follow: bool, tail: int, previous: bool, timestamps: bool):
    scope, project, stage = get_context()
    key = get_apikey()
    url = get_ws_base() + ENDPOINTS[kind]

    envelope = {
        "type": "prepare",
        "params": {
            "scope": scope,
            "project": project,
            "stage": stage,
            "deployment": deployment,
            "options": {
                "follow": follow,
                "pretty": False,
                "tailLines": tail,
                "previous": previous,
                "timestamps": timestamps,
            },
        },
        "headers": {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
        },
    }

    try:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps(envelope))
            first = await ws.recv()
            if isinstance(first, bytes):
                first = first.decode("utf-8", errors="replace")
            if first.strip() != "accept":
                # 서버가 accept 가 아닌 다른 메시지 (보통 에러) 를 보낸 경우
                print(first, end="" if first.endswith("\n") else "\n", file=sys.stderr)
                sys.exit(1)

            async for frame in ws:
                if isinstance(frame, bytes):
                    frame = frame.decode("utf-8", errors="replace")
                sys.stdout.write(frame)
                sys.stdout.flush()
    except websockets.exceptions.ConnectionClosedOK:
        return
    except websockets.exceptions.ConnectionClosedError as e:
        # follow=false 일 때 서버가 데이터 전송 후 닫는 게 정상
        if not follow:
            return
        print(f"\n[connection closed: {e}]", file=sys.stderr)
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="Cloudtype 빌드/실행 로그 스트리밍")
    p.add_argument("kind", choices=["build", "run"], help="로그 종류")
    p.add_argument("deployment", help="deployment 이름 (app.yaml 의 name)")
    p.add_argument("-f", "--follow", action="store_true", help="follow 모드 (기본: off)")
    p.add_argument("-l", "--tail", type=int, default=200, help="가져올 최근 줄 수 (기본: 200)")
    p.add_argument("-p", "--previous", action="store_true", help="이전 컨테이너 로그 (재시작 직전, run 만 의미 있음)")
    p.add_argument("--no-timestamps", action="store_true", help="타임스탬프 숨기기")
    args = p.parse_args()

    # 빌드 로그는 기본적으로 끝까지 받고 종료하는 게 자연스러움 → follow on
    # 실행 로그는 기본 1회성 (최근 N줄) → follow off, -f 로 켬
    follow = True if args.kind == "build" else args.follow

    asyncio.run(stream(
        kind=args.kind,
        deployment=args.deployment,
        follow=follow,
        tail=args.tail,
        previous=args.previous,
        timestamps=not args.no_timestamps,
    ))


if __name__ == "__main__":
    main()
