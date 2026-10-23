#!/usr/bin/env python3
"""Instala/remove o boot hook do Kurumi Saver no AT-HUB do S90D.

O hook troca o ExecStart da primeira unit do cache /opt/etc/systemd/oneservice
por /usr/bin/dotnet /opt/minimal-saver/Boot.dll. O Boot.dll roda o
/opt/etc/parseinfo.sh original e monta o ContentList.json do Kurumi por cima do
launcher de screensaver, em modo somente-leitura.

    py -3 tools/boot_install.py install
    py -3 tools/boot_install.py restore
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import STAGING, Tv  # noqa: E402
from tv_agent import Agent  # noqa: E402
import root  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
BOOT = HERE / "boot-hook"
OUT = BOOT / "out"
STATE = "/opt/minimal-saver"
TARGET = "/usr/apps/com.samsung.tv.glscreensaver-launcher/res/ContentList.json"
SERVICE = "/opt/etc/systemd/oneservice"
PATCHED_HASH = "d8c2d011fe485f8b5076a2e80316d233508235e0ef7dfbb1080768c2f130f309"
ORIGINAL_HASH = "60a17f7bf53a5c0be1d4b4fb0f17c3415d0480b73901e91ff139b5aca550dbce"
TABLE_HASH = "cfbee9145724c7258a4a4895d54cb418372a71db4d6a49b61299f6726d400840"
META = HERE / "diagnostics" / "boot-meta.json"
FILES = ("Boot.dll", "Boot.runtimeconfig.json", "Boot.deps.json")


async def run(connection, command: str, timeout: float = 60) -> str:
    result = await connection.execute(command, timeout)
    if result.exit_code != 0:
        raise RuntimeError(
            f"comando falhou ({result.exit_code}): {command}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result.stdout


async def raw(connection, command: str, timeout: float = 60):
    return await connection.execute(command, timeout)


def hash_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def install(tv: Tv, agent: Agent) -> int:
    connection, server, package, assessment = await root.acquire(
        agent, tv.host, tv.callback, 60
    )
    try:
        meta = json.loads(META.read_text(encoding="utf-8")) if META.is_file() else {}
        original = meta.get("original", ORIGINAL_HASH)
        table_expected = meta.get("table", TABLE_HASH)
        patch = meta.get("patched", PATCHED_HASH)
        patch_path = HERE / "diagnostics" / "oneservice.patched"
        if not patch_path.is_file() or hash_file(patch_path) != patch:
            raise RuntimeError(
                "oneservice.patched ausente ou diferente do boot-meta.json; "
                "rode tools/boot_prepare.py"
            )

        print("== Conferindo hashes da cache de boot")
        service_hash = (await run(connection, f"sha256sum {SERVICE}")).split()[0]
        table_hash = (await run(connection, f"sha256sum {SERVICE}.table")).split()[0]
        if table_hash != table_expected:
            raise RuntimeError("oneservice.table mudou; firmware diferente; revalide o hook")
        if service_hash == patch:
            backup = await raw(connection, f"test -e {STATE}/oneservice.original && echo yes")
            if "yes" not in backup.stdout:
                raise RuntimeError("cache ja patchada e backup original ausente; revalide")
        elif service_hash != original:
            raise RuntimeError("oneservice mudou; firmware diferente; revalide o hook")
        print("service", service_hash, "table", table_hash, "patch", patch)

        print("== Backups em", STATE)
        await run(connection, f"/bin/mkdir -p {STATE}")
        await run(connection, f"chmod 700 {STATE}")
        for source, name in (
            (SERVICE, "oneservice.original"),
            (SERVICE + ".table", "oneservice.table.original"),
            ("/opt/etc/parseinfo.sh", "parseinfo.original.sh"),
        ):
            await run(
                connection,
                f"[ -e {STATE}/{name} ] || cp --preserve=all {source} {STATE}/{name}",
            )

        # O target precisa estar stock para o backup e para o teste do helper.
        await raw(connection, f"nsenter -t 1 -m -- umount {TARGET} 2>/dev/null || true")
        await run(
            connection,
            f"[ -e {STATE}/ContentList.original.json ] || "
            f"cp --preserve=all {TARGET} {STATE}/ContentList.original.json",
        )

        print("== Enviando Boot.dll e ContentList")
        agent.push(OUT / "Boot.dll", f"{STAGING}/Boot.dll")
        agent.push(OUT / "Boot.runtimeconfig.json", f"{STAGING}/Boot.runtimeconfig.json")
        agent.push(OUT / "Boot.deps.json", f"{STAGING}/Boot.deps.json")
        agent.push(BOOT / "ContentList.json", f"{STAGING}/KurumiBoot-ContentList.json")
        agent.push(
            HERE / "diagnostics" / "oneservice.patched",
            f"{STAGING}/oneservice.patched",
        )
        await run(connection, f"cp --preserve=all {STAGING}/KurumiBoot-ContentList.json {STATE}/ContentList.json")
        await run(connection, f"chmod 644 {STATE}/ContentList.json")
        for name in FILES:
            await run(connection, f"cp --preserve=all {STAGING}/{name} {STATE}/{name}")
            await run(connection, f"chown 0:0 {STATE}/{name}")
            await run(connection, f"chmod 600 {STATE}/{name}")
        await run(connection, f": > {STATE}/enabled")
        await run(connection, f"chmod 600 {STATE}/enabled")

        print("== Testando o Boot.dll no namespace do PID 1")
        test = await raw(
            connection,
            f"nsenter -t 1 -m -- /usr/bin/dotnet {STATE}/Boot.dll",
            60,
        )
        print(test.stdout)
        if test.stderr:
            print(test.stderr)
        log = await run(connection, f"cat {STATE}/last-boot.log")
        print(log)
        if "active:" not in log and "already active" not in log:
            raise RuntimeError("Boot.dll nao ativou o ContentList; cache nao foi alterada")
        current = await run(connection, f"nsenter -t 1 -m -- cat {TARGET}")
        print(current)
        if "KurumiSvr1.Saver" not in current:
            raise RuntimeError("target nao mostra o app do Kurumi; cache nao foi alterada")

        print("== Patch da cache de boot")
        await run(
            connection,
            f"cp --preserve=all {SERVICE} {SERVICE}.kurumi-new",
        )
        await run(
            connection,
            f"cat {STAGING}/oneservice.patched > {SERVICE}.kurumi-new",
        )
        observed = await run(connection, f"sha256sum {SERVICE}.kurumi-new")
        print(observed)
        if observed.split()[0] != patch:
            await raw(connection, f"rm -f {SERVICE}.kurumi-new")
            raise RuntimeError("hash da cache patchada nao confere; nada foi trocado")
        await run(connection, f"mv -f {SERVICE}.kurumi-new {SERVICE}")
        await run(connection, "sync")
        await run(connection, "systemctl daemon-reload")
        print(await run(
            connection,
            "systemctl show AT-HUB.service -p ExecStart -p ActiveState -p SubState",
        ))
        print("== Boot hook instalado. O teste real e o proximo reboot.")
        return 0
    finally:
        await root.release(connection, server, agent, package, assessment)


async def restore(tv: Tv, agent: Agent) -> int:
    connection, server, package, assessment = await root.acquire(
        agent, tv.host, tv.callback, 60
    )
    try:
        original = f"{STATE}/oneservice.original"
        exists = await raw(connection, f"test -e {original} && echo yes")
        if "yes" not in exists.stdout:
            raise RuntimeError(f"backup {original} nao existe")
        await run(connection, f"cp --preserve=all {original} {SERVICE}.kurumi-restore")
        await run(connection, f"mv -f {SERVICE}.kurumi-restore {SERVICE}")
        await run(connection, "sync")
        await run(connection, "systemctl daemon-reload")
        await raw(connection, f"rm -f {STATE}/enabled")
        await raw(connection, f"nsenter -t 1 -m -- umount {TARGET} 2>/dev/null || true")
        print(await run(
            connection,
            "systemctl show AT-HUB.service -p ExecStart -p ActiveState -p SubState",
        ))
        print("== Boot hook removido; screensaver original restaurado.")
        return 0
    finally:
        await root.release(connection, server, agent, package, assessment)


async def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    tv = Tv("192.168.1.50")
    tv.connect()
    agent = Agent(tv)
    print("== Abrindo shell persistente")
    agent.start()
    try:
        if action == "install":
            # Sanidade dos artefatos locais.
            for path in (OUT / "Boot.dll", OUT / "Boot.runtimeconfig.json",
                         OUT / "Boot.deps.json", BOOT / "ContentList.json",
                         HERE / "diagnostics" / "oneservice.patched"):
                if not path.is_file():
                    raise RuntimeError(f"artefato ausente: {path}")
            print("Boot.dll", hash_file(OUT / "Boot.dll"))
            print("ContentList", hash_file(BOOT / "ContentList.json"))
            print("oneservice.patched", hash_file(HERE / "diagnostics" / "oneservice.patched"))
            return await install(tv, agent)
        if action == "restore":
            return await restore(tv, agent)
        print("acao invalida", file=sys.stderr)
        return 2
    finally:
        agent.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(asyncio.run(main()))
