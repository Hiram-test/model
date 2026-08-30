#!/bin/bash
set -euo pipefail
ROOT="${1:-$PWD/ccx-build}"
mkdir -p "$ROOT"
cd "$ROOT"
if [ ! -d CalculiX/ccx_2.23/src ]; then
  curl -L --fail -o ccx_2.23.src.tar.bz2 http://www.dhondt.de/ccx_2.23.src.tar.bz2
  tar -xjf ccx_2.23.src.tar.bz2
fi
cd CalculiX/ccx_2.23/src
cat > Makefile.gha <<'EOF'
CFLAGS = -Wall -O2 -I/usr/include/spooles -DARCH="Linux" -DSPOOLES -DARPACK -DMATRIXSTORAGE -DNETWORKOUT
FFLAGS = -Wall -O2 -cpp
CC=gcc
FC=gfortran
.c.o :
	$(CC) $(CFLAGS) -c $<
.f.o :
	$(FC) $(FFLAGS) -c $<
include Makefile.inc
SCCXMAIN = ccx_2.23.c
OCCXF = $(SCCXF:.f=.o)
OCCXC = $(SCCXC:.c=.o)
OCCXMAIN = $(SCCXMAIN:.c=.o)
LIBS = -lspooles -larpack -llapack -lblas -lpthread -lm
ccx_2.23: $(OCCXMAIN) ccx_2.23.a
	./date.pl; $(CC) $(CFLAGS) -c ccx_2.23.c; $(FC) -Wall -O2 -o $@ $(OCCXMAIN) ccx_2.23.a $(LIBS)
ccx_2.23.a: $(OCCXF) $(OCCXC)
	ar vr $@ $?
EOF
make -f Makefile.gha -j"$(nproc)" ccx_2.23
test -x ccx_2.23
./ccx_2.23 -v || true
sha256sum ccx_2.23 | tee "$ROOT/ccx_2.23.sha256"
cp -f ccx_2.23 "$ROOT/ccx_2.23"
echo "CCX_BIN=$ROOT/ccx_2.23"
