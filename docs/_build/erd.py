"""Entity-relationship primitives: table-style entities and crow's-foot connectors."""
from __future__ import annotations

from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D

from dg import Canvas, INK, GREY, GREY_D, GREY_L, GREY_LL, ORANGE, ORANGE_D, ORANGE_L


class Entity:
    """A relational table drawn as a header plus one row per attribute."""

    def __init__(self, ax, x, y, w, name, attrs, header_fc=ORANGE, header_tc="#FFFFFF",
                 row_h=2.05, hdr_h=3.0, fs=6.6, hdr_fs=8.0, ec=GREY_D, body_fc="#FFFFFF",
                 z=3, note=None, note_fs=6.0):
        """attrs: list of (name, kind) where kind in {'pk','fk','pkfk','','idx'}"""
        self.ax, self.x, self.w, self.name = ax, x, w, name
        n = len(attrs)
        self.h = hdr_h + n * row_h
        self.y = y - self.h          # y is the TOP edge
        self.row_h, self.hdr_h = row_h, hdr_h
        self.rows = {}

        ax.add_patch(FancyBboxPatch(
            (self.x + 0.3, self.y - 0.3), w, self.h,
            boxstyle="round,pad=0,rounding_size=0.5", fc="#00000014", ec="none", zorder=z - 1))
        ax.add_patch(FancyBboxPatch(
            (self.x, self.y), w, self.h, boxstyle="round,pad=0,rounding_size=0.5",
            fc=body_fc, ec=ec, lw=1.1, zorder=z))
        ax.add_patch(Rectangle((self.x, y - hdr_h), w, hdr_h, fc=header_fc, ec="none", zorder=z + 1))
        ax.add_line(Line2D([self.x, self.x + w], [y - hdr_h, y - hdr_h], color=ec, lw=1.0, zorder=z + 2))
        ax.text(self.x + w / 2, y - hdr_h / 2, name, ha="center", va="center",
                fontsize=hdr_fs, color=header_tc, weight="bold", zorder=z + 3)

        for i, (an, kind) in enumerate(attrs):
            ry = y - hdr_h - (i + 1) * row_h
            self.rows[an] = ry + row_h / 2
            if i % 2 == 1:
                ax.add_patch(Rectangle((self.x + 0.06, ry), w - 0.12, row_h,
                                       fc=GREY_LL, ec="none", zorder=z + 1))
            mark = {"pk": "PK", "fk": "FK", "pkfk": "PK,FK", "idx": "U"}.get(kind, "")
            mc = {"pk": ORANGE_D, "fk": "#2F6FB0", "pkfk": "#6A4C93", "idx": GREY_D}.get(kind, GREY)
            ax.text(self.x + 0.9, ry + row_h / 2, mark, ha="left", va="center",
                    fontsize=fs - 0.6, color=mc, weight="bold", zorder=z + 3)
            ax.text(self.x + 5.4, ry + row_h / 2, an, ha="left", va="center",
                    fontsize=fs, color=INK if kind in ("pk", "pkfk") else "#2E2E2E",
                    weight="bold" if kind in ("pk", "pkfk") else "normal", zorder=z + 3)
        if note:
            ax.text(self.x + w / 2, self.y - 1.3, note, ha="center", va="top",
                    fontsize=note_fs, color=GREY_D, style="italic", zorder=z + 3)

    @property
    def top(self): return self.y + self.h
    @property
    def cx(self): return self.x + self.w / 2
    @property
    def cy(self): return self.y + self.h / 2
    @property
    def right(self): return self.x + self.w

    def anchor(self, side, frac=0.5, attr=None):
        if attr and attr in self.rows:
            yy = self.rows[attr]
        else:
            yy = self.y + self.h * frac
        if side == "l":
            return (self.x, yy)
        if side == "r":
            return (self.x + self.w, yy)
        if side == "t":
            return (self.x + self.w * frac, self.y + self.h)
        return (self.x + self.w * frac, self.y)


def _foot(ax, p, direction, color, lw=1.1, size=1.5, z=6):
    """Crow's foot (many) at point p, opening away from `direction`."""
    x, y = p
    dx, dy = direction
    if abs(dx) > abs(dy):                       # horizontal connector
        s = size * (1 if dx > 0 else -1)
        for oy in (-size * 0.95, 0, size * 0.95):
            ax.add_line(Line2D([x, x + s], [y, y + oy], color=color, lw=lw, zorder=z))
    else:
        s = size * (1 if dy > 0 else -1)
        for ox in (-size * 0.95, 0, size * 0.95):
            ax.add_line(Line2D([x, x + ox], [y, y + s], color=color, lw=lw, zorder=z))


