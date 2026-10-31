"""Stand-in layer script for the gate example.

Reads one input file and writes a deterministic mesh.obj in the output
directory. The same input bytes always produce the same mesh.obj.
This is not a pipeline and it does not contain anatomy.
"""

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        sys.stderr.write("usage: write_layer.py INPUT OUTDIR\n")
        sys.exit(2)
    data = Path(sys.argv[1]).read_bytes()
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / "mesh.obj"
    if target.exists():
        sys.stderr.write(f"refusing to overwrite {target}\n")
        sys.exit(1)
    target.write_bytes(b"o layer\n" + b"# bytes %d\n" % len(data) + data)


if __name__ == "__main__":
    main()
