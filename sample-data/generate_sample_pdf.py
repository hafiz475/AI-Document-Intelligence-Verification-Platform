"""Generate a dependency-free synthetic PDF from the demo TXT report."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "sample-wind-turbine-inspection.txt"
DESTINATION = ROOT / "sample-wind-turbine-inspection.pdf"
NEWLINE = chr(10)
NEWLINE_BYTES = bytes([10])


def escape_pdf_text(value: str) -> str:
    slash = chr(92)
    return value.replace(slash, slash * 2).replace("(", slash + "(").replace(")", slash + ")")


def build_pdf(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 9 Tf", "45 760 Td", "12 TL"]
    for line in lines[:58]:
        commands.append(f"({escape_pdf_text(line[:105])}) Tj")
        commands.append("T*")
    commands.append("ET")
    stream = NEWLINE.join(commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>"
        + NEWLINE_BYTES
        + b"stream"
        + NEWLINE_BYTES
        + stream
        + NEWLINE_BYTES
        + b"endstream",
    ]
    output = bytearray(b"%PDF-1.4" + NEWLINE_BYTES)
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj{NEWLINE}".encode() + body + f"{NEWLINE}endobj{NEWLINE}".encode())
    xref = len(output)
    output.extend(f"xref{NEWLINE}0 {len(objects) + 1}{NEWLINE}0000000000 65535 f {NEWLINE}".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n {NEWLINE}".encode())
    output.extend(
        f"trailer{NEWLINE}<< /Size {len(objects) + 1} /Root 1 0 R >>{NEWLINE}startxref{NEWLINE}{xref}{NEWLINE}%%EOF".encode()
    )
    return bytes(output)


if __name__ == "__main__":
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    DESTINATION.write_bytes(build_pdf(lines))
    print(f"Generated {DESTINATION}")
