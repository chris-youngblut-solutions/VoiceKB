from __future__ import annotations

import os
import socket

_NOTIFY_ENV = "NOTIFY_SOCKET"


def _send(message: str) -> None:
    path = os.environ.get(_NOTIFY_ENV)
    if not path:
        return
    if path[0] == "@":
        path = "\0" + path[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.connect(path)
        sock.sendall(message.encode("utf-8"))


def ready() -> None:
    _send("READY=1\n")


def stopping() -> None:
    _send("STOPPING=1\n")


def status(msg: str) -> None:
    _send(f"STATUS={msg}\n")
