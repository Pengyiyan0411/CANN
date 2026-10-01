#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
cd "$(dirname "$0")"
mkdir -p logs
cmake -S . -B build -DNPU_ARCH=dav-2201 >logs/configure.log 2>&1
cmake --build build -j2 >logs/build.log 2>&1
sha256sum r03.asc r06.asc build/bench_r03 build/bench_r06 >logs/build_hashes.txt
