#!/usr/bin/env python3
"""Confere o estado depois de um reboot: Home, updates, debloat e memoria."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import Tv  # noqa: E402
from tv_agent import Agent  # noqa: E402

HELPER = "/home/owner/share/tmp/sdk_tools/KurumiHomeControl.dll"


def main() -> int:
    tv = Tv(sys.argv[1] if len(sys.argv) > 1 else "192.168.1.50")
    tv.connect()
    agent = Agent(tv)
    print("== Abrindo shell persistente")
    agent.start()
    try:
        commands = {
            "home": f"test -f {HELPER} && /usr/bin/dotnet {HELPER} query || echo helper-ausente",
            "updates": 'for k in db/menu/support/softwareupdate/autoupdate db/menu/support/softwareupdate/preupdate_consent; do vconftool get "$k"; done',
            "pacotes": 'sqlite3 -readonly /opt/dbspace/.pkgmgr_parser.db "select count(*) from package_info;"',
            "processos": "ps -ef 2>&1 | grep -E 'csfs|HomeMedia|HomeSidebar|HomeArt|art-app|gaminghub|bixby|smartthings|slive' | grep -v grep",
            "memoria": 'grep -E "^(MemTotal|MemAvailable|SwapTotal|SwapFree):" /proc/meminfo; echo; cat /sys/block/zram0/mm_stat 2>/dev/null',
            "boot": 'grep -E "^(Model|Version|Build)=" /etc/prd_info.ini; cat /proc/uptime',
        }
        for label, command in commands.items():
            output, code = agent.run(command, timeout=60)
            print(f"\n######## {label} (exit {code})\n{output}")
        return 0
    finally:
        agent.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
