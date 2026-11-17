#!/usr/bin/env python3
"""Optimised contour of dark shapes using potrace (bundled with Inkscape).

Use for organic shapes (trees, figures, hand lettering) or as a first
measurement pass — NOT as the final geometry for buildings/structures.

CLI:
  python contour.py ref.png --box 600 400 700 520 [--threshold 135] [--tolerance 0.3] \
      [--alphamax 1.0] [--speckle 2] > shape.d
As a module:
  from contour import trace; d, segments, subpaths = trace(bool_mask, offset=(x0, y0))

Higher --tolerance/--alphamax = fewer, smoother curves. Lower alphamax keeps
more corners. Requires numpy pillow opencv-python-headless and libpotrace
(found inside Inkscape.app or via --lib / POTRACE_LIB).
"""
import argparse
import ctypes as C
import os
import sys
from pathlib import Path
import numpy as np

CANDIDATES = [
    '/Applications/Inkscape.app/Contents/Resources/lib/libpotrace.0.dylib',
    '/opt/homebrew/lib/libpotrace.dylib', '/usr/local/lib/libpotrace.dylib',
    '/usr/lib/x86_64-linux-gnu/libpotrace.so.0', '/usr/lib/libpotrace.so.0',
]


class Bitmap(C.Structure):
    _fields_ = [('w', C.c_int), ('h', C.c_int), ('dy', C.c_int), ('map', C.POINTER(C.c_ulong))]


class DPoint(C.Structure):
    _fields_ = [('x', C.c_double), ('y', C.c_double)]


class Curve(C.Structure):
    _fields_ = [('n', C.c_int), ('tag', C.POINTER(C.c_int)), ('c', C.POINTER(DPoint*3))]


class PPath(C.Structure):
    pass


PPath._fields_ = [('area', C.c_int), ('sign', C.c_int), ('curve', Curve), ('next', C.POINTER(PPath)),
                  ('childlist', C.POINTER(PPath)), ('sibling', C.POINTER(PPath)), ('priv', C.c_void_p)]


class State(C.Structure):
    _fields_ = [('status', C.c_int), ('plist', C.POINTER(PPath)), ('priv', C.c_void_p)]


class Progress(C.Structure):
    _fields_ = [('callback', C.c_void_p), ('data', C.c_void_p), ('min', C.c_double),
                ('max', C.c_double), ('epsilon', C.c_double)]


class Params(C.Structure):
    _fields_ = [('turdsize', C.c_int), ('turnpolicy', C.c_int), ('alphamax', C.c_double),
                ('opticurve', C.c_int), ('opttolerance', C.c_double), ('progress', Progress)]


def _lib(path=None):
    for p in [path, os.environ.get('POTRACE_LIB')] + CANDIDATES:
        if p and Path(p).exists():
            lib = C.CDLL(p)
            lib.potrace_param_default.restype = C.POINTER(Params)
            lib.potrace_trace.argtypes = [C.POINTER(Params), C.POINTER(Bitmap)]
            lib.potrace_trace.restype = C.POINTER(State)
            lib.potrace_state_free.argtypes = [C.POINTER(State)]
            lib.potrace_param_free.argtypes = [C.POINTER(Params)]
            return lib
    sys.exit('libpotrace not found; pass --lib or set POTRACE_LIB')


def _f(v):
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def trace(mask, offset=(0, 0), tolerance=0.3, alphamax=1.0, speckle=2, lib=None):
    """Bool mask (True = ink) -> (path data, segment count, subpath count)."""
    lib = lib or _lib()
    mask = np.asarray(mask, bool)
    h, w = mask.shape
    stride = (w + 63)//64
    data = np.zeros((h, stride), np.uint64)
    ys, xs = np.nonzero(mask)
    np.bitwise_or.at(data, (ys, xs//64), np.left_shift(np.uint64(1), (63 - xs % 64).astype(np.uint64)))
    bm = Bitmap(w, h, stride, data.ctypes.data_as(C.POINTER(C.c_ulong)))
    prm = lib.potrace_param_default()
    prm.contents.turdsize, prm.contents.alphamax, prm.contents.opttolerance = speckle, alphamax, tolerance
    st = lib.potrace_trace(prm, C.byref(bm))
    if not st or st.contents.status:
        raise RuntimeError('potrace failed')
    ox, oy = offset
    pt = lambda p: f'{_f(p.x + ox)},{_f(p.y + oy)}'
    out, segs, subs = [], 0, 0
    node = st.contents.plist
    while node:
        cv = node.contents.curve
        if cv.n:
            out.append('M' + pt(cv.c[cv.n - 1][2]))
            for i in range(cv.n):
                a, b, c = cv.c[i]
                if cv.tag[i] == 2:   # POTRACE_CORNER
                    out.append('L' + pt(b) + ' ' + pt(c))
                else:                # POTRACE_CURVETO
                    out.append('C' + pt(a) + ' ' + pt(b) + ' ' + pt(c))
                segs += 1
            out.append('Z'); subs += 1
        node = node.contents.next
    lib.potrace_state_free(st); lib.potrace_param_free(prm)
    return ''.join(out), segs, subs   # use fill-rule="evenodd"


def main():
    from PIL import Image
    import cv2
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('image')
    p.add_argument('--box', type=int, nargs=4, required=True)
    p.add_argument('--threshold', type=int, default=135)
    p.add_argument('--blur', type=float, default=0.5, help='gaussian sigma before thresholding')
    p.add_argument('--tolerance', type=float, default=0.3)
    p.add_argument('--alphamax', type=float, default=1.0)
    p.add_argument('--speckle', type=int, default=2)
    p.add_argument('--lib')
    a = p.parse_args()
    x0, y0, x1, y1 = a.box
    g = np.array(Image.open(a.image).convert('L'))[y0:y1, x0:x1]
    if a.blur:
        g = cv2.GaussianBlur(g, (0, 0), a.blur)
    d, n, k = trace(g < a.threshold, (x0, y0), a.tolerance, a.alphamax, a.speckle, _lib(a.lib))
    print(d)
    print(f'# {n} segments, {k} subpaths (fill-rule evenodd)', file=sys.stderr)


if __name__ == '__main__':
    main()
