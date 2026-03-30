#!/usr/bin/env python3
"""
Ghidra string + function extractor using PyGhidra.

Usage:
  python3 ghidra_export_pyghidra.py

Imports libapp.so, extracts all defined strings and function names,
writes results to docs/RE-libapp-functions.txt
"""
import pyghidra
import os

BINARY = os.path.expanduser("~/projects/fluidra-re/native/lib/arm64-v8a/libapp.so")
OUTPUT = os.path.expanduser("~/projects/ha-fluidra-pool/docs/RE-libapp-functions.txt")
GHIDRA_HOME = "/opt/ghidra/ghidra_12.0.4_PUBLIC"

print(f"[*] Opening {BINARY} in Ghidra...")

with pyghidra.open_program(BINARY, ghidra_install_dir=GHIDRA_HOME, analyze=True) as flat_api:
    from ghidra.program.model.data import StringDataType, StringUTF8DataType, UnicodeDataType

    program = flat_api.getCurrentProgram()
    listing = program.getListing()

    strings = []
    functions = []

    print("[*] Collecting defined strings...")
    data_iter = listing.getDefinedData(True)
    while data_iter.hasNext():
        d = data_iter.next()
        dt = d.getDataType()
        if isinstance(dt, (StringDataType, StringUTF8DataType, UnicodeDataType)):
            try:
                val = str(d.getValue())
                if len(val) > 3:
                    strings.append(f"STR\t0x{d.getAddress().getOffset():x}\t{val}")
            except Exception:
                pass

    print(f"[*] Found {len(strings)} strings")

    print("[*] Collecting function names...")
    func_iter = listing.getFunctions(True)
    while func_iter.hasNext():
        f = func_iter.next()
        functions.append(f"FUN\t0x{f.getEntryPoint().getOffset():x}\t{f.getName()}")

    print(f"[*] Found {len(functions)} functions")

    results = strings + functions
    with open(OUTPUT, "w") as fh:
        fh.write("\n".join(results) + "\n")

    print(f"[+] Wrote {len(results)} entries to {OUTPUT}")
    print(f"    strings={len(strings)}  functions={len(functions)}")
