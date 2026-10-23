#!/usr/bin/env python3
"""Remove os apps opcionais escolhidos, com backup e verificacao.

Categorias aprovadas: TV Plus, Bixby/voz, jogos, SmartThings/IoT, Saude/Life+
e Arte/Ambient Mode. O script:

1. abre um shell sdk e confere, no banco de pacotes, as flags de cada alvo;
2. recusa qualquer pacote com dependencia vinda de um app que fica;
3. com --apply, obtem root, copia o banco de pacotes para o PC e remove um a um;
4. apos cada remocao, confere que o pacote sumiu e que o banco continua integro.

    py -3 tools/debloat.py plan
    py -3 tools/debloat.py apply --yes
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import Tv  # noqa: E402
from tv_agent import Agent  # noqa: E402
import root  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKUPS = ROOT / "tools" / "backups"
DB = "/opt/dbspace/.pkgmgr_parser.db"
DEFAULT_HOST = os.environ.get("KURUMI_TV", "192.168.1.50")

CATEGORIES = {
    "TV Plus": [
        "HEPsqFNie0",
        "com.samsung.tv.tvplus",
        "com.samsung.tv.slive-daemon",
        "com.samsung.tv.tvPlusDeeplinker",
    ],
    "Bixby/voz": [
        "com.samsung.tv.mybixby",
        "com.samsung.tv.bixby-prov",
        "com.samsung.tv.bixby-context-client",
        "com.samsung.tv.bixbycapsuleviewer",
        "com.samsung.tv.bixby-promotion",
        "com.samsung.tv.wakeup-engine-bixby",
        "com.samsung.tv.voice-instant-app",
        "com.samsung.tv.voiceassistant-music",
        "org.tizen.voice-app",
        "org.tizen.voice-client",
        "com.samsung.tv.ondevice-voice",
        "com.samsung.tv.farfieldvoice",
        "com.samsung.tv.voiceid-service",
        "com.samsung.tv.utterance-recommender-service",
        # context-aware-service fica: o AI Picture usa reconhecimento de contexto.
    ],
    "Jogos": [
        "com.samsung.tv.gaminghub",
        "com.samsung.tv.gamehome",
        "com.samsung.tv.gamepadguide",
        "com.samsung.tv.home.game",
        "com.samsung.tv.ghdaemon",
        "com.samsung.tv.ghservice",
    ],
    "SmartThings/IoT": [
        "com.samsung.tizen.smartthings-client",
        "com.samsung.tizen.smartthings-hub",
        "com.samsung.tizen.smartthings-plugin",
        "com.samsung.tizen.smartthings-streaming",
        "com.samsung.tizen.smartthings-thing",
        "com.samsung.tv.SmartThingsApp",
        "com.samsung.tv.iot-hub-control",
        "com.samsung.tv.iot-service-notification-v2",
        "com.samsung.tv.digitalbutler-app",
    ],
    "Saude/Life+": [
        "com.samsung.tv.health-mde-service",
        "com.samsung.tv.health-mde-setting",
        "com.samsung.tv.health-mde-workout-tracker",
        "com.samsung.tv.lifeplus",
        "com.samsung.tv.stpreview",
    ],
    "Arte/Ambient": [
        "org.tizen.art-app",
        "com.samsung.tv.home.art",
        "com.samsung.tv.coba.art",
        "com.samsung.tv.GenerativeWallpaper",
        # CinemaGraph/CinemaGraphApp e custom-picture-resource ficam: sao do
        # pipeline de imagem, nao do Ambient Mode.
        "com.samsung.tv.ambientinfo-resources",
        "com.samsung.tv.ambient-sound",
        "com.samsung.tv.adventure-tpl",
        "com.samsung.tv.bathtub-tpl",
        "com.samsung.tv.butterfly-tpl",
        "com.samsung.tv.floatingspheres-tpl",
        "com.samsung.tv.flowers-tpl",
        "com.samsung.tv.forest-tpl",
        "com.samsung.tv.gravity-tpl",
        "com.samsung.tv.infinityroom-tpl",
        "com.samsung.tv.islands-tpl",
        "com.samsung.tv.journey-tpl",
        "com.samsung.tv.lightcone-tpl",
        "com.samsung.tv.lightgrid-tpl",
        "com.samsung.tv.mountain-tpl",
        "com.samsung.tv.mountainview-tpl",
        "com.samsung.tv.onelinedrawing-tpl",
        "com.samsung.tv.rotatingtiles-tpl",
        "com.samsung.tv.sand-tpl",
        "com.samsung.tv.shelteringtree-tpl",
        "com.samsung.tv.skippingstone-tpl",
        "com.samsung.tv.skylight-tpl",
        "com.samsung.tv.spring-tpl",
        "com.samsung.tv.tranquilnature-tpl",
        "com.samsung.tv.water-tpl",
        "com.samsung.tv.window-tpl",
    ],
}

KEEP = [
    "KurumiTV01", "9Ur5IzDKqV", "OGLLvqej7u", "kIciSQlYEM", "LnLzvqrcEY",
    "com.samsung.tv.csfs", "org.tizen.tv-viewer", "com.samsung.tv.store",
    "com.samsung.tizen.samsung-account",
]


def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_list(packages: list[str]) -> str:
    return ",".join(quote(package) for package in packages)


def names(agent: Agent) -> dict[str, str]:
    output, code = agent.run("pkgcmd -l 2>&1")
    if code != 0:
        raise SystemExit("pkgcmd -l falhou")
    result = {}
    for line in output.splitlines():
        match = re.search(r"pkgid \[(.*?)\]\s+name \[(.*?)\]", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def check(agent: Agent, packages: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Devolve (problemas, presentes, ja_ausentes) consultando o banco da TV."""
    query = (
        "select package, package_removable, package_preload, package_readonly, "
        "package_system from package_info where package in (" + sql_list(packages) + ");"
    )
    output, code = agent.run(f'sqlite3 -readonly -separator "|" {DB} "{query}"')
    if code != 0:
        raise SystemExit(f"consulta de flags falhou: {output}")
    seen = {}
    for line in output.splitlines():
        fields = line.split("|")
        if len(fields) == 5:
            seen[fields[0]] = fields[1:]
    problems = []
    valid = []
    absent = []
    for package in packages:
        flags = seen.get(package)
        if flags is None:
            # Ja foi removido numa execucao anterior; nao e erro.
            absent.append(package)
        elif flags != ["true", "false", "false", "false"]:
            problems.append(f"{package}: flags {flags}")
        else:
            valid.append(package)

    incoming = (
        "select depends_on, package from package_dependency_info where depends_on in ("
        + sql_list(packages)
        + ") and package not in ("
        + sql_list(packages)
        + ");"
    )
    output, code = agent.run(f'sqlite3 -readonly -separator "|" {DB} "{incoming}"')
    if code != 0:
        raise SystemExit(f"consulta de dependencias falhou: {output}")
    for line in output.splitlines():
        if "|" in line:
            target, dependent = line.split("|", 1)
            problems.append(f"{target}: usado por {dependent} (fica na TV)")
    return problems, valid, absent


