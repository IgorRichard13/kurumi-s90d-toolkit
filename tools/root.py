#!/usr/bin/env python3
"""Root temporario na TV pelo caminho archive-launcher, sem depender do sdbd.

O sdbd desta TV fica preso por minutos depois de cada `appinstall`. Entao o
root e lancado por um shell sdk persistente (tools/tv_agent.py): uma unica
injecao abre o shell, e todo o resto (preflight, upload, lancamento) passa por
ele.

O payload e o mesmo do samsung-tv-root: um namespace de mount privado troca
/etc/passwd e /usr/share/sdbd/public.pem, e o sdbd-tarlauncher executa um
launch.sh como root. O agente autentica de volta no PC e aceita comandos.

    py -3 tools/root.py preflight
    py -3 tools/root.py probe
    py -3 tools/root.py exec "id"
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import pathlib
import re
import secrets
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import Tv  # noqa: E402
from tv_agent import Agent  # noqa: E402

ROOT_TOOL = pathlib.Path(
    os.environ.get(
        "SAMSUNG_TV_ROOT_SOURCE",
        pathlib.Path(os.environ.get("LOCALAPPDATA", ""))
        / "kurumi-tv-tools" / "samsung-tv-root"
        / "samsung-tv-root-0.0.11-windows-x86_64" / "source" / "src",
    )
)
sys.path.insert(0, str(ROOT_TOOL))

from samsung_tv_root.archive_root import (  # noqa: E402
    PAYLOAD_FILES,
    RUNTIME_CONFIG_FILES,
    STAGING_ROOT,
    SYSTEM_HASH_COMMAND,
    _file_capabilities,
    _prepare_artifacts,
)
from samsung_tv_root.root_agent import (  # noqa: E402
    RootAgentIdentity,
    RootAgentServer,
    generate_secret,
)

PAYLOADS = pathlib.Path(
    os.environ.get(
        "SAMSUNG_TV_ROOT_PAYLOADS",
        pathlib.Path(os.environ.get("LOCALAPPDATA", ""))
        / "kurumi-tv-tools" / "samsung-tv-root"
        / "samsung-tv-root-0.0.11-windows-x86_64" / "_internal" / "payloads" / "common",
    )
)
ON_DEMAND = f"{STAGING_ROOT}/on-demand"


class RootError(RuntimeError):
    pass


def require(agent: Agent, command: str, timeout: float = 30) -> str:
    output, code = agent.run(command, timeout)
    if code != 0:
        raise RootError(f"comando falhou ({code}): {command}\n{output}")
    return output


def preflight(agent: Agent) -> dict[str, str]:
    capabilities = require(agent, "getcap /usr/bin/dotnet /usr/sbin/sdbd-tarlauncher")
    lines = capabilities.splitlines()
    dotnet = next((line for line in lines if "/usr/bin/dotnet" in line), "")
    launcher = next((line for line in lines if "/usr/sbin/sdbd-tarlauncher" in line), "")
    dotnet_caps = _file_capabilities(dotnet)
    launcher_caps = _file_capabilities(launcher)
    for name in ("cap_setgid", "cap_sys_admin"):
        if "e" not in dotnet_caps.get(name, ""):
            raise RootError(f"/usr/bin/dotnet sem {name} efetiva")
    for name in ("cap_setuid", "cap_setgid"):
        if "e" not in launcher_caps.get(name, ""):
            raise RootError(f"sdbd-tarlauncher sem {name} efetiva")

    runtimes, runtime_code = agent.run("/usr/bin/dotnet --list-runtimes")
    versions = [
        (int(match.group(1)), int(match.group(2)))
        for line in runtimes.splitlines()
        if (match := re.match(r"Microsoft\.NETCore\.App (\d+)\.(\d+)\.\d+\s+\[", line))
    ]
    if runtime_code != 0 and "Unknown option --list-runtimes" in runtimes:
        # Apphost nao padrao da Samsung (Tizen): o runtime ativo e um symlink.
        active = require(agent, "readlink -f /usr/share/dotnet.tizen/netcoreapp")
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", pathlib.PurePosixPath(active).name)
        if match is None:
            raise RootError(f"caminho de runtime inesperado: {active}")
        require(
            agent,
            "test -r /usr/share/dotnet.tizen/netcoreapp/libcoreclr.so && "
            "test -r /usr/share/dotnet.tizen/netcoreapp/System.Private.CoreLib.dll",
        )
        versions = [(int(match.group(1)), int(match.group(2)))]
        runtimes = active
    if not any(major >= 6 for major, _ in versions):
        raise RootError(f"runtime .NET 6+ nao encontrado: {runtimes.strip()}")
    tar_help = require(agent, "/usr/bin/tar --help | grep -- --to-command")
    if "--to-command" not in tar_help:
        raise RootError("tar da TV nao suporta --to-command")
    return {
        "capabilities": capabilities,
        "runtime": "6.0",
        "hashes": require(agent, SYSTEM_HASH_COMMAND),
    }


def upload_artifacts(agent: Agent, directory: pathlib.Path, package: str) -> None:
    staging = f"{STAGING_ROOT}/{package}"
    require(agent, f"/bin/mkdir -p {staging} {ON_DEMAND}")
    for name in PAYLOAD_FILES:
        agent.push(PAYLOADS / name, f"{staging}/{name}")
    for name in RUNTIME_CONFIG_FILES:
        agent.push(directory / name, f"{staging}/{name}")
    for name in ("public.pem", "passwd", "root-agent.token"):
        agent.push(directory / name, f"{staging}/{name}")
    archive_name = f"{package}.tar.gz"
    agent.push(directory / archive_name, f"{ON_DEMAND}/{archive_name}")
    agent.push(
        directory / f"{archive_name}.signature",
        f"{ON_DEMAND}/{archive_name}.signature",
    )


def cleanup(agent: Agent, package: str) -> bool:
    staging = f"{STAGING_ROOT}/{package}"
    archive = f"{ON_DEMAND}/{package}.tar.gz"
    try:
        agent.run(f"/bin/rm -rf {staging} {archive} {archive}.signature", timeout=60)
        check = agent.run(
            f"test ! -e {staging} && test ! -e {archive} && echo ausente"
        )[0].strip()
        return check == "ausente"
    except Exception:
        return False


async def acquire(agent: Agent, tv_host: str, callback: str, timeout: float = 60) -> tuple:
    assessment = preflight(agent)
    package = "archive-root-" + secrets.token_hex(8)
    secret = generate_secret()
    with tempfile.TemporaryDirectory(prefix="kurumi-root-") as folder:
        directory = pathlib.Path(folder)
        server = RootAgentServer(callback, 0, tv_host, secret, require_root=True)
        await server.start()
        port = server.listening_port
        _prepare_artifacts(directory, assessment["runtime"], package, callback, port, secret)
        upload_artifacts(agent, directory, package)
        launcher = f"{STAGING_ROOT}/{package}/SamsungTvArchiveRoot.dll"
        command = (
            f"setsid /usr/bin/dotnet {launcher} {package} "
            f">{STAGING_ROOT}/{package}/launch.out 2>&1 "
            f"< /dev/null &"
        )
        print(f"== Lançando archive-root {package}")
        asyncio.get_running_loop().run_in_executor(None, agent.run, command)
        try:
            connection = await server.accept(timeout)
        except Exception as error:
            log = agent.run(f"/bin/cat {STAGING_ROOT}/{package}/launch.out 2>&1")[0]
            await server.close()
            cleanup(agent, package)
            raise RootError(f"root nao conectou: {error}\nlog: {log}") from error
        identity = await connection.ping()
        if any(value != 0 for value in (identity.uid, identity.euid, identity.gid, identity.egid)):
            await connection.close()
            await server.close()
            cleanup(agent, package)
            raise RootError(
                f"agente conectou sem root: uid={identity.uid} euid={identity.euid} "
                f"gid={identity.gid} egid={identity.egid}"
            )
        return connection, server, package, assessment


async def release(connection, server, agent: Agent, package: str, assessment: dict) -> None:
    try:
        await connection.shutdown()
    except Exception:
        await connection.close()
    await server.close()
    final_hashes = agent.run(SYSTEM_HASH_COMMAND)[0].strip()
    cleaned = cleanup(agent, package)
    print("== /etc/passwd e chave publica inalterados:", final_hashes == assessment["hashes"])
    print("== Staging removido:", cleaned)
    if final_hashes != assessment["hashes"] or not cleaned:
        raise RootError("verificacao final falhou; inspecione a TV")


async def main_async(args) -> int:
    tv = Tv(args.tv)
    tv.connect()
    agent = Agent(tv)
    print("== Abrindo shell persistente (uma injecao)")
    agent.start()
    try:
        if args.action == "preflight":
            assessment = preflight(agent)
            print(assessment["capabilities"])
            print(assessment["hashes"])
            return 0

        connection, server, package, assessment = await acquire(
            agent, tv.host, tv.callback, args.accept_timeout
        )
        print("== Root autenticado")
        print(
            f"uid={connection.identity.uid} euid={connection.identity.euid} "
            f"gid={connection.identity.gid} egid={connection.identity.egid} "
            f"smack={connection.identity.smack_label.strip()}"
        )
        try:
            for command in args.command or ["id"]:
                result = await connection.execute(command, args.command_timeout)
                print(f"$ {command}")
                if result.stdout:
                    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
                if result.stderr:
                    print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
                if result.exit_code:
                    print(f"[exit {result.exit_code}]")
        finally:
            await release(connection, server, agent, package, assessment)
        return 0
    finally:
        agent.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tv", default=os.environ.get("KURUMI_TV", "192.168.1.50"))
    parser.add_argument("--accept-timeout", type=float, default=60)
    parser.add_argument("--command-timeout", type=float, default=120)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("preflight", help="confere os pre-requisitos sem explorar")
    probe = sub.add_parser("probe", help="obtem root e mostra id")
    execute = sub.add_parser("exec", help="obtem root e roda um comando")
    execute.add_argument("command")
    args = parser.parse_args()
    args.command = [args.command] if args.action == "exec" else ["id"]
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
