"""Tiny stdlib-only QR encoder used to print a scannable link in the terminal.

Why hand-rolled: LearnCraft is offline-first and ships zero third-party
dependencies beyond Flask/pydantic. Sharing a link to a phone must therefore
work without ``pip install qrcode``; this module implements just enough of
ISO/IEC 18004 (byte mode, versions 1-10, EC levels L/M) to encode a URL.

Scope (deliberately small, everything else raises ValueError):
  * mode          : 8-bit byte mode only (URLs/UTF-8 text)
  * versions      : 1..10   (up to ~271 bytes at level M)
  * EC levels     : L and M
  * automatic mask: all 8 masks scored with the standard penalty rules
  * version info  : emitted for versions >= 7 (needed by the spec)

The generated matrix is byte-for-byte identical to reference encoders
(verified against ``segno`` for all masks/levels supported here).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# GF(256) arithmetic for Reed-Solomon error correction (poly 0x11D)
# ---------------------------------------------------------------------------
_GF_EXP: list[int] = [0] * 512
_GF_LOG: list[int] = [0] * 256


def _init_gf() -> None:
    value = 1
    for power in range(255):
        _GF_EXP[power] = value
        _GF_LOG[value] = power
        value <<= 1
        if value & 0x100:
            value ^= 0x11D
    for power in range(255, 512):
        _GF_EXP[power] = _GF_EXP[power - 255]


_init_gf()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_generator(degree: int) -> list[int]:
    """Coefficients of (x - a^0)(x - a^1)...(x - a^(degree-1))."""
    poly = [1]
    for power in range(degree):
        poly.append(0)
        factor = _GF_EXP[power]
        for index in range(len(poly) - 1, 0, -1):
            poly[index] ^= _gf_mul(poly[index - 1], factor)
    return poly


def _rs_ecc(data: list[int], degree: int) -> list[int]:
    """Reed-Solomon remainder (error-correction codewords) for one block."""
    generator = _rs_generator(degree)
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder[0]
        remainder = remainder[1:] + [0]
        if factor:
            log_factor = _GF_LOG[factor]
            for index, coefficient in enumerate(generator[1:]):
                if coefficient:
                    remainder[index] ^= _GF_EXP[log_factor + _GF_LOG[coefficient]]
    return remainder


# ---------------------------------------------------------------------------
# Version tables (ISO/IEC 18004). Values: ((blocks, data-codewords)*, ecc)
# ---------------------------------------------------------------------------
_BLOCKS: dict[tuple[str, int], tuple[tuple[tuple[int, int], ...], int]] = {
    ("L", 1): (((1, 19),), 7),
    ("L", 2): (((1, 34),), 10),
    ("L", 3): (((1, 55),), 15),
    ("L", 4): (((1, 80),), 20),
    ("L", 5): (((1, 108),), 26),
    ("L", 6): (((2, 68),), 18),
    ("L", 7): (((2, 78),), 20),
    ("L", 8): (((2, 97),), 24),
    ("L", 9): (((2, 116),), 30),
    ("L", 10): (((2, 68), (2, 69)), 18),
    ("M", 1): (((1, 16),), 10),
    ("M", 2): (((1, 28),), 16),
    ("M", 3): (((1, 44),), 26),
    ("M", 4): (((2, 32),), 18),
    ("M", 5): (((2, 43),), 24),
    ("M", 6): (((4, 27),), 16),
    ("M", 7): (((4, 31),), 18),
    ("M", 8): (((2, 38), (2, 39)), 22),
    ("M", 9): (((3, 36), (2, 37)), 22),
    ("M", 10): (((4, 43), (1, 44)), 26),
}

# ECC indicator bits (L=01, M=00) and alignment-pattern centres per version.
_EC_INDICATOR = {"L": 0b01, "M": 0b00}
_ALIGN: dict[int, list[int]] = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 50],
}
MAX_VERSION = 10


def _data_codewords(version: int, level: str) -> int:
    groups, _ecc = _BLOCKS[(level, version)]
    return sum(count * size for count, size in groups)


def _bch(value: int, poly: int) -> int:
    """Remainder of ``value`` modulo ``poly`` inside GF(2)."""
    poly_bits = poly.bit_length()
    while value.bit_length() >= poly_bits:
        value ^= poly << (value.bit_length() - poly_bits)
    return value


# ---------------------------------------------------------------------------
# Matrix construction
# ---------------------------------------------------------------------------
def _new_matrix(version: int) -> list[list[bool | None]]:
    size = 4 * version + 17
    return [[None] * size for _ in range(size)]


def _draw_finder(matrix: list[list[bool | None]], top: int, left: int) -> None:
    for row in range(top, top + 7):
        for col in range(left, left + 7):
            outer = row in (top, top + 6) or col in (left, left + 6)
            core = 2 <= row - top <= 4 and 2 <= col - left <= 4
            matrix[row][col] = outer or core
    # Separator (light ring) where it fits inside the symbol.
    size = len(matrix)
    for row in range(top - 1, top + 8):
        for col in range(left - 1, left + 8):
            if 0 <= row < size and 0 <= col < size and matrix[row][col] is None:
                matrix[row][col] = False


def _draw_function_patterns(version: int) -> list[list[bool | None]]:
    matrix = _new_matrix(version)
    size = len(matrix)

    _draw_finder(matrix, 0, 0)
    _draw_finder(matrix, 0, size - 7)
    _draw_finder(matrix, size - 7, 0)

    # Timing patterns (row 6 / column 6).
    for index in range(8, size - 8):
        matrix[6][index] = index % 2 == 0
        matrix[index][6] = index % 2 == 0

    # Alignment patterns (skipped where they would collide with a finder).
    centres = _ALIGN[version]
    for row_centre in centres:
        for col_centre in centres:
            corner = (row_centre <= 8 and col_centre <= 8) or \
                (row_centre <= 8 and col_centre >= size - 9) or \
                (row_centre >= size - 9 and col_centre <= 8)
            if corner:
                continue
            for drow in range(-2, 3):
                for dcol in range(-2, 3):
                    distance = max(abs(drow), abs(dcol))
                    matrix[row_centre + drow][col_centre + dcol] = distance != 1

    # Dark module (always dark, just below the top-left format area).
    matrix[size - 8][8] = True

    # Reserve format-information cells (values written once the mask is known).
    for index in range(9):
        if matrix[8][index] is None:
            matrix[8][index] = False
        if matrix[index][8] is None:
            matrix[index][8] = False
    for index in range(8):
        matrix[8][size - 1 - index] = False
    # Bottom-left copy: rows size-7..size-1 only — (size-8, 8) is the fixed
    # dark module and must keep its value.
    for row in range(size - 7, size):
        matrix[row][8] = False

    # Reserve version-information cells (versions >= 7).
    if version >= 7:
        for row in range(6):
            for col in range(size - 11, size - 8):
                matrix[row][col] = False
                matrix[col][row] = False
    return matrix


def _format_info(level: str, mask: int) -> int:
    data = (_EC_INDICATOR[level] << 3) | mask
    return ((data << 10) | _bch(data << 10, 0x537)) ^ 0x5412


def _version_info(version: int) -> int:
    return (version << 12) | _bch(version << 12, 0x1F25)


def _place_format_info(matrix: list[list[bool | None]], level: str, mask: int) -> None:
    """Write both copies of the 15-bit format information (bit 0 = LSB)."""
    size = len(matrix)
    bits = _format_info(level, mask)

    def bit(index: int) -> bool:
        return bool((bits >> index) & 1)

    # Vertical copy: (0..5, 8), (7, 8), (8, 8), then (size-7..size-1, 8).
    for index in range(15):
        if index < 6:
            matrix[index][8] = bit(index)
        elif index < 8:
            matrix[index + 1][8] = bit(index)
        else:
            matrix[size - 15 + index][8] = bit(index)

    # Horizontal copy: (8, size-1) downwards, skipping the timing column 6.
    for index in range(15):
        if index < 8:
            matrix[8][size - index - 1] = bit(index)
        elif index == 8:
            matrix[8][7] = bit(index)
        else:
            matrix[8][14 - index] = bit(index)


def _place_version_info(matrix: list[list[bool | None]], version: int) -> None:
    if version < 7:
        return
    size = len(matrix)
    bits = _version_info(version)
    for index in range(18):
        value = bool((bits >> index) & 1)
        row, col = index // 3, index % 3
        matrix[row][size - 11 + col] = value
        matrix[size - 11 + col][row] = value


def _mask_applies(mask: int, row: int, col: int) -> bool:
    if mask == 0:
        return (row + col) % 2 == 0
    if mask == 1:
        return row % 2 == 0
    if mask == 2:
        return col % 3 == 0
    if mask == 3:
        return (row + col) % 3 == 0
    if mask == 4:
        return (row // 2 + col // 3) % 2 == 0
    if mask == 5:
        return (row * col) % 2 + (row * col) % 3 == 0
    if mask == 6:
        return ((row * col) % 2 + (row * col) % 3) % 2 == 0
    return ((row + col) % 2 + (row * col) % 3) % 2 == 0


def _place_codewords(matrix: list[list[bool | None]], codewords: list[int], mask: int) -> None:
    size = len(matrix)
    bits = [(byte >> shift) & 1 for byte in codewords for shift in range(7, -1, -1)]
    index = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:  # vertical timing pattern is never part of the data region
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for current in (col, col - 1):
                if matrix[row][current] is not None:
                    continue
                value = bool(bits[index]) if index < len(bits) else False
                index += 1
                matrix[row][current] = value != _mask_applies(mask, row, current)
        col -= 2
        upward = not upward


# ---------------------------------------------------------------------------
# Mask selection (ISO/IEC 18004 penalty rules 1-4)
# ---------------------------------------------------------------------------
_FINDER_LIKE = ((1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0), (0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1))


def _matches_at(pattern: tuple[int, ...], line: list[bool], start: int) -> bool:
    return all(
        (1 if line[start + offset] else 0) == expected
        for offset, expected in enumerate(pattern)
    )


def _penalty(matrix: list[list[bool]]) -> int:
    size = len(matrix)
    score = 0

    lines = [list(row) for row in matrix]
    lines += [[matrix[row][col] for row in range(size)] for col in range(size)]

    # Rule 1: runs of five or more identical modules.
    for line in lines:
        run_colour = line[0]
        run_length = 1
        for value in line[1:]:
            if value == run_colour:
                run_length += 1
            else:
                if run_length >= 5:
                    score += 3 + (run_length - 5)
                run_colour, run_length = value, 1
        if run_length >= 5:
            score += 3 + (run_length - 5)

    # Rule 2: every 2x2 block of one colour.
    for row in range(size - 1):
        for col in range(size - 1):
            first = matrix[row][col]
            if first == matrix[row][col + 1] == matrix[row + 1][col] == matrix[row + 1][col + 1]:
                score += 3

    # Rule 3: finder-like 1:1:3:1:1 patterns with a 4-module light area.
    for line in lines:
        for start in range(size - 10):
            for pattern in _FINDER_LIKE:
                if _matches_at(pattern, line, start):
                    score += 40

    # Rule 4: deviation of the dark-module ratio from 50% in 5% steps.
    dark = sum(1 for row in matrix for value in row if value)
    percent = dark * 100 / (size * size)
    score += (int(abs(percent - 50) // 5)) * 10
    return score


# ---------------------------------------------------------------------------
# Data encoding
# ---------------------------------------------------------------------------
def _bit_stream(text: str, version: int, capacity: int) -> list[int]:
    payload = text.encode("utf-8")
    length_bits = 8 if version <= 9 else 16
    bits = [0, 1, 0, 0]  # byte mode
    bits += [(len(payload) >> shift) & 1 for shift in range(length_bits - 1, -1, -1)]
    for byte in payload:
        bits += [(byte >> shift) & 1 for shift in range(7, -1, -1)]
    if len(bits) > capacity * 8:
        raise ValueError("data does not fit the selected version")
    bits += [0] * min(4, capacity * 8 - len(bits))  # terminator
    bits += [0] * ((8 - len(bits) % 8) % 8)  # pad to a codeword boundary
    codewords = [
        int("".join(str(bit) for bit in bits[index:index + 8]), 2)
        for index in range(0, len(bits), 8)
    ]
    pad = (0xEC, 0x11)
    toggle = 0
    while len(codewords) < capacity:
        codewords.append(pad[toggle])
        toggle ^= 1
    return codewords


def _interleave(data: list[int], version: int, level: str) -> list[int]:
    groups, ecc_len = _BLOCKS[(level, version)]
    blocks: list[list[int]] = []
    cursor = 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(data[cursor:cursor + size])
            cursor += size
    ecc_blocks = [_rs_ecc(block, ecc_len) for block in blocks]

    out: list[int] = []
    for index in range(max(len(block) for block in blocks)):
        for block in blocks:
            if index < len(block):
                out.append(block[index])
    for index in range(ecc_len):
        for block in ecc_blocks:
            out.append(block[index])
    return out


def _choose_version(text: str, level: str) -> int:
    length = len(text.encode("utf-8"))
    for version in range(1, MAX_VERSION + 1):
        overhead = 4 + (8 if version <= 9 else 16)
        capacity = _data_codewords(version, level)
        if length <= (capacity * 8 - overhead) // 8:
            return version
    raise ValueError(
        f"text is too long for QR versions 1-{MAX_VERSION} (level {level}): "
        f"{length} bytes"
    )


def encode_matrix(
    text: str,
    *,
    error: str = "M",
    version: int | None = None,
    mask: int | None = None,
) -> list[list[bool]]:
    """Return the QR module matrix (True = dark) for ``text``.

    ``error`` accepts "L" or "M"; ``version``/``mask`` are auto-selected when
    omitted (version by capacity, mask by the standard penalty rules).
    """
    level = error.strip().upper()
    if level not in _EC_INDICATOR:
        raise ValueError('error level must be "L" or "M"')
    if version is None:
        version = _choose_version(text, level)
    elif not 1 <= version <= MAX_VERSION:
        raise ValueError(f"version must be 1..{MAX_VERSION}")

    codewords = _interleave(
        _bit_stream(text, version, _data_codewords(version, level)), version, level
    )

    candidates = [mask] if mask is not None else list(range(8))
    best: tuple[int, list[list[bool]]] | None = None
    for candidate in candidates:
        if not 0 <= candidate <= 7:
            raise ValueError("mask must be 0..7")
        matrix = _draw_function_patterns(version)
        _place_codewords(matrix, codewords, candidate)
        _place_format_info(matrix, level, candidate)
        _place_version_info(matrix, version)
        final = [[bool(value) for value in row] for row in matrix]
        score = _penalty(final)
        if best is None or score < best[0]:
            best = (score, final)
    return best[1]


def render_ascii(
    text: str,
    *,
    error: str = "M",
    border: int = 4,
    color: bool = True,
    version: int | None = None,
) -> str:
    """Render ``text`` as a scannable QR code for the console.

    ``color=True`` prints real black/white module backgrounds (ANSI), so the
    code scans regardless of the terminal theme. ``color=False`` falls back to
    block characters, which needs an inverted-code tolerant scanner on dark
    themes.
    """
    matrix = encode_matrix(text, error=error, version=version)
    dark = "\x1b[40m  \x1b[0m" if color else "\u2588\u2588"
    light = "\x1b[47m  \x1b[0m" if color else "  "
    size = len(matrix)
    span = size + 2 * border
    pattern = [[False] * span for _ in range(span)]
    for row in range(size):
        for col in range(size):
            pattern[row + border][col + border] = matrix[row][col]
    lines = ["".join(dark if value else light for value in row) for row in pattern]
    if color:
        # Reset after every line: full-width background colours can otherwise
        # bleed past the right edge of the terminal window.
        lines = [line + "\x1b[0m" for line in lines]
    return "\n".join(lines)


__all__ = ["MAX_VERSION", "encode_matrix", "render_ascii"]


