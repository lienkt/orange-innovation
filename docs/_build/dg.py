"""Diagram primitives for the Orange Innovation Radar documentation set.

Everything is drawn on a 0..100 x 0..100 canvas so layouts are declarative and
comparable across figures. Boxes carry an optional subtitle; connectors route
orthogonally through explicit waypoints because auto-routing overlaps labels.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch, Circle, Polygon, Ellipse
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe

plt.rcParams["font.family"] = "DejaVu Sans"

# -- palette ---------------------------------------------------------------
ORANGE   = "#FF7900"   # Orange brand, used for the product itself
ORANGE_D = "#A83E00"
ORANGE_L = "#FFEEDD"
INK      = "#141414"
GREY_D   = "#4A4A4A"
GREY     = "#9A9A9A"
GREY_L   = "#EDEDED"
GREY_LL  = "#F7F7F7"
BLUE     = "#2F6FB0"   # external / upstream
BLUE_L   = "#E2EDF7"
GREEN    = "#2E7D5B"   # computed / trusted
GREEN_L  = "#DDEFE7"
PURPLE   = "#6A4C93"   # people / curation
PURPLE_L = "#EBE3F4"
RED      = "#A82820"   # guards, risk
RED_L    = "#F8E2E0"
TEAL     = "#1F7A85"
TEAL_L   = "#DDF0F2"
GOLD     = "#8A6D1F"
GOLD_L   = "#F6EED6"


class Canvas:
    def __init__(self, w=11.0, h=7.0, dpi=200, bg="#FFFFFF"):
        self.fig, self.ax = plt.subplots(figsize=(w, h), dpi=dpi)
        self.fig.patch.set_facecolor(bg)
        self.ax.set_facecolor(bg)
        self.ax.set_xlim(0, 100)
        self.ax.set_ylim(0, 100)
        self.ax.set_aspect("auto")
        self.ax.axis("off")
        self.fig.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.005)

    # -- containers --------------------------------------------------------
    def zone(self, x, y, w, h, label=None, fc=GREY_LL, ec=GREY, ls="--", lw=1.0,
             fs=8.5, tc=GREY_D, align="left", pad=1.4, z=1, alpha=1.0, radius=0.9):
        self.ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
            fc=fc, ec=ec, lw=lw, ls=ls, zorder=z, alpha=alpha))
        if label:
            tx = x + pad if align == "left" else x + w / 2
            self.ax.text(tx, y + h - pad, label, ha=align, va="top",
                         fontsize=fs, color=tc, weight="bold", zorder=z + 1)
        return (x, y, w, h)

    # -- boxes -------------------------------------------------------------
    def box(self, x, y, w, h, title, sub=None, fc="#FFFFFF", ec=INK, tc=INK,
            lw=1.2, fs=9.0, subfs=7.4, subc=GREY_D, z=3, radius=0.8, bold=True,
            shadow=False, ls="-", align="center"):
        if shadow:
            self.ax.add_patch(FancyBboxPatch(
                (x + 0.35, y - 0.35), w, h,
                boxstyle=f"round,pad=0,rounding_size={radius}",
                fc="#00000018", ec="none", zorder=z - 1))
        self.ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
            fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))
        cx = x + w / 2 if align == "center" else x + 1.2
        ha = "center" if align == "center" else "left"
        if sub:
            self.ax.text(cx, y + h * 0.62, title, ha=ha, va="center", fontsize=fs,
                         color=tc, weight="bold" if bold else "normal", zorder=z + 1)
            self.ax.text(cx, y + h * 0.28, sub, ha=ha, va="center", fontsize=subfs,
                         color=subc, zorder=z + 1, linespacing=1.25)
        else:
            self.ax.text(cx, y + h / 2, title, ha=ha, va="center", fontsize=fs,
                         color=tc, weight="bold" if bold else "normal",
                         zorder=z + 1, linespacing=1.3)
        return Node(x, y, w, h)

    def chip(self, x, y, w, h, text, fc=GREY_L, ec="none", tc=INK, fs=7.2, z=4):
        self.ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={h/2}",
            fc=fc, ec=ec, lw=0.8, zorder=z))
        self.ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                     fontsize=fs, color=tc, weight="bold", zorder=z + 1)
        return Node(x, y, w, h)

    def cylinder(self, x, y, w, h, title, sub=None, fc=GREEN_L, ec=GREEN, tc=INK,
                 fs=9.0, subfs=7.2, z=3):
        er = h * 0.13
        self.ax.add_patch(Rectangle((x, y + er), w, h - 2 * er, fc=fc, ec="none", zorder=z))
        self.ax.add_patch(Ellipse((x + w / 2, y + er), w, 2 * er, fc=fc, ec=ec, lw=1.2, zorder=z))
        self.ax.add_patch(Ellipse((x + w / 2, y + h - er), w, 2 * er, fc=fc, ec=ec, lw=1.2, zorder=z + 1))
        self.ax.add_line(Line2D([x, x], [y + er, y + h - er], color=ec, lw=1.2, zorder=z + 1))
        self.ax.add_line(Line2D([x + w, x + w], [y + er, y + h - er], color=ec, lw=1.2, zorder=z + 1))
        yy = y + h * 0.60 if sub else y + h * 0.48
        self.ax.text(x + w / 2, yy, title, ha="center", va="center", fontsize=fs,
                     color=tc, weight="bold", zorder=z + 2)
        if sub:
            self.ax.text(x + w / 2, y + h * 0.34, sub, ha="center", va="center",
                         fontsize=subfs, color=GREY_D, zorder=z + 2)
        return Node(x, y, w, h)

    def actor(self, cx, cy, label, sub=None, color=PURPLE, fs=8.4, scale=1.0):
        r = 1.5 * scale
        self.ax.add_patch(Circle((cx, cy + 3.2 * scale), r, fc="#FFFFFF", ec=color, lw=1.4, zorder=4))
        self.ax.add_line(Line2D([cx, cx], [cy + 1.6 * scale, cy - 1.6 * scale], color=color, lw=1.4, zorder=4))
        self.ax.add_line(Line2D([cx - 2.2 * scale, cx + 2.2 * scale], [cy + 0.6 * scale, cy + 0.6 * scale],
                                color=color, lw=1.4, zorder=4))
        self.ax.add_line(Line2D([cx, cx - 1.8 * scale], [cy - 1.6 * scale, cy - 4.2 * scale], color=color, lw=1.4, zorder=4))
        self.ax.add_line(Line2D([cx, cx + 1.8 * scale], [cy - 1.6 * scale, cy - 4.2 * scale], color=color, lw=1.4, zorder=4))
        self.ax.text(cx, cy - 6.0 * scale, label, ha="center", va="top", fontsize=fs,
                     color=INK, weight="bold", zorder=4)
        if sub:
            self.ax.text(cx, cy - 8.4 * scale, sub, ha="center", va="top", fontsize=fs - 1.4,
                         color=GREY_D, zorder=4)

    # -- connectors --------------------------------------------------------
    def arrow(self, p0, p1, color=GREY_D, lw=1.3, label=None, fs=7.2, lc=None,
              style="-|>", ls="-", z=5, rad=0.0, labelpos=0.5, dx=0.0, dy=0.9,
              labelbg="#FFFFFF"):
        self.ax.add_patch(FancyArrowPatch(
            p0, p1, arrowstyle=style, mutation_scale=11, color=color, lw=lw,
            linestyle=ls, zorder=z, shrinkA=0, shrinkB=0,
            connectionstyle=f"arc3,rad={rad}"))
        if label:
            mx = p0[0] + (p1[0] - p0[0]) * labelpos + dx
            my = p0[1] + (p1[1] - p0[1]) * labelpos + dy
            t = self.ax.text(mx, my, label, ha="center", va="center", fontsize=fs,
                             color=lc or color, zorder=z + 1)
            if labelbg:
                t.set_bbox(dict(fc=labelbg, ec="none", pad=1.0))
        return self

    def path(self, pts, color=GREY_D, lw=1.3, label=None, fs=7.2, lc=None,
             head=True, ls="-", z=5, labelat=None, labeldy=1.0, labeldx=0.0,
             labelbg="#FFFFFF"):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        self.ax.add_line(Line2D(xs, ys, color=color, lw=lw, ls=ls, zorder=z,
                                solid_capstyle="round", solid_joinstyle="round"))
        if head:
            self.ax.add_patch(FancyArrowPatch(
                pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=11, color=color,
                lw=lw, zorder=z, shrinkA=0, shrinkB=0))
        if label:
            ax_, ay_ = labelat if labelat else (
                (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2,
                (ys[len(ys) // 2 - 1] + ys[len(ys) // 2]) / 2)
            t = self.ax.text(ax_ + labeldx, ay_ + labeldy, label, ha="center",
                             va="center", fontsize=fs, color=lc or color, zorder=z + 1)
            if labelbg:
                t.set_bbox(dict(fc=labelbg, ec="none", pad=1.0))
        return self

    def text(self, x, y, s, fs=8.0, color=INK, ha="left", va="center", weight="normal",
             z=8, style="normal", bg=None, ls_=1.35):
        t = self.ax.text(x, y, s, fontsize=fs, color=color, ha=ha, va=va,
                         weight=weight, zorder=z, style=style, linespacing=ls_)
        if bg:
            t.set_bbox(dict(fc=bg, ec="none", pad=2.0))
        return t

    def title(self, s, sub=None):
        self.ax.text(0.5, 99.0, s, fontsize=12.5, color=INK, ha="left", va="top", weight="bold")
        if sub:
            self.ax.text(0.5, 94.6, sub, fontsize=8.6, color=GREY_D, ha="left", va="top")

    def rule(self, y, x0=0.5, x1=99.5, color=GREY_L, lw=1.0):
        self.ax.add_line(Line2D([x0, x1], [y, y], color=color, lw=lw, zorder=1))

    def legend(self, x, y, items, fs=7.4, gap=3.4, swatch=2.2, title=None):
        yy = y
        if title:
            self.ax.text(x, yy, title, fontsize=fs + 0.4, color=GREY_D, weight="bold",
                         ha="left", va="center", zorder=8)
            yy -= gap
        for color, label in items:
            self.ax.add_patch(FancyBboxPatch(
                (x, yy - swatch / 2), swatch, swatch,
                boxstyle="round,pad=0,rounding_size=0.35",
                fc=color, ec=GREY_D, lw=0.7, zorder=8))
            self.ax.text(x + swatch + 1.2, yy, label, fontsize=fs, color=INK,
                         ha="left", va="center", zorder=8)
            yy -= gap
        return yy

    def save(self, path):
        self.fig.savefig(path, dpi=self.fig.dpi, facecolor=self.fig.get_facecolor(),
                         bbox_inches="tight", pad_inches=0.06)
        plt.close(self.fig)
        print("wrote", path)


class Node:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def cx(self): return self.x + self.w / 2

    @property
    def cy(self): return self.y + self.h / 2

    @property
    def top(self): return (self.cx, self.y + self.h)

    @property
    def bottom(self): return (self.cx, self.y)

    @property
    def left(self): return (self.x, self.cy)

    @property
    def right(self): return (self.x + self.w, self.cy)

    def t(self, f=0.5): return (self.x + self.w * f, self.y + self.h)
    def b(self, f=0.5): return (self.x + self.w * f, self.y)
    def l(self, f=0.5): return (self.x, self.y + self.h * f)
    def r(self, f=0.5): return (self.x + self.w, self.y + self.h * f)
