"""EncoLibMG brand assets, drawn on pixel grids (single source of truth).

    python scripts/brand/build.py            → docs/brand/*.svg + docs/brand/preview.png
    python scripts/brand/build.py --final A  → also writes the chosen mark as the app icon

Grids: '#' = lit pixel, '+' = mid pixel (accent tone), '.' = empty.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "brand"

# Solitude palette (omarchy.org) shared with the UI
PALETTE = {
    "bg-deep": "#0c0e10", "bg": "#101315", "surface": "#14181a", "border-strong": "#4b4e55",
    "text": "#cacccc", "text-2": "#a5aeb4", "muted": "#8a8d90", "brand": "#798186",
    "field-dim": "#2a2e30", "field-mid": "#4e5457", "field-lit": "#798186",
    "field-hover": "#a1a7aa", "field-crest": "#cccfd1",
}

MARKS = {
    # A — "Equalizador E": the E's arms are level-meter bars; the middle one is still "sounding"
    "A": [
        "................",
        ".##############.",
        ".##############.",
        ".##.............",
        ".##.............",
        ".##.............",
        ".##########.+.+.",
        ".##########.+.+.",
        ".##.............",
        ".##.............",
        ".##.............",
        ".############...",
        ".############...",
        "................",
        "................",
        "................",
    ],
    # B — "Letra cantada": a karaoke line mid-wipe (sung part lit) and the next line waiting,
    #     inside Omarchy-style corner brackets
    "B": [
        "###..........###",
        "#..............#",
        "#..............#",
        "................",
        "................",
        "..########++++..",
        "..########++++..",
        "................",
        "................",
        "..++++++++++....",
        "..++++++++++....",
        "................",
        "................",
        "#..............#",
        "#..............#",
        "###..........###",
    ],
    # C — "Microfone": solid pixel mic with two grill lines, same corner brackets
    "C": [
        "###..........###",
        "#..............#",
        "#.....####.....#",
        ".....######.....",
        ".....#++++#.....",
        ".....######.....",
        ".....#++++#.....",
        "......####......",
        "....#......#....",
        ".....#....#.....",
        "......####......",
        ".......##.......",
        ".......##.......",
        "#.....####.....#",
        "#..............#",
        "###..........###",
    ],
}

CHOSEN = "B"  # picked by the user: "Letra cantada"

# 5×7 pixel font for the wordmark (and the UI's pixel logo)
FONT = {
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "N": ["#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "G": [".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."],
}


def word_grid(text: str, accent_from: int) -> list[str]:
    """Letters from index `accent_from` on are drawn with '+' (mid tone): ENCOLIB + MG."""
    rows = [""] * 7
    for i, ch in enumerate(text):
        glyph = FONT[ch]
        for r in range(7):
            px = glyph[r].replace("#", "+") if i >= accent_from else glyph[r]
            rows[r] += px + ("." if i < len(text) - 1 else "")
    return rows


def bold(grid: list[str]) -> list[str]:
    """Each font pixel becomes a 2×2 block: strokes two cells thick, like the Omarchy logo."""
    out = []
    for row in grid:
        wide = "".join(c * 2 for c in row)
        out += [wide, wide]
    return out


WORDMARK = bold(word_grid("ENCOLIBMG", accent_from=7))


def svg(grid: list[str], cell: int = 10, gap: int = 1, lit: str = PALETTE["text"], mid: str = PALETTE["field-mid"],
        bg: str | None = None, pad: int = 0) -> str:
    h, w = len(grid), max(len(r) for r in grid)
    W, H = w * cell + pad * 2, h * cell + pad * 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
             f'shape-rendering="crispEdges">']
    if bg:
        parts.append(f'<rect width="{W}" height="{H}" fill="{bg}"/>')
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c in "#+":
                parts.append(f'<rect x="{pad + x * cell}" y="{pad + y * cell}" width="{cell - gap}" '
                             f'height="{cell - gap}" fill="{lit if c == "#" else mid}"/>')
    parts.append("</svg>")
    return "".join(parts)


def png(grid: list[str], path: Path, cell: int = 10, gap: int = 1, bg=PALETTE["bg"], pad: int = 0,
        lit=PALETTE["text"], mid=PALETTE["field-mid"]):
    from PIL import Image, ImageDraw

    h, w = len(grid), max(len(r) for r in grid)
    img = Image.new("RGB", (w * cell + 2 * pad, h * cell + 2 * pad), bg)
    d = ImageDraw.Draw(img)
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c in "#+":
                x0, y0 = pad + x * cell, pad + y * cell
                d.rectangle([x0, y0, x0 + cell - gap - 1, y0 + cell - gap - 1], fill=lit if c == "#" else mid)
    img.save(path)
    return img


def preview(path: Path):
    """One sheet with the 3 marks (big + 32px + 16px) and the wordmark, for review."""
    from PIL import Image

    tiles = []
    for k, g in MARKS.items():
        big = png(g, OUT / f"_tmp_{k}.png", cell=12, gap=1, pad=24)
        m32 = png(g, OUT / f"_tmp_{k}32.png", cell=2, gap=0, pad=0)
        m16 = png(g, OUT / f"_tmp_{k}16.png", cell=1, gap=0, pad=0)
        tiles.append((big, m32, m16))
    word = png(WORDMARK, OUT / "_tmp_word.png", cell=5, gap=1, pad=24)
    W = max(sum(t[0].width for t in tiles) + 40 * 2, word.width)
    H = tiles[0][0].height + 60 + word.height
    sheet = Image.new("RGB", (W, H), PALETTE["bg-deep"])
    x = 0
    for big, m32, m16 in tiles:
        sheet.paste(big, (x, 0))
        sheet.paste(m32, (x + 24, big.height + 8))
        sheet.paste(m16, (x + 24 + 40, big.height + 16))
        x += big.width + 40
    sheet.paste(word, (0, tiles[0][0].height + 60))
    sheet.save(path)
    for p in OUT.glob("_tmp_*.png"):
        p.unlink()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for k, g in MARKS.items():
        (OUT / f"mark-{k}.svg").write_text(svg(g), encoding="utf-8")
    (OUT / "wordmark.svg").write_text(svg(WORDMARK, cell=5), encoding="utf-8")
    (OUT / "grids.json").write_text(json.dumps({"marks": MARKS, "font": FONT, "wordmark": WORDMARK,
                                                "palette": PALETTE}, indent=1), encoding="utf-8")
    preview(OUT / "preview.png")
    print("ok", OUT)


def page():
    """docs/brand/index.html: the identity sheet with live pixel animations."""
    tpl = (Path(__file__).parent / "page.html").read_text(encoding="utf-8")
    data = json.dumps({"marks": MARKS, "wordmark": WORDMARK, "palette": PALETTE, "chosen": CHOSEN})
    (OUT / "index.html").write_text(tpl.replace("__DATA__", data), encoding="utf-8")


if __name__ == "__main__":
    main()
    page()


STATIC = ROOT / "encolibmg" / "webui" / "static" / "brand"


def icon_image(size: int):
    """The chosen mark on a dark tile, drawn natively at `size` (no blurry downscaling)."""
    from PIL import Image, ImageDraw

    grid = MARKS[CHOSEN]
    img = Image.new("RGBA", (size, size), PALETTE["bg"])
    d = ImageDraw.Draw(img)
    if size >= 48:
        pad = round(size * .14)
        cell = (size - 2 * pad) / 16
        gap = 1 if size >= 128 else 0  # below that a 1px gap reads as dots
    else:  # 16 → 1px per cell, 32 → 2px per cell, edge to edge
        pad, cell, gap = 0, size / 16, 0
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c in "#+":
                x0, y0 = pad + x * cell, pad + y * cell
                d.rectangle([round(x0), round(y0), round(x0 + cell) - 1 - gap, round(y0 + cell) - 1 - gap],
                            fill=PALETTE["text"] if c == "#" else PALETTE["brand"])
    return img


def final():
    STATIC.mkdir(parents=True, exist_ok=True)
    (STATIC / "mark.svg").write_text(svg(MARKS[CHOSEN], cell=10, gap=1), encoding="utf-8")
    (STATIC / "wordmark.svg").write_text(svg(WORDMARK, cell=5, gap=1), encoding="utf-8")
    (STATIC / "brand.json").write_text(json.dumps({"mark": MARKS[CHOSEN], "wordmark": WORDMARK, "font": FONT,
                                                   "palette": PALETTE}), encoding="utf-8")
    sizes = [256, 128, 64, 48, 32, 24, 16]
    imgs = [icon_image(s) for s in sizes]
    imgs[0].save(STATIC / "icon.ico", format="ICO", sizes=[(s, s) for s in sizes], append_images=imgs[1:])
    imgs[0].save(STATIC / "icon-256.png")
    icon_image(32).save(STATIC / "favicon.png")
    print("final", CHOSEN, STATIC)


if __name__ == "__main__" and "--final" in sys.argv:
    final()
