"""Shared figure style for every chart and map figure.

Serif type on a white surface, light horizontal grid, boxed hairline
legends. Series charts use one navy + coral pair; maps and diverging bars
use the blue/red ramp so gain/loss reads the same everywhere.
"""
import matplotlib

SURFACE = "#ffffff"
INK, INK2 = "#1b1b1b", "#555555"
GRID = "#e9e9e9"
NAVY, CORAL = "#24435c", "#e8794f"

# diverging ramp shared with the site maps (gain blue / loss red)
RED_ARM = ["#6b1414", "#a11d1d", "#e04234", "#f79b8e"]
NEUTRAL = "#f0efec"
BLUE_ARM = ["#74b3f7", "#2a7ff0", "#0f5ec4", "#093a80"]
NODATA = "#e5e4e0"
GRAY_DEEMPH = "#b5b3ac"


def apply() -> None:
    matplotlib.rcParams.update({
        "font.family": "serif",
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK2,
        "ytick.color": INK2,
    })


def box_legend(leg) -> None:
    leg.get_frame().set_linewidth(0.8)
    leg.get_frame().set_edgecolor("#d9d9d9")
    leg.get_frame().set_facecolor(SURFACE)
