# Retargetable Assembly

SimpleASM is a small educational compiler for a register-based assembly-like
language. It parses one program into a shared intermediate representation, then
emits a runnable Python emulator or native Linux executables for x86-64 and
AArch64. The project is intended to explore compiler backends, machine
instructions, executable formats, and testing techniques.

## Features

- A compact but powerful language with `.DATA` and `.CODE` sections, 16 64-bit general
  registers (`R0`-`R15`), a persistent condition register (`Rc`), and
  arithmetic, memory, branching, and text-output instructions.
- One parser and program representation shared by independent emitters.
- Native x86-64 and AArch64 Linux ELF64 output, generated directly by the
  compiler without invoking an assembler or linker.
- A Python emitter that produces a readable, runnable emulator and reports the
  final guest registers and storage.
- Conservative compile-time rejection of statically provable out-of-bounds
  memory/text accesses and division by a known zero divisor.

The supported emitters are `python`, `x86`, and `arm`. IBM Z is listed as a
future target but is not implemented yet.

## Build

From the repository root, build the C++17 compiler with `clang++`, `g++`, or
another C++17 compiler:

```sh
c++ -std=c++17 -O2 SimpleASM/compiler.cpp -o SimpleASM/compile
```

## Quick start

Create a small program:

```sh
cat > /tmp/hello.sasm <<'EOF'
.DATA
MESSAGE t'Hello from SimpleASM!'
.CODE
START LI R0, d0
      WRTE MESSAGE
      EXIT
EOF
```

Use the Python emitter to generate and run an emulator:

```sh
./SimpleASM/compile --emit python /tmp/hello.sasm
python3 /tmp/hello.py
```

The generated Python script writes the program's text to standard output, then
prints its final register and storage state. The process status is the low byte
of `R0`.

To inspect the parsed program without generating a target:

```sh
./SimpleASM/compile --emit print /tmp/hello.sasm
```

## Emitters and output

```sh
# Python source: writes /tmp/hello.py by default
./SimpleASM/compile --emit python /tmp/hello.sasm

# Native x86-64 Linux ELF: writes /tmp/hello-x86.out
./SimpleASM/compile --emit x86 -o /tmp/hello-x86.out /tmp/hello.sasm

# Native AArch64 Linux ELF: binary output goes to stdout
./SimpleASM/compile --emit arm /tmp/hello.sasm > /tmp/hello-arm
chmod +x /tmp/hello-arm
```

Python and x86 output paths can also be selected with `-o` or `--output`.
`--emit arm` writes the ELF image to standard output so it can be redirected
to a file. The native targets are Linux executables: run x86 output on
x86-64 Linux and ARM output on AArch64 Linux. On other hosts, a suitably
configured Linux container or emulator can be used. For example, with Docker:

```sh
docker run --rm --platform linux/arm64 \
  --volume /tmp:/work --workdir /work ubuntu:24.04 ./hello-arm
```

Use `--help` for the command-line options. The `--x86-state-fd <fd>` and
`--arm-state-fd <fd>` options enable optional final-state snapshots on an
inherited file descriptor for debugging; both use the same binary snapshot
format.

## Design highlights

### Retargetable front end

The parser converts source into a `Program` containing ordered data entries,
instructions, operands, and a symbol table. Emitters consume that shared
representation through a common interface, keeping parsing and language
semantics separate from target instruction encoding. This makes it possible
to compare different backends on the same input without changing the source
program.

### Register spilling

The guest language exposes 16 general registers, more than either backend can
dedicate safely to guest values while also reserving native registers for
address calculations, arithmetic, and Linux system calls.

- The x86-64 emitter maps guest `R0`-`R8` directly to native registers and
  stores `R9`-`R15` in zero-initialized eight-byte slots in the writable data
  segment.
- The AArch64 emitter maps `R0`-`R9` to `X19`-`X28`, which survive Linux system
  calls, and spills `R10`-`R15` to six eight-byte slots after declared program
  storage.

Spilled values are loaded into scratch registers when needed and written back
when modified. The condition register is stored separately so comparisons
remain observable by later conditional branches. Internal spill and condition
slots are excluded from guest storage snapshots.

### Python as a differential reference

The Python emitter implements the same 64-bit register and memory model in
generated, inspectable Python code. The emitter test suite runs shared
SimpleASM fixtures through Python, x86, and ARM, comparing output, exit status,
registers, condition state, and storage. This provides a portable reference
for validating native backends, including register spilling and memory
behavior.

## Tests

Run the parser and emitter suites from the repository root:

```sh
python3 SimpleASM/test-scripts/test_parser.py
python3 SimpleASM/test-scripts/test_emitters.py
```

The emitter suite uses Docker to run the native Linux executables (`linux/amd64`
for x86 and `linux/arm64` for ARM); Docker is not required for the parser
suite. More details about fixtures, snapshots, and test behavior are in
[`SimpleASM/test-scripts/README.md`](SimpleASM/test-scripts/README.md).

## Repository note

The `kaleidoscope/` directory contains the separate LLVM Kaleidoscope tutorial
compiler. This project began as an exploration into LLVM and compilers and evolved into SimpleASM.

# Personal Notes (taken throughout the project)

## Intro

So I decided to make some compilers. This is primarily an educational project for 
me, so the goal is to cover a lot of breadth and make working programs, not
necessarily of the best quality or optimization. I have a few more specific goals.

