from reference_runtime import run_reference

registers = [0] * 17
registers[0] = 1 << 63
registers[1] = (1 << 64) - 1

raise SystemExit(run_reference(registers, bytearray()))
