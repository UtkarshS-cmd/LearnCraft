"""QR encoder tests (stdlib-only, offline).

The encoder was validated module-for-module against the reference ``segno``
implementation and every generated symbol was decoded back with ``zxing-cpp``
(the engine behind real phone scanners). Neither library is a LearnCraft
dependency, so this module keeps a dependency-free regression net instead: the
canonical Reed-Solomon vector from ISO/IEC 18004, the structural invariants of
the symbol, the format/version information bits, capacity limits, and a
decode-style read-back of the data region.
"""

import unittest

from app.core import qr


def _finders(matrix):
    size = len(matrix)
    for top, left in ((0, 0), (0, size - 7), (size - 7, 0)):
        for row in range(7):
            for col in range(7):
                outer = row in (0, 6) or col in (0, 6)
                core = 2 <= row <= 4 and 2 <= col <= 4
                if matrix[top + row][left + col] != (outer or core):
                    return False
    return True


def _read_data_bits(matrix, version, mask):
    """Recover the unmasked bit stream (inverse of the placement step)."""
    skeleton = qr._draw_function_patterns(version)
    size = len(skeleton)
    bits = []
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for current in (col, col - 1):
                if skeleton[row][current] is not None:
                    continue
                value = bool(matrix[row][current])
                if qr._mask_applies(mask, row, current):
                    value = not value
                bits.append(1 if value else 0)
        col -= 2
        upward = not upward
    return bits


def _best_mask(text, level="M"):
    """Repeat the encoder's own mask choice so tests know what it picked."""
    best = None
    for mask in range(8):
        score = qr._penalty(qr.encode_matrix(text, error=level, mask=mask))
        if best is None or score < best[0]:
            best = (score, mask)
    return best[1]


def _decode_payload(matrix, version, mask):
    bits = _read_data_bits(matrix, version, mask)
    bits = bits[:len(bits) - (len(bits) % 8)]
    codewords = [int("".join(str(b) for b in bits[i:i + 8]), 2)
                 for i in range(0, len(bits), 8)]
    stream = "".join(bin(c)[2:].zfill(8) for c in codewords)
    assert stream[:4] == "0100", "byte mode indicator"
    length = int(stream[4:12], 2)
    payload = bytes(int(stream[12 + i:20 + i], 2) for i in range(0, length * 8, 8))
    return payload.decode("utf-8")


class ReedSolomonTests(unittest.TestCase):
    def test_matches_iso_18004_worked_example(self):
        """Version 1-M for "01234567": data + ECC codewords from the spec."""
        data = [0x10, 0x20, 0x0C, 0x56, 0x61, 0x80, 0xEC, 0x11,
                0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11]
        expected = [0xA5, 0x24, 0xD4, 0xC1, 0xED, 0x36, 0xC7, 0x87, 0x2C, 0x55]
        self.assertEqual(qr._rs_ecc(data, 10), expected)

    def test_generator_polynomial_degree(self):
        for degree in (7, 10, 15, 26, 30):
            self.assertEqual(len(qr._rs_generator(degree)), degree + 1)


class StructureTests(unittest.TestCase):
    def test_size_follows_version(self):
        for version in range(1, qr.MAX_VERSION + 1):
            matrix = qr.encode_matrix("x" * (2 * version), version=version)
            self.assertEqual(len(matrix), 4 * version + 17)

    def test_finders_separators_and_timing(self):
        matrix = qr.encode_matrix("https://example.com/demo")
        size = len(matrix)
        self.assertTrue(_finders(matrix))
        for row in range(8):
            self.assertFalse(matrix[7][row])
            self.assertFalse(matrix[row][7])
        for index in range(8, size - 8):
            self.assertEqual(matrix[6][index], index % 2 == 0)
            self.assertEqual(matrix[index][6], index % 2 == 0)

    def test_dark_module_and_alignment_pattern(self):
        matrix = qr.encode_matrix("https://example.com/demo", version=2)
        size = len(matrix)
        self.assertIs(matrix[size - 8][8], True)
        for drow in range(-2, 3):  # version 2 alignment pattern at (18, 18)
            for dcol in range(-2, 3):
                expected = max(abs(drow), abs(dcol)) != 1
                self.assertEqual(matrix[18 + drow][18 + dcol], expected)

    def test_data_region_matches_the_codeword_count(self):
        for level in ("L", "M"):
            for version in (1, 3, 7):
                matrix = qr.encode_matrix("x" * 8, error=level, version=version, mask=0)
                bits = _read_data_bits(matrix, version, mask=0)
                data_codewords = qr._data_codewords(version, level)
                groups, ecc_len = qr._BLOCKS[(level, version)]
                total = data_codewords + sum(count for count, _size in groups) * ecc_len
                self.assertGreaterEqual(len(bits), total * 8)
                self.assertLess(len(bits), (total + 8) * 8)

    def test_read_back_recovers_the_payload(self):
        for text in ("Hi", "http://192.168.1.10:5000", "a" * 40):
            matrix = qr.encode_matrix(text, error="M")
            version = (len(matrix) - 17) // 4
            self.assertEqual(_decode_payload(matrix, version, _best_mask(text)), text)

    def test_padding_uses_the_spec_codewords(self):
        """ISO/IEC 18004 pad codewords are 0xEC / 0x11 and start with 0xEC."""
        codewords = qr._bit_stream("Hi", 1, qr._data_codewords(1, "M"))
        self.assertEqual(codewords[:4], [0x40, 0x24, 0x86, 0x90])
        self.assertEqual(codewords[4:8], [0xEC, 0x11, 0xEC, 0x11])
        self.assertEqual(len(codewords), 16)  # version 1-M capacity


