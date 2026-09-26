"""FP64 whole-operator oracle and separate strict/combined acceptance gates."""
import numpy as np

def golden(x1,x2,transpose_x1=False,transpose_x2=False):
    a=np.asarray(x1);b=np.asarray(x2)
    if a.ndim!=3 or b.ndim!=3: raise ValueError('rank must be 3')
    a=a.astype(np.float64);b=b.astype(np.float64)
    if transpose_x1:a=a.swapaxes(1,2)
    if transpose_x2:b=b.swapaxes(1,2)
    if a.shape[0]!=b.shape[0] or a.shape[2]!=b.shape[1]:raise ValueError('batch/K mismatch')
    if not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('nonfinite input')
    return np.matmul(a,b).max(axis=2).sum(axis=1,dtype=np.float64).astype(np.float32)

def assess(actual,reference,repeat=None):
    a=np.asarray(actual);r=np.asarray(reference)
    if a.shape!=r.shape or a.dtype!=np.float32 or r.dtype!=np.float32:
        raise ValueError('exact output shape and FP32 dtype required')
    finite=bool(np.isfinite(a).all() and np.isfinite(r).all())
    if not finite:return dict(finite=False,strict=False,combined=False,bitwise_repeat=None)
    absolute=np.abs(a.astype(np.float64)-r.astype(np.float64))
    relative=np.divide(absolute,np.abs(r.astype(np.float64)),out=np.full(a.shape,np.inf),where=r!=0)
    relative[(r==0)&(absolute==0)]=0
    bits=None
    if repeat is not None:
        q=np.asarray(repeat)
        bits=bool(q.dtype==np.float32 and q.shape==a.shape and np.array_equal(a.view(np.uint32),q.view(np.uint32)))
    return dict(finite=True,strict=bool(np.all(absolute<1e-4)&np.all(relative<1e-4)),combined=bool(np.all(absolute<=1e-4+1e-4*np.abs(r))),max_abs=float(absolute.max(initial=0)),max_rel=float(relative.max(initial=0)),bitwise_repeat=bits)
