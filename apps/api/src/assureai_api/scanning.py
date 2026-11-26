"""Malware scanning boundary with an explicit development-disabled adapter."""

import socket
import struct
from typing import Protocol

from assureai_api.config import Settings


class ScanRejectedError(ValueError):
    pass


class DocumentScanner(Protocol):
    provider: str

    def scan(self, content: bytes) -> None: ...


class DisabledDocumentScanner:
    provider = "disabled"

    def scan(self, content: bytes) -> None:
        del content


class ClamAVDocumentScanner:
    provider = "clamav"

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def scan(self, content: bytes) -> None:
        try:
            with socket.create_connection((self.host, self.port), timeout=10) as connection:
                connection.sendall(b"zINSTREAM\0")
                for offset in range(0, len(content), 64 * 1024):
                    chunk = content[offset : offset + 64 * 1024]
                    connection.sendall(struct.pack("!I", len(chunk)) + chunk)
                connection.sendall(struct.pack("!I", 0))
                response = connection.recv(4096).decode("utf-8", errors="replace")
        except OSError as exc:
            raise ScanRejectedError("Document scanning is temporarily unavailable.") from exc
        if not response.endswith("OK\0") and not response.endswith("OK"):
            raise ScanRejectedError("Document was rejected by malware scanning.")


def create_document_scanner(settings: Settings) -> DocumentScanner:
    if settings.malware_scanner == "clamav":
        return ClamAVDocumentScanner(settings.clamav_host, settings.clamav_port)
    return DisabledDocumentScanner()
