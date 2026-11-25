# SimpleASM test scripts

### Parser

Run the parser regression suite from the repository root:

```sh
python3 SimpleASM/test-scripts/test_parser.py
```

The parser harness runs the compiler with `--emit print` and compares its
parsed-program output to the paired `parser/*.expected.txt` snapshots. Its
fixtures cover every opcode, operand type, immediate type, addressing form,
label handling, data-only and code-only programs, and empty input. It also
checks malformed numeric values, text commas, exact register and label syntax,
unknown labels, and invalid operand counts and types.

### Emitters

Build `SimpleASM/compile`, then run the combined Python/x86/ARM differential
suite from the repository root:

```sh
python3 SimpleASM/test-scripts/test_emitters.py
```

The combined harness reads its complete fixture corpus from
`emitter-tests/shared/` and `emitter-tests/additional/`; it no longer reads
fixtures from the separate emitter-specific directories. Each valid fixture is
compiled and run through the Python, x86, and ARM emitters, comparing process
status and program output. The x86 tests additionally compare final registers,
condition state, and declared storage using x86 state snapshots, and normalize
x86 native data addresses against Python byte offsets. ARM runtime tests use
`linux/arm64` containers and compare observable behavior with the Python
emulator. Paired Python reference scripts and x86 JSON snapshots remain as
independent checks. Statically invalid accesses and division by zero must be
rejected by all emitters. The suite also checks invalid memory widths and
native-emitter register restrictions. Docker is required to execute generated ELF
files; x86 tests use `linux/amd64` and ARM tests use `linux/arm64`.

For x86-64 ELF tests on macOS, run the generated executable in an `amd64` Linux
container. `--x86-state-fd 3` enables a final-state snapshot on inherited file
descriptor 3, separate from program stdout:

```sh
SimpleASM/compile --emit x86 --x86-state-fd 3 -o /tmp/program.out path/to/program.sasm
docker run --rm --platform linux/amd64 -v /tmp:/work -w /work ubuntu:24.04 \
  sh -c 'exec 3>state.bin; exec ./program.out'
```

The snapshot file is `/tmp/state.bin` on the host. Its binary layout is
documented in `SimpleASM/SPEC.md`; it contains the x86 backend's supported
registers R0-R15, Rc, and the final program storage bytes.
Display it from the repository root with:

```sh
python3 SimpleASM/test-scripts/show_x86_state.py /tmp/state.bin
```

The script prints registers in decimal and hexadecimal and storage in
offsetted hexadecimal/ASCII rows. If no path is provided, it reads `state.bin`
from the current directory.
