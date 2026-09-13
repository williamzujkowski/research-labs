"""Original, deterministic ZIP fixtures. Stored ASCII text; no dangerous paths."""
import hashlib
import struct
import zlib

MARKER = b"REVIEW-ME\n"


def archive(entries, central_order=None):
    """entries: (local name, central name, bytes); order may omit local records."""
    local = bytearray()
    central = []
    for local_name, central_name, data in entries:
        name, cname = local_name.encode("ascii"), central_name.encode("ascii")
        crc, size, offset = zlib.crc32(data), len(data), len(local)
        local.extend(struct.pack("<I5H3I2H", 0x04034B50, 20, 0, 0, 0, 33,
                                 crc, size, size, len(name), 0) + name + data)
        central.append(struct.pack("<I6H3I5H2I", 0x02014B50, 20, 20, 0, 0, 0,
                                   33, crc, size, size, len(cname), 0, 0, 0,
                                   0, 0, offset) + cname)
    order = list(range(len(entries))) if central_order is None else central_order
    directory = b"".join(central[i] for i in order)
    return bytes(local) + directory + struct.pack(
        "<I4H2IH", 0x06054B50, 0, 0, len(order), len(order), len(directory), len(local), 0)


def fixtures():
    safe = ("note.txt", "note.txt", b"ordinary text\n")
    marked = ("note.txt", "note.txt", MARKER)
    return {
        "control": archive([safe]),
        "duplicate-marker-first": archive([marked, safe]),
        "duplicate-marker-last": archive([safe, marked]),
        "central-order-reversed": archive([
            ("first.txt", "first.txt", b"first\n"),
            ("second.txt", "second.txt", MARKER)], [1, 0]),
        "local-central-name-conflict": archive([("local.txt", "index.txt", MARKER)]),
        "local-entry-absent-from-index": archive([
            safe, ("extra.txt", "extra.txt", MARKER)], [0]),
    }


def inventory():
    return {name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in fixtures().items()}
