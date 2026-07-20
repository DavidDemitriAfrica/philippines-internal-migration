"""Static hero figure: municipal net migration 2020-2024 with the country
rotated 90° counterclockwise (Luzon left, Mindanao right) so the long
archipelago fills a wide frame, plus upright cutaway insets for the three
metros where municipalities are too small to see at national scale.

Output: figures/hero_municipal_sideways.png (+ docs/assets copy)
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Rectangle
from shapely import affinity
from shapely.geometry import box

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
figstyle.apply()
SURFACE, INK, INK2, LINE = figstyle.SURFACE, figstyle.INK, figstyle.INK2, figstyle.GRID
RED_ARM = ["#6b1414", "#a11d1d", "#e04234", "#f79b8e"]
NEUTRAL = "#f0efec"
BLUE_ARM = ["#74b3f7", "#2a7ff0", "#0f5ec4", "#093a80"]
NODATA = "#e5e4e0"
BINS = [-np.inf, -10, -5, -2, -0.5, 0.5, 2, 5, 10, np.inf]
LABELS = ["< −10", "−10 to −5", "−5 to −2", "−2 to −0.5", "about even",
          "0.5 to 2", "2 to 5", "5 to 10", "> 10"]
ORIGIN = (122.0, 12.0)  # rotation origin, roughly mid-archipelago
METROS = [  # (title, lon0, lat0, lon1, lat1)
    ("Metro Manila", 120.85, 14.20, 121.30, 14.95),
    ("Metro Cebu", 123.55, 10.10, 124.15, 10.70),
    ("Metro Davao", 125.10, 6.80, 125.80, 7.50),
]
ISLAND_LABELS = [  # (name, lon, lat) in original coordinates
    ("Luzon", 121.2, 17.5), ("Visayas", 122.3, 10.6),
    ("Mindanao", 125.4, 8.4), ("Palawan", 119.2, 10.3),
]


def rot_pt(x, y):
    """The same 90° CCW rotation the geometries get."""
    return ORIGIN[0] - (y - ORIGIN[1]), ORIGIN[1] + (x - ORIGIN[0])


def main() -> None:
    g = gpd.read_file(ROOT / "docs" / "municipal.geojson")
    # drop empty geometries and Kalayaan (Spratlys, 400 km west — it would
    # shrink the whole frame; the interactive map keeps it, pannable)
    g = g[g.geometry.notna() & ~g.geometry.is_empty
          & (g.psgc10 != "1705321000")].copy()
    cmap = ListedColormap(RED_ARM + [NEUTRAL] + BLUE_ARM)
    norm = BoundaryNorm(BINS, cmap.N)

    fig = plt.figure(figsize=(13.2, 10.4))
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0.005, 0.285, 0.99, 0.635])
    ax.set_facecolor(SURFACE)
    ax.set_axis_off()
    ax.set_aspect("equal")

    rot = g.copy()
    rot["geometry"] = rot.geometry.map(lambda p: affinity.rotate(p, 90, origin=ORIGIN))
    rot.plot(ax=ax, column="rate", cmap=cmap, norm=norm,
             edgecolor="#ffffff", linewidth=0.45,
             missing_kwds={"color": NODATA, "edgecolor": "#ffffff", "linewidth": 0.45})

    # metro locator boxes on the rotated map
    for _, x0, y0, x1, y1 in METROS:
        b = affinity.rotate(box(x0, y0, x1, y1), 90, origin=ORIGIN)
        xs, ys = b.exterior.xy
        ax.plot(xs, ys, color=INK, linewidth=1.5)

    # island-group labels so the unfamiliar orientation still reads
    import matplotlib.patheffects as pe
    for name, lx, ly in ISLAND_LABELS:
        rx, ry = rot_pt(lx, ly)
        ax.text(rx, ry, name, fontsize=13, color=INK2, family="serif",
                style="italic", ha="center", va="center",
                path_effects=[pe.withStroke(linewidth=3, foreground=SURFACE)])

    # north arrow: after a 90° CCW rotation, north points left
    ax.annotate("N", xy=(0.028, 0.92), xytext=(0.075, 0.92),
                xycoords="axes fraction", textcoords="axes fraction",
                fontsize=12, color=INK2, va="center",
                arrowprops=dict(arrowstyle="-|>", color=INK2, linewidth=1.2))

    # upright cutaway insets along the bottom
    for i, (title, x0, y0, x1, y1) in enumerate(METROS):
        axi = fig.add_axes([0.085 + i * 0.31, 0.012, 0.26, 0.235])
        axi.set_facecolor(SURFACE)
        axi.set_aspect("equal")
        g.plot(ax=axi, column="rate", cmap=cmap, norm=norm,
               edgecolor="#ffffff", linewidth=1.0,
               missing_kwds={"color": NODATA, "edgecolor": "#ffffff", "linewidth": 1.0})
        axi.set_xlim(x0, x1); axi.set_ylim(y0, y1)
        axi.set_xticks([]); axi.set_yticks([])
        for s in axi.spines.values():
            s.set_color(INK); s.set_linewidth(1)
        axi.set_title(title, fontsize=10.5, color=INK, family="serif", pad=4)

    fig.text(0.012, 0.955, "Where Filipinos moved, 2020–2024",
             fontsize=19, color=INK, family="serif", fontweight=600)
    fig.text(0.012, 0.918,
             "net internal migration for 1,626 cities and municipalities: "
             "blue gained people, red lost them (residual method)",
             fontsize=10.5, color=INK2)

    handles = [Patch(facecolor=c, edgecolor="#d8d7d3", linewidth=0.4, label=l)
               for c, l in zip(RED_ARM + [NEUTRAL] + BLUE_ARM, LABELS)]
    handles.append(Patch(facecolor=NODATA, label="no estimate"))
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.995, 0.94),
               ncol=2, fontsize=8, frameon=False, labelcolor=INK2,
               title="people per 1,000 per year", title_fontsize=9)
    out = ROOT / "figures" / "hero_municipal_sideways.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    import shutil
    shutil.copy(out, ROOT / "docs" / "assets" / "hero_municipal_sideways.png")
    print("wrote", out, f"({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
