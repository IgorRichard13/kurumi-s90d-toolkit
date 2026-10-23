#!/usr/bin/env python3
"""Prepara os artefatos do boot hook a partir da TV (sem alterar a TV).

Le /opt/etc/systemd/oneservice e o ContentList stock, gera
tools/diagnostics/oneservice.patched e boot-meta.json. O boot_install.py usa
esses arquivos; o Boot.dll tem hashes fixos desta firmware, entao confira os
hashes impressos e atualize tools/boot-hook/Program.cs se necessario.

    py -3 tools/boot_prepare.py
    py -3 tools/boot_install.py install
"""
from __future__ import annotations

import asyncio
import os
import base64
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import Tv  # noqa: E402
from tv_agent import Agent  # noqa: E402
import root  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "diagnostics"
BOOT = HERE / "boot-hook"
TARGET = "/usr/apps/com.samsung.tv.glscreensaver-launcher/res/ContentList.json"
SERVICE = "/opt/etc/systemd/oneservice"
TABLE = SERVICE + ".table"


def patch_oneservice(data: bytes) -> tuple[bytes, int]:
    end = data.index(b"_EOF")
    first = data[:end]
    if b"ExecStart=/opt/etc/parseinfo.sh &" not in first:
        raise RuntimeError("a primeira unit do oneservice nao e a esperada")
    new = (
        b"[Unit]\n"
        b"After=buxton2.service systemd-udevd.service connman.service net-config.service deviced.service\n"
        b"[Service]\n"
        b"ExecStart=/usr/bin/dotnet /opt/minimal-saver/Boot.dll\n"
    )
    if len(new) + 2 > end:
        raise RuntimeError("a primeira unit do oneservice e curta demais para o patch")
    patched_first = new + b"#" + b" " * (end - len(new) - 2) + b"\n"
    return patched_first + data[end:], end


async def run(connection, command: str, timeout: float = 60) -> str:
    result = await connection.execute(command, timeout)
    if result.exit_code != 0:
        raise RuntimeError(f"comando falhou: {command}\n{result.stdout}{result.stderr}")
    return result.stdout


async def raw(connection, command: str, timeout: float = 60):
    return await connection.execute(command, timeout)


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def main() -> int:
    OUT.mkdir(exist_ok=True)
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
            print("== Lendo ContentList stock")
            await raw(connection, f"nsenter -t 1 -m -- umount {TARGET} 2>/dev/null || true")
            stock_hash = (await run(connection, f"nsenter -t 1 -m -- sha256sum {TARGET}")).split()[0]
            stock_b64 = await run(connection, f"nsenter -t 1 -m -- base64 {TARGET}")
            stock = base64.b64decode(stock_b64)
            if hashlib.sha256(stock).hexdigest() != stock_hash:
                raise RuntimeError("hash do ContentList stock nao confere")
            print("stock", stock_hash, len(stock), "bytes")

            table_hash = (await run(connection, f"sha256sum {TABLE}")).split()[0]
            parse_hash = (await run(connection, "sha256sum /opt/etc/parseinfo.sh")).split()[0]
            await run(connection, f"cp {SERVICE} {root.STAGING_ROOT}/{package}/oneservice")
            data = (await connection.read_file(f"{root.STAGING_ROOT}/{package}/oneservice")).data
            (OUT / "oneservice.bin").write_bytes(data)
            patched, end = patch_oneservice(data)
            (OUT / "oneservice.patched").write_bytes(patched)

            meta = {
                "original": hashlib.sha256(data).hexdigest(),
                "table": table_hash,
                "patched": hashlib.sha256(patched).hexdigest(),
                "stock_contentlist": stock_hash,
                "custom_contentlist": sha(BOOT / "ContentList.json"),
                "parseinfo": parse_hash,
                "oneservice_first_unit_end": end,
            }
            if (BOOT / "out" / "Boot.dll").is_file():
                meta["boot_dll"] = sha(BOOT / "out" / "Boot.dll")
            (OUT / "boot-meta.json").write_text(
                json.dumps(meta, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(meta, indent=2))
            print("\nSe os hashes de stock_contentlist/parseinfo/boot_dll nao baterem")
            print("com as constantes de tools/boot-hook/Program.cs, atualize e recompile.")
            return 0
        finally:
            await root.release(connection, server, agent, package, assessment)
    finally:
        agent.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(asyncio.run(main()))
