# PREREG example (not a real layer run)

Format example for the layer-improvement gate. `synthetic.txt` and `sample.txt` are stand-in inputs, not anatomy. Hashes below are the md5 of the files next to this one. `prereg_md5` is the md5 of this file with that one line removed. Do not edit a hash to make a run pass; write a new PREREG instead.

```prereg
prereg_md5: bea04298b5d60e57c0163f5f0e1834b0
script: write_layer.py 837e324fc07025e0a69ba5efe94c35b9
input: synthetic.txt b4ed168e23fddde517fe0bcc37726fe1
input: sample.txt 82a030ed5b28c5186502700696814388
env: OMP_NUM_THREADS=1
env: MKL_NUM_THREADS=1
env: OPENBLAS_NUM_THREADS=1
smoke: python3 write_layer.py synthetic.txt {outdir}
run: python3 write_layer.py sample.txt {outdir}
output: mesh.obj
staging: staging/layer-r1
status: staging/layer-r1-STATUS.md
md5sums: staging/layer-r1-MD5SUMS
# optional; omit a line to skip that limit
# memory_cap_mb: 4096
# free_ram_floor_mb: 512
# timeout_sec: 3600
```
