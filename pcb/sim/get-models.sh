#!/bin/sh
# Download TI's SPICE models into models/ (git-ignored: they are TI's, not ours to publish).
# The unencrypted PSpice versions, which ngspice reads in its PSpice mode (ngbehavior=psa).
set -e
cd "$(dirname "$0")"
mkdir -p models
get() {  # literature number, file in the zip, name to save as
	[ -f "models/$3" ] && return
	curl -sSfL -A "Mozilla/5.0" -o "models/$1.zip" "https://www.ti.com/lit/zip/$1"
	unzip -p "models/$1.zip" "$2" | tr -d '\r' > "models/$3"
	rm "models/$1.zip"
}
get sbom627 OPA164x.LIB opa164x.lib                          # OPA1641/2/4 (Rev. D)
get slcj016 lm393.lib lm393.lib                              # LM393 (LM2903B/LM393B model)
get slvmda8 TPS61040_lib/TPS61040.lib tps61040.lib           # TPS61040 unencrypted transient
get sbvm528 TPS7A4901_TRANS.LIB tps7a4901.lib                # TPS7A4901 unencrypted transient
# TI marks some resistors noiseless with PSpice's T_ABS=-273.15, which ngspice ignores: the OPA164x
# then shows 65 nV/sqrt(Hz) instead of its 5.1. ngspice's own switch for that is noisy=0.
sed -i 's/^\(\.MODEL R_NOISELESS RES (T_ABS=-273.15\))/\1 noisy=0)/I' models/*.lib
# A typo in TI's TPS61040 model ("PARAMS: PARAMS:"), which PSpice forgives and ngspice does not.
sed -i 's/PARAMS: PARAMS:/PARAMS:/' models/tps61040.lib
ls models