def _bar(ax, p, direction, color, lw=1.2, size=1.3, off=1.9, z=6):
    """The 'one' tick — a bar across the connector."""
    x, y = p
    dx, dy = direction
    if abs(dx) > abs(dy):
        xx = x + off * (1 if dx > 0 else -1)
        ax.add_line(Line2D([xx, xx], [y - size, y + size], color=color, lw=lw, zorder=z))
    else:
        yy = y + off * (1 if dy > 0 else -1)
        ax.add_line(Line2D([x - size, x + size], [yy, yy], color=color, lw=lw, zorder=z))


def _circle(ax, p, direction, color, r=0.75, off=3.3, z=6):
    """Optionality 'zero' ring."""
    from matplotlib.patches import Circle
    x, y = p
    dx, dy = direction
    if abs(dx) > abs(dy):
        cx = x + off * (1 if dx > 0 else -1); cy = y
    else:
        cx = x; cy = y + off * (1 if dy > 0 else -1)
    ax.add_patch(Circle((cx, cy), r, fc="#FFFFFF", ec=color, lw=1.0, zorder=z))


def rel(ax, pts, left="one", right="many", color=GREY_D, lw=1.1, label=None,
        fs=6.2, labelat=None, labeldy=1.1, labeldx=0.0, ls="-", z=5,
        left_optional=False, right_optional=False, labelbg="#FFFFFF"):
    """Orthogonal relationship line through waypoints with crow's-foot ends."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.add_line(Line2D(xs, ys, color=color, lw=lw, ls=ls, zorder=z,
                       solid_capstyle="round", solid_joinstyle="round"))

    d0 = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    d1 = (pts[-2][0] - pts[-1][0], pts[-2][1] - pts[-1][1])
    for end, card, d, opt in ((pts[0], left, d0, left_optional),
                              (pts[-1], right, d1, right_optional)):
        if card == "many":
            _foot(ax, end, d, color, lw=lw, z=z + 1)
            if opt:
                _circle(ax, end, d, color, z=z + 1)
            else:
                _bar(ax, end, d, color, lw=lw, off=1.95, z=z + 1)
        else:
            _bar(ax, end, d, color, lw=lw, off=1.2, z=z + 1)
            if opt:
                _circle(ax, end, d, color, off=2.9, z=z + 1)
            else:
                _bar(ax, end, d, color, lw=lw, off=2.5, z=z + 1)
    if label:
        if labelat:
            lx, ly = labelat
        else:
            i = len(pts) // 2
            lx = (pts[i - 1][0] + pts[i][0]) / 2
            ly = (pts[i - 1][1] + pts[i][1]) / 2
        t = ax.text(lx + labeldx, ly + labeldy, label, ha="center", va="center",
                    fontsize=fs, color=color, zorder=z + 2)
        if labelbg:
            t.set_bbox(dict(fc=labelbg, ec="none", pad=1.0))


def erd_key(ax, x, y, fs=6.4):
    """Notation key for the crow's-foot diagrams."""
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x, y - 15.0), 27.0, 15.0,
                                boxstyle="round,pad=0,rounding_size=0.6",
                                fc="#FFFFFF", ec=GREY, lw=0.9, ls="--", zorder=9))
    ax.text(x + 1.4, y - 2.0, "Notation  (crow's foot)", fontsize=fs + 0.8,
            color=INK, weight="bold", ha="left", va="center", zorder=10)
    rows = [
        ("exactly one", "one", False),
        ("zero or one", "one", True),
        ("one or many", "many", False),
        ("zero or many", "many", True),
    ]
    yy = y - 5.2
    for label, card, opt in rows:
        p0 = (x + 2.0, yy)
        p1 = (x + 9.5, yy)
        ax.add_line(Line2D([p0[0], p1[0]], [yy, yy], color=GREY_D, lw=1.1, zorder=10))
        d = (p0[0] - p1[0], 0)
        if card == "many":
            _foot(ax, p1, d, GREY_D, z=11)
            if opt:
                _circle(ax, p1, d, GREY_D, z=11)
            else:
                _bar(ax, p1, d, GREY_D, off=1.95, z=11)
        else:
            _bar(ax, p1, d, GREY_D, off=1.2, z=11)
            if opt:
                _circle(ax, p1, d, GREY_D, off=2.9, z=11)
            else:
                _bar(ax, p1, d, GREY_D, off=2.5, z=11)
        ax.text(x + 13.2, yy, label, fontsize=fs, color=INK, ha="left", va="center", zorder=10)
        yy -= 2.9
    ax.text(x + 1.4, y - 16.0, "", fontsize=fs)