class FormatAndVersionInfoTests(unittest.TestCase):
    def test_format_bits_placed_in_both_copies(self):
        for level in ("L", "M"):
            for mask in range(8):
                matrix = qr.encode_matrix("https://learncraft.local", error=level, mask=mask)
                size = len(matrix)
                bits = qr._format_info(level, mask)
                expect = lambda index: bool((bits >> index) & 1)  # noqa: E731

                for index in range(6):
                    self.assertEqual(matrix[index][8], expect(index))
                    self.assertEqual(matrix[8][size - 1 - index], expect(index))
                self.assertEqual(matrix[7][8], expect(6))
                self.assertEqual(matrix[8][8], expect(7))
                self.assertEqual(matrix[8][7], expect(8))
                for index in range(9, 15):
                    self.assertEqual(matrix[size - 15 + index][8], expect(index))
                    self.assertEqual(matrix[8][14 - index], expect(index))

    def test_automatic_mask_matches_lowest_penalty(self):
        text = "https://learncraft.local/student"
        matrix = qr.encode_matrix(text, error="M")
        bits = qr._format_info("M", _best_mask(text, "M"))
        for index in range(6):
            self.assertEqual(matrix[index][8], bool((bits >> index) & 1))

    def test_long_symbol_includes_version_information(self):
        long_text = "https://example.com/" + "a" * 120  # needs version >= 7
        matrix = qr.encode_matrix(long_text, error="M")
        size = len(matrix)
        version = (size - 17) // 4
        self.assertGreaterEqual(version, 7)
        bits = qr._version_info(version)
        for index in range(18):
            value = bool((bits >> index) & 1)
            row, col = index // 3, index % 3
            self.assertEqual(matrix[row][size - 11 + col], value)
            self.assertEqual(matrix[size - 11 + col][row], value)

    def test_short_symbol_has_no_version_information(self):
        self.assertEqual((len(qr.encode_matrix("Hi", error="M")) - 17) // 4, 1)


class CapacityTests(unittest.TestCase):
    def test_version_choice_at_capacity_boundary(self):
        # Version 1-M carries 16 data codewords = 14 payload bytes (byte mode).
        self.assertEqual(qr._choose_version("x" * 14, "M"), 1)
        self.assertEqual(qr._choose_version("x" * 15, "M"), 2)

    def test_too_long_text_raises(self):
        with self.assertRaises(ValueError):
            qr.encode_matrix("x" * 400, error="M")

    def test_unsupported_error_levels_are_rejected(self):
        for level in ("Q", "H", "Z", ""):
            with self.assertRaises(ValueError):
                qr.encode_matrix("Hi", error=level)

    def test_error_level_is_case_insensitive(self):
        self.assertEqual(qr.encode_matrix("Hi", error="m", mask=1),
                         qr.encode_matrix("Hi", error="M", mask=1))


class RenderingTests(unittest.TestCase):
    def test_matrix_is_deterministic(self):
        first = qr.encode_matrix("https://learncraft.local", error="M")
        self.assertEqual(first, qr.encode_matrix("https://learncraft.local", error="M"))
        self.assertNotEqual(first, qr.encode_matrix("https://learncraft.local/x", error="M"))

    def test_color_render_has_quiet_zone_and_modules(self):
        url = "https://random-fox-jumps-42.trycloudflare.com"
        lines = qr.render_ascii(url).splitlines()
        matrix = qr.encode_matrix(url, error="M")
        self.assertEqual(len(lines), len(matrix) + 8)  # border = 4 modules
        modules_per_line = lines[0].count("\x1b[40m") + lines[0].count("\x1b[47m")
        self.assertEqual(modules_per_line, len(matrix) + 8)
        self.assertNotIn("\x1b[40m", lines[0])  # quiet zone is light
        self.assertIn("\x1b[40m", lines[len(lines) // 2])

    def test_plain_render_uses_block_characters(self):
        rendered = qr.render_ascii("Hi", color=False, border=2)
        for line in rendered.splitlines():
            self.assertTrue(set(line) <= {"\u2588", " "}, repr(line))
        self.assertEqual(len(rendered.splitlines()),
                         len(qr.encode_matrix("Hi")) + 4)


if __name__ == "__main__":
    unittest.main()

