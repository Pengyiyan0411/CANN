"""CPU FP64 oracle with bounded C scratch; no intermediate FP32 dot rounding.

Inputs contain actual stored values. BF16 may be decoded to NumPy FP32 before
calling; the caller must quantize BEFORE calling, never after the reference.
This module does not certify device arithmetic or impose a Judge tolerance.
"""
from __future__ import annotations

import numpy as np


def golden(x1, x2, transpose_x1=False, transpose_x2=False,
           m_block=64, n_block=128):
    if m_block <= 0 or n_block <= 0:
        raise ValueError("positive block dimensions required")
    a = np.asarray(x1)
    b = np.asarray(x2)
    if a.ndim != 3 or b.ndim != 3:
        raise ValueError("rank-3 inputs required")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("finite stored input values required")
    if transpose_x1:
        a = a.swapaxes(1, 2)
    if transpose_x2:
        b = b.swapaxes(1, 2)
    batch, m, k = a.shape
    if b.shape[0] != batch or b.shape[1] != k:
        raise ValueError("equal batch and K required; broadcasting forbidden")
    n = b.shape[2]
    if min(batch, m, n, k) <= 0:
        raise ValueError("empty inputs forbidden")
    result = np.empty(batch, dtype=np.float32)
    # Keep every row max in FP64 until the final reduction over M.  Only one
    # batch is live: scratch is O(M + m_block*n_block + (m_block+n_block)*K).
    for bi in range(batch):
        row_max = np.full(m, -np.inf, dtype=np.float64)
        for m0 in range(0, m, m_block):
            m1 = min(m0 + m_block, m)
            aa = a[bi, m0:m1, :].astype(np.float64)
            maxima = row_max[m0:m1]
            for n0 in range(0, n, n_block):
                n1 = min(n0 + n_block, n)
                bb = b[bi, :, n0:n1].astype(np.float64)
                # Every output dot spans ALL K in FP64 before Max(N).
                cc = aa @ bb
                np.maximum(maxima, cc.max(axis=1), out=maxima)
        # The contract's possible BF16->FP32 overflow remains visible here.
        with np.errstate(over="ignore", invalid="ignore"):
            result[bi] = row_max.sum(dtype=np.float64)
    return result


def _bf16_stored(x):
    """Round normal test FP32 values to BF16 RNE, represented as FP32."""
    bits = np.asarray(x, dtype=np.float32).view(np.uint32).copy()
    bits += np.uint32(0x7fff) + ((bits >> 16) & np.uint32(1))
    bits &= np.uint32(0xffff0000)
    return bits.view(np.float32)


def self_check():
    rng = np.random.default_rng(290626)
    results = []
    for dtype_name, quantize in (("float16", lambda x: x.astype(np.float16)),
                                ("bfloat16_decoded", _bf16_stored)):
        a = quantize(rng.uniform(-1, 1, (2, 17, 40)).astype(np.float32))
        b = quantize(rng.uniform(-1, 1, (2, 40, 19)).astype(np.float32))
        reference = (a.astype(np.float64) @ b.astype(np.float64)).max(2).sum(
            1, dtype=np.float64).astype(np.float32)
        for ta in (False, True):
            for tb in (False, True):
                ap = np.ascontiguousarray(a.swapaxes(1, 2) if ta else a)
                bp = np.ascontiguousarray(b.swapaxes(1, 2) if tb else b)
                for mb, nb in ((1, 1), (3, 7), (64, 128)):
                    actual = golden(ap, bp, ta, tb, mb, nb)
                    assert np.array_equal(actual.view(np.uint32), reference.view(np.uint32))
                    results.append(dict(dtype=dtype_name, ta=ta, tb=tb,
                                        m_block=mb, n_block=nb, bitwise_equal=True))
    # C-to-FP32 before the M sum would erase this exact nonzero result.
    a = np.zeros((1, 17, 32), np.float16)
    b = np.zeros((1, 32, 3), np.float16)
    a[0, 0, :2] = (1, 2**-12)
    a[0, 1, 0] = -1
    b[0, 0, :] = 1
    b[0, 1, :] = 2**-13
    assert golden(a, b, m_block=1, n_block=1)[0] == np.float32(2**-25)
    all_negative = golden(np.ones((1, 3, 32), np.float16),
                          -np.ones((1, 32, 17), np.float16),
                          m_block=2, n_block=5)
    assert all_negative[0] == np.float32(-96)
    invalid_checks = 0
    for aa, bb in ((np.zeros((1, 2, 32)), np.zeros((2, 32, 3))),
                   (np.zeros((1, 2, 32)), np.zeros((1, 40, 3))),
                   (np.full((1, 2, 32), np.nan), np.zeros((1, 32, 3)))):
        try:
            golden(aa, bb)
        except ValueError:
            invalid_checks += 1
        else:
            raise AssertionError("invalid oracle input accepted")
    return dict(layout_block_comparisons=len(results), comparisons=results,
                cancellation_preserved=True, all_negative_correct=True,
                rejected_invalid_inputs=invalid_checks,
                limitation="CPU oracle tests, not a device precision certification")


if __name__ == "__main__":
    import json
    print(json.dumps(self_check(), ensure_ascii=False, indent=2))
