#!/usr/bin/env python3
"""Liga/desliga o auto-update de firmware da TV pelas chaves nativas.

As chaves foram tiradas do proprio binario /usr/bin/SWUAutoUpgrade:
  db/menu/support/softwareupdate/autoupdate
  db/menu/support/softwareupdate/preupdate_consent
  db/menu/support/softwareupdate/block_standby_scan

    py -3 tools/updates.py query
    py -3 tools/updates.py off --yes
    py -3 tools/updates.py on --yes

Isto nao impede um update manual nem um factory reset. O backup do banco de
pacotes e o stock.json do Home continuam em tools/.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import home  # noqa: E402
from tv import Tv  # noqa: E402

DEFAULT_HOST = "192.168.1.50"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tv", default=DEFAULT_HOST)
    parser.add_argument("--skip-build", action="store_true")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("query")
    off = sub.add_parser("off", help="desliga auto-update e scan em standby")
    off.add_argument("--yes", action="store_true")
    on = sub.add_parser("on", help="volta ao padrao de fabrica")
    on.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if args.action in ("off", "on") and not args.yes:
        answer = input("Alterar as chaves de atualizacao da TV? [s/N] ").strip().lower()
        if answer not in ("s", "sim", "y", "yes"):
            return 2

    if not args.skip_build:
        home.build()
    tv = Tv(args.tv)
    tv.connect()
    home.upload(tv)

    mode = {"query": "update-query", "off": "update-off", "on": "update-on"}[args.action]
    output, code = home.run_helper(tv, mode)
    print(output)
    if code != 0:
        print(f"[exit {code}]", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