1. Get back into C++. 
    - I haven't touched C++ in a long time. Though I used C regularly through 
    college, I never needed C++ except for a small Arduino project.
2. Practice applying theory throughout implementation.
    - I love learning theory and I love building things. On paper, we want to
    extrapolate good design principles from theory and then build according to 
    those. In both school and work, I don't always get the chance to fully reason
    through the best design myself because things need to get done and good 
    principles are already agreed upon.
3. AI, of course
    - My job is one of the more cautious with AI usage, and the platforms we work
    on don't make using AI easy. I want to make more use of coding agents, but
    still maintain caution and verification at every step.
    - So much I see today is demos and prototypes that are great for funding 
    rounds because AI builds for appearances. But they don't always function great
    as full products. I'd like to make my own impression of best practices for
    coding with AI, not too crazed but also not too hesitant.
4. Open source exposure
    - I've always liked the idea of open source development and hope to contribute
    to projects like LLVM one day.
5. Going lower level
    - I'm very interested in working more with instruction sets, programming
    optimization, and thinking about how code actually runs on hardware. In
    this project, I plan to dig into the LLVM optimization passes and backend to
    learn more about connecting high-level computing tasks to optimized instructions.

## Part 1: The LLVM Tutorial

The LLVM tutorial creates a compiler for the toy language Kaleidoscope, and my
following of it can be found in ```./kaleidoscope```. Since this is a tutorial
with reference code, I won't use AI for this section.

### Chapters 1, 2, 3
Largely followed the tutorial but skipping extern. Tbh because I just don't care 
about it.

### Chapter 4
Decided to skip optimizatons and JIT in favor of completing the language syntax.
I will return after the later chapters on building your own JIT. 

### Chapter 5
Implemented the lexer, AST, and parser portions without the tutorial.

### Chapters 6, 7
Continued following the tutorial and implementing parts that were familiar (such
as lexer and AST extensions) independently before looking at the reference code.

### Chapter 8
Followed the tutorial, tested a few different functions using the variety of
syntax implemented.

## Part 2: Simple Assembly

To work more with machine code, I'll make a fairly simple but functional assembly
language and assemble it to a few architectures, as well as just a simple Python
emulator.

The main complexity here is in providing more registers than are available to 
use freely in machine architectures. This requires emitting machine code that 
manually manages some registers using memory rather than directly mapping to 
hardware registers.

To be honest, I'm not sure there's any value to this assembly language beyond
being educational. The point of writing code in assembly is to take full advantage
of the specific hardware details, so abstracting away the specific architecture 
makes it a futile exercise. But there's a lot to learn here and I'm not too 
concerned at this stage about the scheduling and allocation problems of a full 
IR backend.

### Parsing

The parser is quite straightforward because of how simple the language is. I
started using Copilot and Claude to help speed along the more tedious 
implementation like having to handle each individual instruction and also to 
quickly write entry points for testing.

### Python emulator

The purpose of this is mostly just to work through the process of an emitter
while producing an easily readable and runnable result. 

### x86 Emitter

This is the first really significant chunk of this part. I got some good experience
working out design decisions and details as part of the process of implementing
it with AI and forcing it to go step by step and verify each step. There's a lot
of debugging and verification that still had to be done, but it certainly made
the process a lot faster. I found a good balance of the size of each step so that
I've moved through it quickly but the chunks of AI generated code are still a 
reviewable and editable size. This made verifying the code and debugging the bugs 
I did find a pleasant process.

I also had to relearn a bunch about x86 and learn more about executable formats
and how to format machine code instructions and emit them. The LLVM backend code
was very useful to review for getting comfortable with the idea of producing
a raw executable and understanding how to handle issues like instruction encoding
and addressing.

### Code Review AI-generated code

I'm finding the generated code even by the currently lowest-tier models to be
quite good, although not the most polished. It definitely continues to need good
review to keep good design and consistent structure throughout the program. It's also 
just good practice to reign in the models a bit because they get a bit overzealous
with making changes, and I don't want the code to get away from me too much.

### Unit Testing

This is definitely made a lot more efficient with AI, but I'm finding that it 
needs some pointers to get comprehensive tests. Unrelated to AI, I've never
used elaborate testing tools like the python unittest library, so I'm finding
the process very informative.

### Differential Testing and Resolving Issues

I've focused a lot of effort into the testing methodology, ensuring it's simple to use,
comprehensive, and fairly rigorous. There are certainly more rigorous methods I 
could use, but I think differential testing is sufficient for the sake of
this project. In particular, using the LLVM backend as reference and comparing 
program byte by byte or at least the state line by line would be more thorough, 
something I may come back to after implementation is done. 

I think testing is perhaps the best place to start when using AI-generated code
since it makes it so easy for agents to catch bugs as they go. It would also 
ensure tests are generated based on the SPEC and not the existing implementation
if the implementation doesn't exist yet. Because I learned this, I've prioritized
building and polishing the testing before moving on to implement the ARM emitter.
I think this will make that process much smoother and leave me with more confidence
in the final code.

I'm finding that the AI tools still tend to take shortcuts, like making tests
based on the compiler behavior rather than calculating expected behavior from the
SPEC, but with interruption and correction, they get there in the end. 

It is encouraging to see that asking AI to review the code and list issues it finds
produces a lot of the same issues I found in code review and was concerned about 
when testing, such as dead code and insufficient error parsing around `stoi` and
`stoll`. 