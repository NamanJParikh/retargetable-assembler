"""Differentially test the Python and x86 SimpleASM emitters."""
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

from show_x86_state import read_snapshot


SCRIPT_DIR = Path(__file__).resolve().parent
EMITTER_FIXTURE_DIR = SCRIPT_DIR / "emitter-tests"
SHARED_FIXTURE_DIR = EMITTER_FIXTURE_DIR / "shared"
ADDITIONAL_FIXTURE_DIR = EMITTER_FIXTURE_DIR / "additional"
COMPILER = SCRIPT_DIR.parent / "compile"
DOCKER_IMAGE = "ubuntu:24.04"
FIXTURE_SOURCES = sorted(SHARED_FIXTURE_DIR.glob("*.sasm")) + sorted(
    ADDITIONAL_FIXTURE_DIR.glob("*.sasm")
)


def fixture_label(source):
    return source.relative_to(EMITTER_FIXTURE_DIR).as_posix()


def compile_program(target, source, output, state_snapshot=False):
    command = [str(COMPILER), "--emit", target]
    if state_snapshot:
        command.extend(["--x86-state-fd", "3"])
    command.extend(["-o", str(output), str(source)])
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def read_python_state(stdout):
    marker = "\nReturn code (R0): "
    program_stdout, separator, state = stdout.partition(marker)
    if not separator:
        raise AssertionError("Python emitter did not print its final-state report")

    return_code, _, state = state.partition("\n")
    registers = {
        f"R{index}": int(value)
        for index, value in re.findall(r"^  R(\d+): (\d+)$", state, re.MULTILINE)
    }
    rc_match = re.search(r"^  Rc: (\d+)$", state, re.MULTILINE)
    storage_match = re.search(
        r"^Storage contents \(hex\): ([0-9a-f]*)$", state, re.MULTILINE
    )
    if not rc_match or not storage_match:
        raise AssertionError("Python emitter final-state report is malformed")
    return (
        program_stdout,
        int(return_code),
        registers,
        int(rc_match.group(1)),
        bytes.fromhex(storage_match.group(1)),
    )


def read_writable_segment(path):
    image = path.read_bytes()
    if image[:4] != b"\x7fELF" or image[4] != 2 or image[5] != 1:
        raise AssertionError("x86 emitter did not produce a little-endian ELF64 executable")

    program_header_offset = struct.unpack_from("<Q", image, 32)[0]
    program_header_size = struct.unpack_from("<H", image, 54)[0]
    program_header_count = struct.unpack_from("<H", image, 56)[0]
    for index in range(program_header_count):
        header_offset = program_header_offset + index * program_header_size
        kind, flags, _, virtual_address, _, _, memory_size, _ = struct.unpack_from(
            "<IIQQQQQQ", image, header_offset
        )
        if kind == 1 and flags & 2:
            return virtual_address, memory_size
    raise AssertionError("x86 ELF has no writable load segment")


class EmitterDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not COMPILER.is_file():
            raise RuntimeError("Build SimpleASM/compile before running this harness")

    def test_fixture_corpus_has_expected_results(self):
        self.assertTrue(FIXTURE_SOURCES, "No emitter fixtures found")
        for source in FIXTURE_SOURCES:
            label = fixture_label(source)
            with self.subTest(fixture=label):
                print(f"  fixture corpus: {label}", flush=True)
                expected_file = source.with_suffix(".expected.json")
                self.assertTrue(expected_file.is_file(), f"Missing results: {expected_file.name}")
                expected = json.loads(expected_file.read_text())
                reference = source.with_suffix(".expected.py")
                if source.parent == SHARED_FIXTURE_DIR and not expected.get("compile_error"):
                    self.assertTrue(reference.is_file(), f"Missing Python reference: {reference.name}")

    def test_both_emitters_reject_statically_invalid_fixtures(self):
        for source in FIXTURE_SOURCES:
            expected_file = source.with_suffix(".expected.json")
            expected = json.loads(expected_file.read_text())
            expected_error = expected.get("compile_error")
            if not expected_error:
                continue

            label = fixture_label(source)
            with self.subTest(fixture=label):
                print(f"  compile rejection: {label}", flush=True)
                with tempfile.TemporaryDirectory(prefix="simpleasm-compile-rejection-") as temp_dir:
                    work_dir = Path(temp_dir)
                    python_output = work_dir / "program.py"
                    x86_output = work_dir / "program.out"
                    python_result = compile_program("python", source, python_output)
                    x86_result = compile_program("x86", source, x86_output)

                    self.assertNotEqual(python_result.returncode, 0)
                    self.assertIn(
                        expected_error.replace("x86", "Python", 1),
                        python_result.stderr,
                    )
                    self.assertFalse(python_output.exists())
                    self.assertNotEqual(x86_result.returncode, 0)
                    self.assertIn(expected_error, x86_result.stderr)
                    self.assertFalse(x86_output.exists())

    def test_both_emitters_reject_invalid_memory_widths(self):
        invalid_sources = {
            "LMU zero width": ".DATA\nVALUE d0\n.CODE\nLMU R0, VALUE, d0\nEXIT\n",
            "LMS width above eight": ".DATA\nVALUE d0\n.CODE\nLMS R0, VALUE, d9\nEXIT\n",
            "ST zero width": ".DATA\nVALUE d0\n.CODE\nST R0, VALUE, d0\nEXIT\n",
            "ST width above eight": ".DATA\nVALUE d0\n.CODE\nST R0, VALUE, d9\nEXIT\n",
        }
        with tempfile.TemporaryDirectory(prefix="simpleasm-invalid-width-") as temp_dir:
            work_dir = Path(temp_dir)
            for name, source_text in invalid_sources.items():
                with self.subTest(width=name):
                    print(f"  invalid width: {name}", flush=True)
                    source = work_dir / f"{name.replace(' ', '-')}.sasm"
                    source.write_text(source_text)
                    for target in ("python", "x86"):
                        output = work_dir / f"{source.stem}.{target}"
                        result = compile_program(target, source, output)
                        self.assertNotEqual(result.returncode, 0, f"{target} accepted {name}")
                        self.assertIn(
                            "size must be between 1 and 8 bytes",
                            result.stderr,
                            f"Unexpected {target} diagnostic for {name}",
                        )
                        self.assertFalse(output.exists())

    def test_x86_rejects_registers_outside_simpleasm_range(self):
        invalid_sources = {
            "R16 instruction operand": (".CODE\nLI R16, d1\nEXIT\n", "register"),
            "condition register as general register": (
                ".CODE\nLI Rc, d1\nEXIT\n",
                "must be a general register",
            ),
        }
        with tempfile.TemporaryDirectory(prefix="simpleasm-invalid-register-") as temp_dir:
            work_dir = Path(temp_dir)
            for name, (source_text, expected_error) in invalid_sources.items():
                with self.subTest(source=name):
                    print(f"  invalid x86 register: {name}", flush=True)
                    source = work_dir / "invalid.sasm"
                    source.write_text(source_text)
                    output = work_dir / "program.out"
                    result = compile_program("x86", source, output)
                    self.assertNotEqual(result.returncode, 0, f"Compiler accepted {name}")
                    self.assertIn(expected_error, result.stderr)
                    self.assertFalse(output.exists())

    def test_runtime_fixtures_match_between_emitters(self):
        if shutil.which("docker") is None:
            self.skipTest("Docker is required to run x86 ELF tests")
        try:
            docker_info = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.skipTest("Docker is unavailable: `docker info` timed out after 15 seconds")
        except OSError as error:
            self.skipTest(f"Docker is unavailable: could not run `docker info`: {error}")
        if docker_info.returncode != 0:
            detail = docker_info.stderr.strip()
            suffix = f": {detail}" if detail else ""
            self.skipTest(
                "Docker is unavailable or its daemon is not running: "
                f"`docker info` exited with status {docker_info.returncode}{suffix}"
            )

        for source in FIXTURE_SOURCES:
            expected_file = source.with_suffix(".expected.json")
            expected = json.loads(expected_file.read_text())
            if expected.get("compile_error"):
                continue

            label = fixture_label(source)
            with self.subTest(fixture=label):
                print(f"  differential fixture: {label}", flush=True)
                with tempfile.TemporaryDirectory(prefix="simpleasm-differential-") as temp_dir:
                    work_dir = Path(temp_dir)
                    python_output = work_dir / "program.py"
                    x86_output = work_dir / "program.out"
                    snapshot = work_dir / "state.bin"
                    python_compile = compile_program("python", source, python_output)
                    self.assertEqual(
                        python_compile.returncode,
                        0,
                        f"Python compiler failed for {source.name}:\n{python_compile.stderr}",
                    )
                    x86_compile = compile_program(
                        "x86", source, x86_output, state_snapshot=True
                    )
                    self.assertEqual(
                        x86_compile.returncode,
                        0,
                        f"x86 compiler failed for {source.name}:\n{x86_compile.stderr}",
                    )

                    env = os.environ.copy()
                    env["PYTHONDONTWRITEBYTECODE"] = "1"
                    python_result = subprocess.run(
                        [sys.executable, str(python_output)],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                        env=env,
                    )
                    x86_result = subprocess.run(
                        [
                            "docker", "run", "--rm", "--platform", "linux/amd64",
                            "--volume", f"{work_dir}:/work",
                            "--workdir", "/work",
                            DOCKER_IMAGE,
                            "sh", "-c", "exec 3>state.bin; exec ./program.out",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                    )
                    self.assertEqual(
                        python_result.returncode,
                        expected["exit_status"],
                        f"Python exit differs for {source.name}",
                    )
                    self.assertEqual(x86_result.returncode, expected["exit_status"])
                    self.assertEqual(x86_result.stdout, expected["stdout"])
                    self.assertEqual(x86_result.stderr, expected["stderr"])
                    self.assertTrue(snapshot.is_file(), f"No state snapshot for {source.name}")

                    python_stdout, python_r0, python_registers, python_rc, python_storage = (
                        read_python_state(python_result.stdout)
                    )
                    x86_registers, x86_rc, x86_storage = read_snapshot(snapshot)
                    self.assertEqual(python_result.returncode, x86_result.returncode)
                    self.assertEqual(python_stdout, x86_result.stdout)
                    self.assertEqual(python_result.stderr, x86_result.stderr)
                    self.assertEqual(python_r0, expected["registers"].get("R0", 0))
                    self.assertEqual(python_rc, x86_rc)
                    self.assertEqual(x86_rc, expected["rc"])
                    self.assertEqual(
                        python_storage[:len(x86_storage)],
                        x86_storage,
                        "Declared storage differs between emitters",
                    )
                    self.assertEqual(x86_storage.hex(), expected["storage_hex"])

                    data_base, data_size = read_writable_segment(x86_output)
                    for index, x86_value in enumerate(x86_registers):
                        name = f"R{index}"
                        python_value = python_registers[name]
                        expected_value = expected["registers"].get(name, 0)
                        self.assertEqual(
                            x86_value,
                            expected_value,
                            f"x86 reference state differs for {name}",
                        )
                        if (
                            data_base <= x86_value < data_base + data_size
                            and x86_value - data_base == python_value
                        ):
                            continue
                        self.assertEqual(
                            x86_value,
                            python_value,
                            f"Final {name} differs between emitters",
                        )

                    reference = source.with_suffix(".expected.py")
                    if reference.is_file():
                        reference_result = subprocess.run(
                            [sys.executable, str(reference)],
                            capture_output=True,
                            text=True,
                            timeout=5,
                            check=False,
                            env=env,
                        )
                        self.assertEqual(
                            python_result.returncode,
                            reference_result.returncode,
                            f"Python exit differs from reference for {source.name}",
                        )
                        self.assertEqual(
                            python_result.stdout,
                            reference_result.stdout,
                            f"Python output differs from reference for {source.name}",
                        )
                        self.assertEqual(
                            python_result.stderr,
                            reference_result.stderr,
                            f"Python stderr differs from reference for {source.name}",
                        )
                print(f"  passed: {label}", flush=True)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EmitterDifferentialTests)
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    docker_skip_reasons = [
        reason
        for _, reason in result.skipped
        if reason.startswith(("Docker is required", "Docker is unavailable"))
    ]
    if docker_skip_reasons:
        print("Docker unavailable; x86 runtime differential tests were skipped:")
        for reason in docker_skip_reasons:
            print(f"  {reason}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
