"""Chart engine for AutoAtlas Pro.

Dual-backend chart rendering:
  - matplotlib (always available in QGIS) for reliable fallback
  - plotly (optional) for premium high-impact visuals

All public methods return PNG bytes at configurable DPI.
"""

from __future__ import annotations

import io
from typing import List, Optional, Tuple

from .models import FeatureContext, FieldStats, RankEntry

# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

_HAS_PLOTLY = False
try:
    import plotly.graph_objects as go
    import plotly.io as pio

    _HAS_PLOTLY = True
except ImportError:
    pass

import matplotlib

matplotlib.use("Agg")  # headless backend — must be set before pyplot
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


# ======================================================================
# Color palette (premium dark theme)
# ======================================================================

_PALETTE = {
    "bg": "#1a1a2e",
    "surface": "#16213e",
    "primary": "#0f3460",
    "accent": "#e94560",
    "text": "#eaeaea",
    "text_muted": "#8d8d9b",
    "highlight": "#e94560",
    "grid": "#2a2a4a",
    "positive": "#2ecc71",
    "negative": "#e74c3c",
    "bar_default": "#3498db",
    "gradient_start": "#667eea",
    "gradient_end": "#764ba2",
}


_PALETTE_LIGHT = {
    "bg": "#ffffff",
    "surface": "#f8f9fa",
    "primary": "#2c3e50",
    "accent": "#e74c3c",  # Red accent
    "text": "#2c3e50",
    "text_muted": "#7f8c8d",
    "highlight": "#e74c3c",
    "grid": "#ecf0f1",
    "positive": "#27ae60",
    "negative": "#c0392b",
    "bar_default": "#3498db",  # Blue
    "gradient_start": "#3498db",
    "gradient_end": "#2980b9",
}

