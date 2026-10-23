#!/usr/bin/env python3
"""Troca o conteudo do screensaver nativo por um app instalado (teste/rollback)."""
from __future__ import annotations

import asyncio
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import STAGING, Tv  # noqa: E402
from tv_agent import Agent  # noqa: E402
import root  # noqa: E402

TARGET = "/usr/apps/com.samsung.tv.glscreensaver-launcher/res/ContentList.json"
BACKUP = f"{STAGING}/KurumiSaver-ContentList.original.json"
STAGED = f"{STAGING}/KurumiSaver-ContentList.json"
LAUNCHER = "com.samsung.tv.glscreensaver-launcher"
OLD_CONTENT = "com.samsung.tv.spotlight-ss"


def content_json(app_id: str) -> str:
    return (
        '{\n  "duration": "36000",\n  "contents": [\n'
        f'    "{app_id}"\n  ]\n}}\n'
    )


async def main() -> int:
    app_id = sys.argv[1] if len(sys.argv) > 1 else "KurumiSvr1.Saver"
    import os
    tv = Tv(os.environ.get("KURUMI_TV", "192.168.1.50"))
    tv.connect()
    agent = Agent(tv)
    print("== Abrindo shell persistente")
    agent.start()
    try:
        connection, server, package, assessment = await root.acquire(
            agent, tv.host, tv.callback, 60
        )
        try:
            print("== Preparando ContentList.json")
            await connection.execute(
                f"cp --preserve=all {TARGET} {BACKUP} 2>/dev/null || true",
                30,
            )
            await connection.execute(
                f"printf '%s' '{content_json(app_id)}' > {STAGED}",
                30,
            )
            await connection.execute(f"chmod 644 {STAGED}", 30)
            print((await connection.execute(f"ls -lZ {STAGED}", 30)).stdout)
            print("== Bind-mount no namespace do PID 1")
            result = await connection.execute(
                f"nsenter -t 1 -m -- mount --bind {STAGED} {TARGET}", 30
            )
            if result.exit_code != 0:
                print(result.stderr)
                return 1
            print((await connection.execute(
                f"nsenter -t 1 -m -- cat {TARGET}", 30
            )).stdout)

            print("== Reiniciando o launcher do screensaver")
            agent.run(f"app_launcher -t {app_id}", 60)
            # O app_launcher como sdk pode nao derrubar apps do owner; root
            # derruba o launcher/conteudo antigo para reler o ContentList.json.
            await connection.execute(
                "for p in $(ps -eo pid,comm | awk '$2 ~ /^ScreenSaver/ {print $1}'); "
                "do kill $p; done",
                30,
            )
            await asyncio.sleep(3)
            agent.run(f"app_launcher -s {LAUNCHER}", 60)
            await asyncio.sleep(4)
            output, code = agent.run(
                f"app_launcher -r {app_id}; "
                "vconftool get memory/appfw/current_fullscreen_appid; "
                f"ps -ef | grep -E 'KurumiSvr1|glscreensaver|spotlight' | grep -v grep",
                60,
            )
            print(output)
            return 0 if code == 0 else code
        finally:
            await root.release(connection, server, agent, package, assessment)
    finally:
        agent.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(asyncio.run(main()))
