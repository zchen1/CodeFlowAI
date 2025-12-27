# -*- coding: utf-8 -*-
"""
DEPRECATED MODULE – DO NOT USE IN THE MAIN PIPELINE.

Why deprecated?
- The modern pipeline centers on: Renderer (structure-only) → single-source style in
  configs/mermaid.config.json → Exporters that call mmdc once (Windows-safe).
- Any post-processing that mutates SVG layout (canvas recentering, padding, etc.)
  can cause divergence between SVG and PDF, and may break arrowheads/text layout.

Safe behavior:
- This legacy shim preserves the public API but performs NO mutation (no-op).
- It prints a concise warning so that accidental use is visible in logs,
  while avoiding runtime crashes in older branches.

Use instead:
- Keep all visual parameters (line width, arrowheads, margins) in
  configs/mermaid.config.json (single source of truth).
- For PDF A4 single-page: use pdf_exporter.export_a4_pdf with --pdfFit.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


def _warn(msg: str) -> None:
    try:
        print(msg, file=sys.stderr)
    except Exception:
        # last-resort: swallow logging issues
        pass


def center_svg_canvas(svg_path: str, canvas: str = "A4", pad: Optional[int] = None) -> None:
    """
    DEPRECATED no-op.

    Parameters (kept for compatibility):
        svg_path: path to the SVG file (string).
        canvas:   ignored (historically "A4"); kept for call compatibility.
        pad:      ignored; kept for call compatibility.

    Behavior:
        - Verifies the file exists.
        - Performs NO mutation to the SVG.
        - Prints a single-line warning to stderr for visibility.

    Rationale:
        - Prevents exporter-layer relayout that could skew arrowheads/text.
        - Ensures legacy callers won't crash while clearly signaling deprecation.
    """
    p = Path(svg_path)
    if not p.exists():
        raise FileNotFoundError(svg_path)

    _warn("[warn] center_svg_canvas is DEPRECATED and now a no-op; "
          "use configs/mermaid.config.json for style and pdf_exporter --pdfFit for A4.")
    return None
