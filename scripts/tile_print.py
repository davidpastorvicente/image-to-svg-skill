#!/usr/bin/env python3
"""Split a poster PDF into sheets (A4 by default) at 100% scale for a home test print.

Example:
  python tile_print.py poster.pdf                           # A4 portrait, grid chosen automatically
  python tile_print.py poster.pdf --sheet 297 420 --lang es  # A3, Spanish labels
  python tile_print.py poster.pdf --cols 3 --rows 3 -o test.pdf

Layout (assumes the artwork has a white margin of at least ~5 mm, the unprintable
edge of home printers):
  - first column/row sit flush with the sheet's left/top edge and the last ones with
    its right/bottom edge, so the sheet edge IS the poster edge: no cutting there;
  - every other sheet is trimmed on its left and/or top side only and glued OVER the
    previous one, which hides that sheet's blank strip;
  - nothing is printed on the part that stays visible: short corner ticks touch the
    tile edge in the strips that are cut off or covered, a pair of scissors lies along
    each edge to cut, and a short label (row, column, what to cut) sits in a hidden strip.
Print at 100% / "actual size", never "fit to page". Requires: pymupdf
"""
import argparse
import math

import pymupdf as fitz

MM = 72 / 25.4
TEXT = {'en': ('Row {r} · Column {c}', 'No cutting needed', 'Cut along the ', 'left', 'top', ' and '),
        'es': ('Fila {r} · Columna {c}', 'No hay que cortar', 'Cortar por ', 'la izquierda', 'arriba', ' y ')}


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('pdf')
    a.add_argument('-o', '--out')
    a.add_argument('--sheet', type=float, nargs=2, default=(210, 297), metavar=('W_MM', 'H_MM'))
    a.add_argument('--cols', type=int)
    a.add_argument('--rows', type=int)
    a.add_argument('--offset', type=float, default=20, help='tile start on middle sheets, mm (strip that is cut off)')
    a.add_argument('--lang', choices=TEXT, default='en')
    o = a.parse_args()

    src = fitz.open(o.pdf)
    W, H = src[0].rect.width, src[0].rect.height
    PW, PH = o.sheet[0] * MM, o.sheet[1] * MM
    room = lambda n, page: page - (o.offset * MM if n > 2 else 0) - 12 * MM   # space left for a tile
    cols = o.cols or next(n for n in range(1, 20) if W / n <= room(n, PW))
    rows = o.rows or next(n for n in range(1, 20) if H / n <= room(n, PH))
    tw, th = W / cols, H / rows
    assert tw <= PW and th <= PH, 'tiles do not fit on the sheet; add rows/columns'
    place = lambda i, n, page, tile: 0 if i == 0 else (page - tile if i == n - 1 else o.offset * MM)
    head, none, cut, left, top, join = TEXT[o.lang]
    TICK = 6 * MM
    doc = fitz.open()
    for r in range(rows):
        for c in range(cols):
            p = doc.new_page(width=PW, height=PH)
            tx, ty = place(c, cols, PW, tw), place(r, rows, PH, th)
            d = fitz.Rect(tx, ty, tx + tw, ty + th)
            p.show_pdf_page(d, src, 0, clip=fitz.Rect(c * tw, r * th, (c + 1) * tw, (r + 1) * th))

            def ticks(side, scissors):
                for f in (0, 1):
                    if side == 'left':
                        x, y = d.x0, d.y0 + f * th; p.draw_line((x, y), (x - TICK, y), width=.4)
                    elif side == 'top':
                        x, y = d.x0 + f * tw, d.y0; p.draw_line((x, y), (x, y - TICK), width=.4)
                    elif side == 'right':
                        x, y = d.x1, d.y0 + f * th; p.draw_line((x, y), (x + TICK, y), width=.4)
                    else:
                        x, y = d.x0 + f * tw, d.y1; p.draw_line((x, y), (x, y + TICK), width=.4)
                if scissors:   # ZapfDingbats scissors, lying along the edge to cut
                    if side == 'left':
                        p.insert_text((d.x0 - TICK - 1.4 * MM, d.y0 + th / 2 - 2 * MM), '\x22', fontsize=14, fontname='zadb', rotate=270)
                    else:
                        p.insert_text((d.x0 + tw / 2 - 2 * MM, d.y0 - TICK + 1.7 * MM), '\x22', fontsize=14, fontname='zadb')

            if c < cols - 1: ticks('right', False)
            if r < rows - 1: ticks('bottom', False)
            cuts = []
            if c > 0: ticks('left', True); cuts.append(left)
            if r > 0: ticks('top', True); cuts.append(top)
            msg = head.format(r=r + 1, c=c + 1) + '   |   ' + (cut + join.join(cuts) if cuts else none)
            y = ty - 12 * MM if r == rows - 1 and r > 0 else ty + th + 14 * MM   # always in a hidden strip
            p.insert_text((12 * MM, y), msg, fontsize=9, fontname='helv')
    out = o.out or o.pdf.rsplit('.', 1)[0] + f'-tiles-{cols}x{rows}.pdf'
    doc.save(out)
    print(f'{cols} x {rows} sheets of {o.sheet[0]:g} x {o.sheet[1]:g} mm, tile {tw / MM:.1f} x {th / MM:.1f} mm -> {out}')


if __name__ == '__main__':
    main()
