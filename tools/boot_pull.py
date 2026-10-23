#!/usr/bin/env python3
"""Le o oneservice e o ContentList original para preparar o boot hook."""
from __future__ import annotations

import asyncio
import os
import base64
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import Tv  # noqa: E402
from tv_agent import Agent  # noqa: E402
import root  # noqa: E402

TARGET = "/usr/apps/com.samsung.tv.glscreensaver-launcher/res/ContentList.json"
OUT = pathlib.Path(__file__).resolve().parent / "diagnostics"


async def main() -> int:
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
            print("== Removendo bind-mount atual")
            await connection.execute(
                f"nsenter -t 1 -m -- umount {TARGET} 2>/dev/null || true", 30
            )
            stock = await connection.execute(
                f"nsenter -t 1 -m -- sha256sum {TARGET}; "
                f"nsenter -t 1 -m -- wc -c {TARGET}; "
                f"nsenter -t 1 -m -- base64 {TARGET}",
                30,
            )
            print(stock.stdout)
            (OUT / "stock-contentlist.txt").write_text(stock.stdout, encoding="utf-8")

            print("== Copiando oneservice")
            await connection.execute(
                f"cp /opt/etc/systemd/oneservice {root.STAGING_ROOT}/{package}/oneservice",
                30,
            )
            data = await connection.read_file(
                f"{root.STAGING_ROOT}/{package}/oneservice"
            )
            (OUT / "oneservice.bin").write_bytes(data.data)
            print(f"oneservice: {len(data.data)} bytes")
            return 0
        finally:
            await root.release(connection, server, agent, package, assessment)
    finally:
        agent.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(asyncio.run(main()))
