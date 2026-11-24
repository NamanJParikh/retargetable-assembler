"""Snapshot-test the parsed SimpleASM program and exercise parser rejections."""
from pathlib import Path
import subprocess
import tempfile
import unittest


FIXTURE_DIR = Path(__file__).resolve().parent / "parser"
COMPILER = Path(__file__).resolve().parents[1] / "compile"
SOURCES = sorted(FIXTURE_DIR.glob("*.sasm"))

INVALID_SOURCES = {
    "content_before_section": (
        "LI R0, d1\n",
        "Expected .DATA or .CODE before:",
    ),
    "data_entry_without_value": (
        ".DATA\nVALUE\n",
        "Malformed .DATA entry:",
    ),
    "invalid_immediate_prefix": (
        ".DATA\nVALUE q1\n",
        "Invalid immediate prefix:",
    ),
    "invalid_register": (
        ".CODE\nLI R16, d1\n",
        "Invalid register identifier:",
    ),
    "register_with_leading_zero": (
        ".CODE\nLI R01, d1\n",
        "Invalid register identifier:",
    ),
    "register_with_sign": (
        ".CODE\nLI R+1, d1\n",
        "Invalid register identifier:",
    ),
    "decimal_suffix": (
        ".DATA\nVALUE d12junk\n",
        "Invalid numeric immediate:",
    ),
    "binary_suffix": (
        ".DATA\nVALUE b102\n",
        "Invalid numeric immediate:",
    ),
    "hex_suffix": (
        ".DATA\nVALUE x2ag\n",
        "Invalid numeric immediate:",
    ),
    "lowercase_data_label": (
        ".DATA\nvalue d1\n",
        "Invalid label:",
    ),
    "malformed_data_label": (
        ".DATA\nBAD-LABEL d1\n",
        "Invalid label:",
    ),
    "lowercase_code_label": (
        ".CODE\nentry LI R0, d1\n",
        "Invalid label:",
    ),
    "malformed_code_label": (
        ".CODE\nBAD-LABEL LI R0, d1\n",
        "Invalid label:",
    ),
    "unknown_opcode": (
        ".CODE\nUNKNOWN\n",
        "Unknown instruction opcode:",
    ),
    "duplicate_label": (
        ".DATA\nVALUE d1\n.CODE\nVALUE EXIT\n",
        "Duplicate label:",
    ),
    "def_requires_immediate": (
        ".CODE\nDEF R0\n",
        "DEF requires exactly one immediate value:",
    ),
    "text_address_displacement": (
        ".CODE\nLA R0, [R1 + t'x']\n",
        "Address displacement must be numeric:",
    ),
    "unknown_data_label": (
        ".CODE\nLA R0, MISSING\n",
        "Unknown data label in address:",
    ),
    "unknown_code_label": (
        ".CODE\nBRU MISSING\n",
        "Unknown code label:",
    ),
    "invalid_operand_type": (
        ".CODE\nADD R0, d1\n",
        "ADD operand 2 must be a register",
    ),
    "invalid_operand_count": (
        ".CODE\nEXIT d1\n",
        "EXIT requires 0 operands",
    ),
}


class ParserTests(unittest.TestCase):
    def test_compiler_available(self):
        self.assertTrue(COMPILER.is_file(), "Build SimpleASM/compile before running this harness")

    def test_valid_fixtures_match_parsed_program(self):
        self.assertTrue(SOURCES, "No parser .sasm fixtures found")
        for source in SOURCES:
            with self.subTest(fixture=source.name):
                expected = source.with_suffix(".expected.txt")
                self.assertTrue(expected.is_file(), f"Missing parsed-program snapshot: {expected.name}")
                result = subprocess.run(
                    [str(COMPILER), "--emit", "print", str(source)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"Parser/compiler rejected {source.name}:\n{result.stderr}",
                )
                self.assertEqual(result.stderr, "", f"Unexpected diagnostics for {source.name}")
                self.assertEqual(result.stdout, expected.read_text(), f"Parsed program differs for {source.name}")

    def test_invalid_sources_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="simpleasm-parser-") as temp_dir:
            for name, (source_text, expected_error) in INVALID_SOURCES.items():
                with self.subTest(source=name):
                    source = Path(temp_dir) / f"{name}.sasm"
                    source.write_text(source_text)
                    result = subprocess.run(
                        [str(COMPILER), "--emit", "print", str(source)],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0, f"Parser accepted invalid source {name}")
                    self.assertEqual(result.stdout, "", f"Invalid source {name} produced parsed output")
                    self.assertIn(expected_error, result.stderr, f"Unexpected parser error for {name}")


if __name__ == "__main__":
    unittest.main()