def _apply_style(fig: plt.Figure, ax: plt.Axes, dark: bool = False) -> None:
    """Apply theme to a matplotlib figure."""
    palette = _PALETTE if dark else _PALETTE_LIGHT
    
    fig.patch.set_facecolor(palette["bg"])
    ax.set_facecolor(palette["surface"])
    
    # Spines
    for spine in ax.spines.values():
        spine.set_color(palette["grid"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    # Ticks and labels
    ax.tick_params(colors=palette["text_muted"], labelsize=9)
    ax.xaxis.label.set_color(palette["text"])
    ax.yaxis.label.set_color(palette["text"])
    ax.title.set_color(palette["text"])


def _apply_dark_style(fig: plt.Figure, ax: plt.Axes) -> None:
    """Deprecated: Use _apply_style(..., dark=True)."""
    _apply_style(fig, ax, dark=True)


def _fig_to_bytes(fig: plt.Figure, dpi: int = 150) -> bytes:
    """Render a matplotlib figure to PNG bytes."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ======================================================================
# Chart Engine
# ======================================================================


class ChartEngine:
    """Generates statistical charts for territorial reports.

    Uses plotly when available for premium quality, falls back to matplotlib.
    """

    def __init__(self, dpi: int = 150, use_plotly: bool = True, dark_theme: bool = False) -> None:
        self.dpi = dpi
        self.use_plotly = use_plotly and _HAS_PLOTLY
        self.dark_theme = dark_theme

    # ------------------------------------------------------------------
    # Distribution chart
    # ------------------------------------------------------------------

    def render_distribution(
        self,
        stats: FieldStats,
        highlight_value: Optional[float] = None,
        title: str = "",
    ) -> bytes:
        """Render a distribution histogram with optional highlighted value.

        Args:
            stats: Precomputed field statistics with histogram data.
            highlight_value: Value to highlight with a vertical line.
            title: Chart title.

        Returns:
            PNG bytes.
        """
        if self.use_plotly:
            return self._distribution_plotly(stats, highlight_value, title)
        return self._distribution_mpl(stats, highlight_value, title)

    def _distribution_mpl(
        self, stats: FieldStats, highlight: Optional[float], title: str
    ) -> bytes:
        palette = _PALETTE if self.dark_theme else _PALETTE_LIGHT
        fig, ax = plt.subplots(figsize=(6, 3.5))
        _apply_style(fig, ax, self.dark_theme)

        if stats.histogram_bins and stats.histogram_counts:
            bin_edges = np.array(stats.histogram_bins)
            counts = np.array(stats.histogram_counts)
            widths = np.diff(bin_edges)
            centers = bin_edges[:-1] + widths / 2

            colors = [palette["bar_default"]] * len(counts)

            # Highlight the bin containing highlight_value
            if highlight is not None:
                for i, (lo, hi) in enumerate(zip(bin_edges[:-1], bin_edges[1:])):
                    if lo <= highlight <= hi:
                        colors[i] = palette["highlight"]
                        break

            ax.bar(centers, counts, width=widths * 0.85, color=colors, edgecolor="none")

            if highlight is not None:
                ax.axvline(
                    x=highlight,
                    color=palette["accent"],
                    linewidth=2,
                    linestyle="--",
                    alpha=0.9,
                )
                ax.annotate(
                    f"{highlight:,.1f}",
                    xy=(highlight, max(counts) * 0.85),
                    fontsize=10,
                    fontweight="bold",
                    color=palette["accent"],
                    ha="center",
                )

        ax.set_title(title or stats.field_name, fontsize=13, fontweight="bold", pad=12)
        ax.set_xlabel("Value", fontsize=10)
        ax.set_ylabel("Frequency", fontsize=10)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

        fig.tight_layout()
        return _fig_to_bytes(fig, self.dpi)

    def _distribution_plotly(
        self, stats: FieldStats, highlight: Optional[float], title: str
    ) -> bytes:
        if not stats.histogram_bins or not stats.histogram_counts:
            return self._distribution_mpl(stats, highlight, title)

        bin_edges = stats.histogram_bins
        counts = stats.histogram_counts
        centers = [(a + b) / 2 for a, b in zip(bin_edges[:-1], bin_edges[1:])]

        colors = []
        for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
            if highlight is not None and lo <= highlight <= hi:
                colors.append(_PALETTE["highlight"])
            else:
                colors.append(_PALETTE["bar_default"])

        fig = go.Figure(
            go.Bar(x=centers, y=counts, marker_color=colors, width=[b - a for a, b in zip(bin_edges[:-1], bin_edges[1:])])
        )

        if highlight is not None:
            fig.add_vline(x=highlight, line_dash="dash", line_color=_PALETTE["accent"], line_width=2)
            fig.add_annotation(x=highlight, y=max(counts) * 0.9, text=f"{highlight:,.1f}", showarrow=False, font=dict(color=_PALETTE["accent"], size=14, family="Arial Black"))

        fig.update_layout(
            template="plotly_dark",
            title=dict(text=title or stats.field_name, font=dict(size=16)),
            paper_bgcolor=_PALETTE["bg"],
            plot_bgcolor=_PALETTE["surface"],
            margin=dict(l=50, r=20, t=50, b=40),
            height=280,
            width=480,
        )

        return fig.to_image(format="png", scale=2, engine="kaleido")

    # ------------------------------------------------------------------
    # Ranking chart (lollipop)
    # ------------------------------------------------------------------

    def render_ranking(
        self,
        ranking: List[RankEntry],
        highlight_id: object = None,
        max_items: int = 30,
        title: str = "",
    ) -> bytes:
        """Render a horizontal lollipop ranking chart.

        Args:
            ranking: Sorted list of RankEntry.
            highlight_id: Feature ID to visually highlight.
            max_items: Max number of items to show.
            title: Chart title.

        Returns:
            PNG bytes.
        """
        if self.use_plotly:
            return self._ranking_plotly(ranking, highlight_id, max_items, title)
        return self._ranking_mpl(ranking, highlight_id, max_items, title)

    def _ranking_mpl(
        self, ranking: List[RankEntry], highlight_id: object, max_items: int, title: str
    ) -> bytes:
        palette = _PALETTE if self.dark_theme else _PALETTE_LIGHT
        items = ranking[:max_items]
        items.reverse()  # bottom-to-top for horizontal

        names = [r.name for r in items]
        values = [r.value for r in items]
        colors = [
            palette["highlight"] if r.feature_id == highlight_id else palette["bar_default"]
            for r in items
        ]
        sizes = [
            80 if r.feature_id == highlight_id else 40 for r in items
        ]

        fig_height = max(4, len(items) * 0.35)
        fig, ax = plt.subplots(figsize=(7, fig_height))
        _apply_style(fig, ax, self.dark_theme)

        y_pos = range(len(items))

        # Lollipop lines
        for i, (y, v) in enumerate(zip(y_pos, values)):
            ax.plot(
                [0, v], [y, y],
                color=colors[i], linewidth=1.5, alpha=0.6,
            )

        # Lollipop dots
        ax.scatter(values, y_pos, c=colors, s=sizes, zorder=3, edgecolors="none")

        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(names, fontsize=8)
        ax.set_title(title or "Ranking", fontsize=13, fontweight="bold", pad=12)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
        ax.grid(axis="x", color=palette["grid"], linewidth=0.5, alpha=0.5)

        fig.tight_layout()
        return _fig_to_bytes(fig, self.dpi)

    def _ranking_plotly(
        self, ranking: List[RankEntry], highlight_id: object, max_items: int, title: str
    ) -> bytes:
        items = ranking[:max_items]
        items.reverse()

        names = [r.name for r in items]
        values = [r.value for r in items]
        colors = [
            _PALETTE["highlight"] if r.feature_id == highlight_id else _PALETTE["bar_default"]
            for r in items
        ]

        fig = go.Figure(
            go.Scatter(
                x=values, y=names, mode="markers+text",
                marker=dict(size=[16 if r.feature_id == highlight_id else 10 for r in items], color=colors),
                text=[f"{v:,.0f}" if r.feature_id == highlight_id else "" for r, v in zip(items, values)],
                textposition="middle right",
                textfont=dict(color=_PALETTE["accent"], size=11),
            )
        )

        # Lollipop stems
        for i, (name, val) in enumerate(zip(names, values)):
            fig.add_shape(
                type="line", x0=0, x1=val, y0=name, y1=name,
                line=dict(color=colors[i], width=1.5),
            )

        fig.update_layout(
            template="plotly_dark",
            title=dict(text=title or "Ranking", font=dict(size=16)),
            paper_bgcolor=_PALETTE["bg"],
            plot_bgcolor=_PALETTE["surface"],
            margin=dict(l=120, r=40, t=50, b=30),
            height=max(300, len(items) * 28),
            width=560,
        )

        return fig.to_image(format="png", scale=2, engine="kaleido")

    # ------------------------------------------------------------------
    # Waffle / Donut chart
    # ------------------------------------------------------------------

    def render_waffle(
        self,
        value: float,
        total: float,
        label: str = "",
        title: str = "",
    ) -> bytes:
        """Render a donut proportion chart.

        Args:
            value: The part value.
            total: The whole value.
            label: Center label text.
            title: Chart title.

        Returns:
            PNG bytes.
        """
        return self._waffle_mpl(value, total, label, title)

    def _waffle_mpl(
        self, value: float, total: float, label: str, title: str
    ) -> bytes:
        palette = _PALETTE if self.dark_theme else _PALETTE_LIGHT
        pct = (value / total * 100) if total > 0 else 0
        remainder = 100 - pct

        fig, ax = plt.subplots(figsize=(3.5, 3.5))
        fig.patch.set_facecolor(palette["bg"])

        wedges, _ = ax.pie(
            [pct, remainder],
            colors=[palette["accent"], palette["surface"]],
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.3, edgecolor=palette["bg"], linewidth=2),
        )

        # Center text
        ax.text(
            0, 0.05,
            f"{pct:.1f}%",
            ha="center", va="center",
            fontsize=22, fontweight="bold",
            color=palette["text"],
        )
        if label:
            ax.text(
                0, -0.18,
                label,
                ha="center", va="center",
                fontsize=9,
                color=palette["text_muted"],
            )

        if title:
            ax.set_title(title, fontsize=12, fontweight="bold", color=palette["text"], pad=16)

        fig.tight_layout()
        return _fig_to_bytes(fig, self.dpi)

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------

    def render_summary_table(
        self,
        context: FeatureContext,
        stats: FieldStats,
        title: str = "",
    ) -> bytes:
        """Render a styled summary table as an image.

        Args:
            context: Feature context with rank, percentile, deviation, etc.
            stats: Aggregated field stats for comparison.
            title: Table title.

        Returns:
            PNG bytes.
        """
        return self._summary_mpl(context, stats, title)

    def _summary_mpl(
        self, ctx: FeatureContext, stats: FieldStats, title: str
    ) -> bytes:
        palette = _PALETTE if self.dark_theme else _PALETTE_LIGHT
        fig, ax = plt.subplots(figsize=(5, 3))
        fig.patch.set_facecolor(palette["bg"])
        ax.set_facecolor(palette["bg"])
        ax.axis("off")

        rows = [
            ["Value", f"{ctx.value:,.2f}"],
            ["Rank", f"{ctx.rank} / {ctx.total_features}"],
            ["Percentile", f"P{ctx.percentile:.0f}"],
            ["Mean", f"{stats.mean:,.2f}"],
            ["Std Dev", f"±{stats.std:,.2f}"],
            ["Deviation", f"{ctx.deviation_from_mean:+.2f}σ"],
            ["Min", f"{stats.min_val:,.2f}"],
            ["Max", f"{stats.max_val:,.2f}"],
        ]

        table = ax.table(
            cellText=rows,
            colLabels=["Metric", ctx.name],
            loc="center",
            cellLoc="center",
        )

        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.6)

        # Style cells
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor(palette["grid"])
            if row == 0:  # header
                cell.set_facecolor(palette["primary"])
                cell.set_text_props(color="white", fontweight="bold")
            else:
                cell.set_facecolor(palette["surface"])
                cell.set_text_props(color=palette["text"])

        if title:
            ax.set_title(
                title, fontsize=13, fontweight="bold",
                color=palette["text"], pad=20,
            )

        fig.tight_layout()
        return _fig_to_bytes(fig, self.dpi)
