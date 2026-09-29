"""Общие фикстуры: синтетические текстуры *.pkm.ccz вместо файлов игры."""
import struct
import zlib

import pytest


def ccz_pkm(width: int, height: int, orig_width: int, orig_height: int,
            payload: bytes | None = None, fmt: int = 0) -> bytes:
    """CCZ(zlib) с PKM 1.0 внутри. Данные ETC1 — нули нужной длины: их всё равно читает фейковый
    декодер из тестов."""
    if payload is None:
        payload = bytes(((width + 3) // 4) * ((height + 3) // 4) * 8)
    pkm = b"PKM 10" + struct.pack(">HHHHH", fmt, width, height, orig_width, orig_height) + payload
    return b"CCZ!" + struct.pack(">HHII", 0, 2, 0, len(pkm)) + zlib.compress(pkm)


@pytest.fixture
def make_ccz():
    return ccz_pkm
