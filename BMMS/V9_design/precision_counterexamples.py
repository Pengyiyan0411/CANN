"""Reproduce design counterexamples using CPU, small matrices and exact repeats."""
from pathlib import Path
import json
import numpy as np
from blocked_oracle import self_check


def main():
    # The repeated 8192x16 output is represented by one exact two-row pair.
    a = np.zeros((2, 32), np.float16)
    b = np.zeros((32, 1), np.float16)
    a[0, :2] = (1, 2**-12)
    a[1, 0] = -1
    b[:2, 0] = (1, 2**-13)
    pair = a.astype(np.float64) @ b.astype(np.float64)
    reference = np.float32(pair.sum(dtype=np.float64) * 4096)
    rounded = np.float32(pair.astype(np.float32).astype(np.float64).sum() * 4096)
    absolute = abs(float(reference) - float(rounded))
    relative = absolute / abs(float(reference))
    assert float(reference) == 2**-13 and rounded == 0
    c = np.array([[10, 9], [9, 10]], np.float64)
    split_k = np.array([[10, 0], [-10, 1]], np.float64)
    bf16_exact = np.array([2**24, 1, -2**24], np.float32)
    naive = np.float32(0)
    for value in bf16_exact:
        naive = np.float32(naive + value)
    with np.errstate(over="ignore"):
        overflowing = np.float32(np.float64(2**64) ** 2)
    assert not np.isfinite(overflowing)
    data = dict(
        scope="CPU mathematical counterexamples; no NPU run or compiler test",
        fp32_c_loss=dict(shape=[1,8192,16,32], stored_dtype="float16",
                        exact_dot_pair=pair[:,0].tolist(), repeats=4096,
                        golden=float(reference), rounded_c_then_exact_sum=float(rounded),
                        abs_error=absolute, rel_error=relative,
                        strict_pass=bool(absolute<1e-4 and relative<1e-4),
                        combined_pass=bool(absolute<=1e-4+1e-4*abs(float(reference)))),
        n_shard_scalar=dict(C=c.tolist(), golden=float(c.max(1).sum()),
                            max_of_shard_sums=float(c.sum(0).max()),
                            sum_of_shard_sums=float(c.sum())),
        split_k_early_max=dict(partials=split_k.tolist(),
                              golden=float(split_k.sum(0).max()),
                              sum_of_partial_max=float(split_k.max(1).sum())),
        n1_naive_fp32=dict(stored_dtype="bfloat16 (exact powers and one)",
                          values=bf16_exact.tolist(), golden=1.0,
                          sequential_fp32=float(naive)),
        finite_bf16_overflow=dict(shape=[1,1,1,32], nonzero_input=float(2**64),
                                 fp64_dot=float(np.float64(2**64)**2),
                                 fp32_finite=bool(np.isfinite(overflowing)),
                                 fp32_result="+Inf"),
        fp16_output_bound=dict(max_abs_y=float(8192*8192*np.float64(65504)**2),
                               fp32_max=float(np.finfo(np.float32).max)),
        blocked_oracle=self_check(),
    )
    target = Path(__file__).with_name("counterexamples.json")
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n",
                      encoding="utf-8")
    print(json.dumps(dict(output=str(target), fp32_c_loss=data["fp32_c_loss"],
                         blocked_oracle_layout_checks=data["blocked_oracle"]["layout_block_comparisons"],
                         status="all CPU assertions passed"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
