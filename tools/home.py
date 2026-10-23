#!/usr/bin/env python3
"""Aponta o botao Home da TV para o Kurumi Home (ou restaura o Home da Samsung).

O helper C# roda na propria TV como uid 901(sdk). Ele usa as APIs nativas que o
S90D usa para o botao Home e para o autostart do Smart Hub.

    py -3 tools/home.py query
    py -3 tools/home.py set --yes
    py -3 tools/home.py restore --yes

O primeiro `set` grava tools/home-route/stock.json com os valores originais da
TV. O `restore` usa esse arquivo; sem ele, nao mexe em nada.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import STAGING, Tv  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECT = ROOT / "tools" / "home-route"
OUTPUT = PROJECT / "out"
STOCK = PROJECT / "stock.json"
ASSEMBLY = "KurumiHomeControl"
STOCK_FIELDS = ("home_appid", "startup_appid", "booting_appid_backup", "auto_start")


def build() -> None:
    print("== Compilando o helper (net6.0, para o runtime da TV)")
    result = subprocess.run(
        [
            "dotnet", "build", str(PROJECT / f"{ASSEMBLY}.csproj"),
            "-c", "Release", "--nologo", "-v", "quiet", "-o", str(OUTPUT),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("dotnet build falhou")


def upload(tv: Tv) -> None:
    for name in (f"{ASSEMBLY}.dll", f"{ASSEMBLY}.runtimeconfig.json", f"{ASSEMBLY}.deps.json"):
        local = OUTPUT / name
        if not local.is_file():
            raise SystemExit(f"arquivo nao gerado: {local}")
        print(f"== Enviando {name}")
        tv.push(local, f"{STAGING}/{name}")


def run_helper(tv: Tv, arguments: str) -> tuple[str, int]:
    command = f"/usr/bin/dotnet {STAGING}/{ASSEMBLY}.dll {arguments}"
    print(f"== Executando na TV: {arguments}")
    return tv.run(command, timeout=45)


def parse_stock(output: str) -> dict[str, str]:
    stock: dict[str, str] = {}
    for line in output.splitlines():
        if line.startswith("stock."):
            key, _, value = line.partition("=")
            stock[key[len("stock."):]] = value.strip()
        elif line.startswith("home_atual="):
            stock["home_operation"] = line.split("=", 1)[1].strip()
    return stock


def confirm(question: str, yes: bool) -> None:
    if yes:
        return
    answer = input(question + " [s/N] ").strip().lower()
    if answer not in ("s", "sim", "y", "yes"):
        raise SystemExit("cancelado")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tv", default=None, help="IP da TV (padrao: variavel KURUMI_TV ou 192.168.1.50)")
    parser.add_argument("--skip-build", action="store_true", help="usa o helper ja compilado")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("query", help="mostra o Home atual e os valores originais salvos")
    set_parser = sub.add_parser("set", help="faz o Kurumi Home ser o Home e o app de boot")
    set_parser.add_argument("--yes", action="store_true")
    restore_parser = sub.add_parser("restore", help="volta o Home da Samsung e o boot original")
    restore_parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if not args.skip_build:
        build()
    if args.action == "set":
        confirm(
            "Isto troca o botao Home e o app que abre no boot para o Kurumi Home. Continuar?",
            args.yes,
        )
    if args.action == "restore":
        confirm("Isto devolve o botao Home e o boot para o Samsung Home. Continuar?", args.yes)

    tv = Tv(args.tv or _default_host())
    tv.connect()
    upload(tv)

    if args.action == "query":
        output, code = run_helper(tv, "query")
        print(output)
        if STOCK.is_file():
            print("== stock.json salvo")
            print(STOCK.read_text(encoding="utf-8").strip())
        return code

    if args.action == "set":
        output, code = run_helper(tv, "set")
        print(output)
        if code != 0:
            print(f"[exit {code}]", file=sys.stderr)
            return code
        stock = parse_stock(output)
        if not STOCK.is_file():
            STOCK.write_text(json.dumps(stock, indent=2) + "\n", encoding="utf-8")
            print(f"== Valores originais salvos em {STOCK}")
        else:
            print(f"== Mantendo o stock.json existente em {STOCK}")
        return 0

    if not STOCK.is_file():
        print(
            f"{STOCK} nao existe; nao sei quais valores restaurar. "
            "Rode `set` primeiro ou restaure pelo menu da TV.",
            file=sys.stderr,
        )
        return 2
    stock = json.loads(STOCK.read_text(encoding="utf-8"))
    missing = [field for field in STOCK_FIELDS if field not in stock]
    if missing or "home_operation" not in stock:
        print(f"stock.json incompleto: faltam {missing}", file=sys.stderr)
        return 2
    arguments = " ".join(
        shlex.quote(str(value))
        for value in (
            "restore",
            stock["home_appid"],
            stock["startup_appid"],
            stock["booting_appid_backup"],
            stock["auto_start"],
            stock["home_operation"],
        )
    )
    output, code = run_helper(tv, arguments)
    print(output)
    if code != 0:
        print(f"[exit {code}]", file=sys.stderr)
    return code


def _default_host() -> str:
    import os
    return os.environ.get("KURUMI_TV", "192.168.1.50")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
