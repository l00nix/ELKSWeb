#!/usr/bin/env python3
"""Prepare the upstream Nano-X client for the medium-model ELKS browser."""
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).read_text()
callback = "void * oldSignalHandler = signal"
if source.count(callback) != 1:
    raise SystemExit("Review Nano-X GrClose callback compatibility")
source = source.replace(callback, "void (*oldSignalHandler)(int) = signal")

# The ELKS tiny server implements CheckNextEvent, but the tiny client omits
# its entry point. Keep just that upstream routine available: synchronous
# event polling avoids pending replies blocking redraws on small sockets.
signature = "void \nGrCheckNextEvent(GR_EVENT *ep)\n{"
if source.count(signature) != 1:
    raise SystemExit("Review Nano-X GrCheckNextEvent implementation")
start = source.index(signature)
end = source.index("\n}", start) + 2
guard = source.rfind("\n#if !MW_FEATURE_TINY", 0, start)
if guard < 0 or "\n#endif" in source[guard:start]:
    raise SystemExit("Review Nano-X tiny-client event guard")
source = (source[:start] + "#endif /* !MW_FEATURE_TINY */\n" +
          source[start:end] + "\n#if !MW_FEATURE_TINY\n" + source[end:])
pathlib.Path(sys.argv[2]).write_text(source)
