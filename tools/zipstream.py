"""Read entries from a PARTIALLY downloaded zip by walking local file headers.

`zipfile` needs the central directory, which lives at the END of the archive — useless while a
740 MB dataset is still downloading. Every member is however preceded by its own local header, so
we can stream whatever has already landed. Truncated tail entry is skipped.
"""
import struct
import zlib

_LFH = b"PK\x03\x04"


def _zip64_csize(extra, usize_present):
    """Pull the compressed size out of the ZIP64 extended-information extra field (id 0x0001).

    Its payload is [uncompressed][compressed][...] but only the fields that were 0xFFFFFFFF in
    the local header are actually present, so the offset of `compressed` depends on that.
    """
    i = 0
    while i + 4 <= len(extra):
        hid, hlen = struct.unpack("<HH", extra[i:i + 4])
        body = extra[i + 4:i + 4 + hlen]
        if hid == 0x0001:
            off = 8 if usize_present else 0
            if len(body) >= off + 8:
                return struct.unpack("<Q", body[off:off + 8])[0]
            return None
        i += 4 + hlen
    return None


def iter_members(path, want=lambda n: n.endswith(".json")):
    """Yield (name, bytes) for every complete member present in the file so far."""
    with open(path, "rb") as f:
        while True:
            hdr = f.read(30)
            if len(hdr) < 30 or hdr[:4] != _LFH:
                return
            (_, _flags, method, _t, _d, _crc, csize, _usize,
             nlen, elen) = struct.unpack("<HHHHHIIIHH", hdr[4:30])
            name = f.read(nlen).decode("utf-8", "replace")
            extra = f.read(elen)
            if csize == 0xFFFFFFFF or _usize == 0xFFFFFFFF:
                csize = _zip64_csize(extra, _usize == 0xFFFFFFFF)
                if csize is None:
                    return
            if csize == 0 and (_flags & 0x08):
                return                      # streamed entry, size only in the trailing descriptor
            blob = f.read(csize)
            if len(blob) < csize:
                return                      # truncated: we've reached the download frontier
            if not want(name):
                continue
            try:
                yield name, (zlib.decompress(blob, -15) if method == 8 else blob)
            except Exception:
                continue
