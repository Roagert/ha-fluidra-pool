# Ghidra headless script — extract strings and defined data from libapp.so
# Run via: analyzeHeadless ... -postScript ghidra_strings.py
# Output: /tmp/ghidra_fluidra/libapp_strings.txt

import os
from ghidra.program.model.data import StringDataType, StringUTF8DataType
from ghidra.program.model.listing import CodeUnit

OUTPUT = "/tmp/ghidra_fluidra/libapp_strings.txt"

program = currentProgram
listing = program.getListing()
memory = program.getMemory()

results = []

# Walk all defined data, collect strings
data_iter = listing.getDefinedData(True)
while data_iter.hasNext():
    d = data_iter.next()
    dt = d.getDataType()
    if isinstance(dt, (StringDataType, StringUTF8DataType)):
        try:
            val = d.getValue()
            if val and len(str(val)) > 3:
                results.append("STR 0x{:x} {}".format(d.getAddress().getOffset(), str(val)))
        except Exception:
            pass

# Walk defined functions
func_iter = listing.getFunctions(True)
count = 0
while func_iter.hasNext():
    f = func_iter.next()
    name = f.getName()
    addr = f.getEntryPoint().getOffset()
    results.append("FUN 0x{:x} {}".format(addr, name))
    count += 1

with open(OUTPUT, "w") as fh:
    fh.write("\n".join(results))

print("ghidra_strings.py: wrote {} entries to {}".format(len(results), OUTPUT))
print("  strings: {}  functions: {}".format(len(results) - count, count))
