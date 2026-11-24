from reference_runtime import run_reference

MASK64 = (1 << 64) - 1
registers = [0] * 17

# The .DATA entries are packed consecutively: numeric values use eight
# little-endian bytes and text values include a trailing NUL byte.
word = 0x0102030405060708
word_bytes = word.to_bytes(8, "little")
memory = bytearray(
    word_bytes
    + bytes(8)
    + b"SimpleASM\0"
    + b" tests!\0"
    + (99).to_bytes(8, "little")
)

# Apply the loads and stores in source order using their specified widths.
registers[0] = 73
registers[1] = 0
registers[2] = int.from_bytes(memory[0:1], "little")
registers[3] = int.from_bytes(memory[2:4], "little")
registers[4] = int.from_bytes(memory[0:8], "little")
memory[8:16] = registers[4].to_bytes(8, "little")
registers[5] = 254
memory[8:9] = bytes((registers[5] & 0xFF,))
registers[6] = int.from_bytes(memory[8:9], "little")
registers[7] = int.from_bytes(memory[8:9], "little", signed=True) & MASK64
registers[8] = 8
registers[9] = 4660
memory[registers[8] + 2:registers[8] + 4] = registers[9].to_bytes(2, "little")
registers[10] = int.from_bytes(memory[registers[8] + 2:registers[8] + 4], "little")
registers[11] = 32768
memory[12:14] = registers[11].to_bytes(2, "little")
registers[12] = int.from_bytes(memory[12:14], "little", signed=True) & MASK64
registers[13] = 16
registers[5] = 2
registers[14] = int.from_bytes(memory[0:4], "little")
registers[15] = int.from_bytes(memory[34:42], "little")

raise SystemExit(run_reference(registers, memory, "SimpleASM" + " tests!"))
