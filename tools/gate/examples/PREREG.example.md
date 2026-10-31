# PREREG example (not a real layer run)

Format example for the layer-improvement gate. `synthetic.txt` and `sample.txt` are stand-in inputs, not anatomy. Hashes below are the md5 of the files next to this one. Do not edit a hash to make a run pass; write a new PREREG instead.

```prereg
script: write_layer.py b03a8995eab3f61f004d30d6549087d1
input: synthetic.txt b4ed168e23fddde517fe0bcc37726fe1
input: sample.txt 82a030ed5b28c5186502700696814388
smoke: python3 write_layer.py synthetic.txt {outdir}
run: python3 write_layer.py sample.txt {outdir}
output: mesh.obj
staging: staging/layer-r1
status: staging/layer-r1-STATUS.md
md5sums: staging/layer-r1-MD5SUMS
# optional peak RSS cap in mebibytes; omit the line to skip it
# memory_cap_mb: 4096
```
