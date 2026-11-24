from reference_runtime import run_reference

registers = [0] * 17
memory = bytearray(8)
memory.extend(bytes(1))
memory[8:9] = bytes((registers[0] & 0xFF,))

raise SystemExit(run_reference(registers, memory))
