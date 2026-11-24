from reference_runtime import run_reference

registers = [0] * 17
memory = bytearray(8)
memory.extend(bytes(1))
registers[0] = int.from_bytes(memory[8:9], "little")

raise SystemExit(run_reference(registers, memory))