def print_plan(valid: list[str], labels: dict[str, str], absent: list[str]) -> None:
    by_category = {package: [] for package in valid}
    for category, packages in CATEGORIES.items():
        for package in packages:
            if package in by_category:
                by_category[package].append(category)
    print(f"== {len(valid)} pacotes para remover; {len(absent)} ja ausentes")
    for package in valid:
        label = labels.get(package, "")
        print(f"  {package:50} {label[:38]:38} {','.join(by_category[package])}")
    if absent:
        print("== Ja ausentes (serao ignorados):")
        for package in absent:
            print("  " + package)


async def apply(packages: list[str], host: str) -> int:
    tv = Tv(host)
    tv.connect()
    agent = Agent(tv)
    print("== Abrindo shell persistente")
    agent.start()
    try:
        labels = names(agent)
        problems, valid, absent = check(agent, packages)
        if problems:
            print("== ABORTADO: problemas encontrados")
            for problem in problems:
                print("  " + problem)
            return 2
        print_plan(valid, labels, absent)
        if not valid:
            print("== Nada a remover.")
            return 0

        print("== Obtendo root")
        connection, server, staging_package, assessment = await root.acquire(
            agent, tv.host, tv.callback, 60
        )
        staging = f"{root.STAGING_ROOT}/{staging_package}"
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = BACKUPS / stamp
        backup.mkdir(parents=True, exist_ok=True)
        try:
            for name, path in (
                ("pkgmgr_parser.db", DB),
                ("appsvc.db", "/opt/dbspace/user/5001/.appsvc.db"),
            ):
                await connection.execute(f"cp {path} {staging}/{name}", 30)
                data = await connection.read_file(f"{staging}/{name}")
                (backup / name).write_bytes(data.data)
                print(f"== Backup {name}: {len(data.data)} bytes")

            before = await connection.execute(
                f'sqlite3 -readonly -separator "|" {DB} "select package, package_removable, '
                f"package_preload, package_readonly, package_system from package_info "
                f'where package in ({sql_list(valid)});"',
                30,
            )
            (backup / "removidos-antes.txt").write_text(before.stdout, encoding="utf-8")
            total_before = await connection.execute(
                f'sqlite3 -readonly {DB} "select count(*) from package_info;"', 30
            )
            print(f"== Pacotes antes: {total_before.stdout.strip()}")

            failures = []
            for index, package in enumerate(valid, 1):
                label = labels.get(package, package)
                print(f"== [{index}/{len(valid)}] {package} ({label})")
                result = await connection.execute(
                    f"/usr/bin/pkgcmd -u -n {package}", 120
                )
                if result.exit_code != 0:
                    failures.append(f"{package}: pkgcmd exit {result.exit_code} {result.stderr.strip()}")
                    print(f"   FALHOU: {result.stderr.strip() or result.stdout.strip()}")
                    break
                verify = await connection.execute(
                    f'sqlite3 -readonly {DB} "select count(*) from package_info '
                    f"where package = {quote(package)};\"",
                    30,
                )
                if verify.stdout.strip() != "0":
                    failures.append(f"{package}: ainda aparece no banco")
                    print("   FALHOU: pacote ainda aparece no banco")
                    break

            integrity = await connection.execute(
                f'sqlite3 -readonly {DB} "pragma integrity_check;"', 30
            )
            print(f"== integrity_check: {integrity.stdout.strip()}")
            if integrity.stdout.strip() != "ok":
                failures.append("integrity_check nao retornou ok")

            after = await connection.execute(
                f'sqlite3 -readonly {DB} "select count(*) from package_info '
                f'where package in ({sql_list(valid)});"',
                30,
            )
            remaining_text = after.stdout.strip()
            remaining = int(remaining_text) if remaining_text.isdigit() else -1
            print(f"== Pacotes alvo que sobraram: {remaining}")
            if remaining not in (0,):
                failures.append(f"{remaining} pacotes alvo ainda presentes")

            kept = await connection.execute(
                f'sqlite3 -readonly {DB} "select package from package_info '
                f'where package in ({sql_list(KEEP)});"',
                30,
            )
            print("== Apps preservados:")
            print(kept.stdout.strip())
            missing_kept = [p for p in KEEP if p not in kept.stdout]
            if missing_kept:
                failures.append("sumiram apps que deviam ficar: " + ", ".join(missing_kept))

            (backup / "resultado.json").write_text(
                json.dumps(
                    {
                        "removidos": valid,
                        "falhas": failures,
                        "pacotes_antes": total_before.stdout.strip(),
                        "alvos_restantes": remaining,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            if failures:
                print("== FALHAS:")
                for failure in failures:
                    print("  " + failure)
                return 1
            print(f"== Concluido. Backup em {backup}")
            return 0
        finally:
            await root.release(connection, server, agent, staging_package, assessment)
    finally:
        agent.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tv", default=DEFAULT_HOST)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("plan", help="confere e lista os pacotes, sem remover")
    apply_parser = sub.add_parser("apply", help="obtem root e remove os pacotes")
    apply_parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    packages = []
    for category in CATEGORIES.values():
        for package in category:
            if package not in packages:
                packages.append(package)

    if args.action == "plan":
        tv = Tv(args.tv)
        tv.connect()
        agent = Agent(tv)
        print("== Abrindo shell persistente")
        agent.start()
        try:
            labels = names(agent)
            problems, valid, absent = check(agent, packages)
            if problems:
                print("== PROBLEMAS")
                for problem in problems:
                    print("  " + problem)
                return 2
            print_plan(valid, labels, absent)
            return 0
        finally:
            agent.close()

    if not args.yes:
        answer = input(f"Remover {len(packages)} pacotes? [s/N] ").strip().lower()
        if answer not in ("s", "sim", "y", "yes"):
            return 2
    return asyncio.run(apply(packages, args.tv))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
