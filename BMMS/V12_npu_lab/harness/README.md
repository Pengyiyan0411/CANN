# NPU validation and experiments

Follow-up tools (2026-09-28):

- `generate_followup.py`: 66 additional cases, including R06 layouts/tails, Native narrow-N and Split-K.
- `generate_native.py`: 41 Native scale/value/boundary cases. `--output cases_native_holdout --holdout` creates a separate holdout set.
- `run_screen.py`: serialized A/B/B/A (or alternating paired windows), checking every output; task durations are **profiled** measurements.
- `event_bench_r07`: one binary containing the baseline and candidate kernels, preallocated shared workspace, 100 warmup calls, alternating 64-call device-event windows. `BMMS_EVENT_AA=1` measures baseline-vs-baseline repeatability.
- `event_bench_r09`: the same auxiliary method for Native; launch-only path bypasses the public host dispatcher and is not the unknown Judge timer. It validates output after each window and exercises workspace reuse. Full `bench_rxx` validation remains mandatory.
- `analyze_followup.py` and `collect_followup.py`: summaries and evidence archive. Input and executable binaries remain on the remote lab, while manifests, hashes and logs are archived.

Build individual targets after CMake configuration, e.g. `cmake --build build --target bench_r09 -j2`. All files are full standalone source builds. Performance sessions must not overlap other NPU jobs or heavy builds.

## Initial batch

These are synthetic inputs, not the hidden 15 Judge cases. No source optimization is introduced here.

- r03/r06 source copies must match frozen source SHA256 values.
- TensorInfo/TensorGroupInfo exactly match the supplied original Judge main.asc.
- CMake uses the supplied Judge link libraries and `--npu-arch=dav-2201`.
- `BMMS_DEVICE` selects one visible logical NPU; default 0. Tests run sequentially.
- Generate inputs using `TORCH_DEVICE_BACKEND_AUTOLOAD=0 python3 generate_cases.py`; generation uses CPU only.
- FP64 reference is computed from the actual quantized FP16/BF16 tensors, before applying physical storage transpose.
- 34 cases: tiny static-K, Native, full R06 macro, tail R06 macro, zero and all-negative outputs. No claim of full route coverage.
- Runtime logs the actual cube core count and the r06 metadata guard.
- Three repeated calls with different NaN output poison; failure stops the batch.
- Host-call elapsed time includes allocation, planner, synchronization and free inside the submitted entry. It is explicitly **not kernel task time** and must not be compared with Judge microseconds.
- The original public verifier uses 1e-4 absolute/relative tolerance; this harness requires every finite output to satisfy that threshold against FP64. Hidden verifier details remain unavailable.

The lab does not modify the frozen sources or promote a baseline automatically. Device profiling/performance work starts after validation succeeds.
