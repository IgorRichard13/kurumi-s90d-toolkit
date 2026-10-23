#!/usr/bin/env python3
"""Coloca/tira o screensaver Kurumi no launcher nativo do S90D.

O `com.samsung.tv.glscreensaver-launcher` le o ContentList.json em /usr, que e
read-only. O script faz um bind-mount de uma copia em /home/owner/... no
namespace de mount do PID 1. O bind-mount vale ate o reboot; depois de reiniciar,
rode `apply` de novo (ou use o reapply.ps1).

    py -3 tools/saver.py apply --yes
    py -3 tools/saver.py restore --yes
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import STAGING, Tv  # noqa: E402
from tv_agent import Agent  # noqa: E402
import root  # noqa: E402

APP_ID = "KurumiSvr1.Saver"
TARGET = "/usr/apps/com.samsung.tv.glscreensaver-launcher/res/ContentList.json"
STOCK = "com.samsung.tv.spotlight-ss"
BACKUP = f"{STAGING}/KurumiSaver-ContentList.original.json"
STAGED = f"{STAGING}/KurumiSaver-ContentList.json"
LAUNCHER = "com.samsung.tv.glscreensaver-launcher"
DEFAULT_HOST = "192.168.1.50"


def content_json(app_id: str) -> str:
    return (
        '{\n  "duration": "36000",\n  "contents": [\n'
        f'    "{app_id}"\n  ]\n}}\n'
    )


async def run(action: str, host: str, launch: bool) -> int:
    tv = Tv(host)
    tv.connect()
    agent = Agent(tv)
    print("== Abrindo shell persistente")
    agent.start()
    try:
        connection, server, package, assessment = await root.acquire(
            agent, tv.host, tv.callback, 60
        )
        try:
            if action == "apply":
                print("== Preparando ContentList.json")
                await connection.execute(
                    f"cp --preserve=all {TARGET} {BACKUP} 2>/dev/null || true", 30
                )
                await connection.execute(
                    f"printf '%s' '{content_json(APP_ID)}' > {STAGED}", 30
                )
                await connection.execute(f"chmod 644 {STAGED}", 30)

                print("== Bind-mount no namespace do PID 1")
                await connection.execute(
                    f"nsenter -t 1 -m -- umount {TARGET} 2>/dev/null || true", 30
                )
                result = await connection.execute(
                    f"nsenter -t 1 -m -- mount --bind {STAGED} {TARGET}", 30
                )
                if result.exit_code != 0:
                    print(result.stderr)
                    return 1
                shown = await connection.execute(
                    f"nsenter -t 1 -m -- cat {TARGET}", 30
                )
                print(shown.stdout)

                if launch:
                    print("== Reiniciando o launcher para testar")
                    agent.run(f"app_launcher -t {APP_ID}", 60)
                    await connection.execute(
                        "for p in $(ps -eo pid,comm | awk "
                        "'$2 ~ /^ScreenSaver/ {print $1}'); do kill $p; done",
                        30,
                    )
                    await asyncio.sleep(3)
                    agent.run(f"app_launcher -s {LAUNCHER}", 60)
                    await asyncio.sleep(3)
                    output, _ = agent.run(
                        f"app_launcher -r {APP_ID}; "
                        "vconftool get memory/appfw/current_fullscreen_appid",
                        60,
                    )
                    print(output)
                return 0

            if action == "restore":
                print("== Removendo o bind-mount do screensaver")
                await connection.execute(
                    f"nsenter -t 1 -m -- umount {TARGET} 2>/dev/null || true", 30
                )
                shown = await connection.execute(
                    f"nsenter -t 1 -m -- cat {TARGET}", 30
                )
                print(shown.stdout)
                if STOCK not in shown.stdout:
                    print(
                        "aviso: o ContentList.json nao voltou ao conteudo original",
                        file=sys.stderr,
                    )
                    return 1
                return 0

            print(f"acao invalida: {action}", file=sys.stderr)
            return 2
        finally:
            await root.release(connection, server, agent, package, assessment)
    finally:
        agent.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tv", default=DEFAULT_HOST)
    sub = parser.add_subparsers(dest="action", required=True)
    apply_parser = sub.add_parser("apply", help="aponta o screensaver para o Kurumi Saver")
    apply_parser.add_argument("--yes", action="store_true")
    apply_parser.add_argument("--no-launch", action="store_true", help="nao reinicia o launcher agora")
    restore_parser = sub.add_parser("restore", help="volta ao screensaver original da Samsung")
    restore_parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if args.action in ("apply", "restore") and not args.yes:
        answer = input("Alterar o screensaver da TV? [s/N] ").strip().lower()
        if answer not in ("s", "sim", "y", "yes"):
            return 2

    launch = args.action == "apply" and not getattr(args, "no_launch", False)
    return asyncio.run(run(args.action, args.tv, launch))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
