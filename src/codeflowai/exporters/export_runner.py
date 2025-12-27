from __future__ import annotations
from pathlib import Path
import os
import sys
import shutil
import subprocess

from .svg_exporter import export_svg_from_mmd
from .pdf_exporter import export_a4_pdf


def _resolve_npx() -> str:
    """
    Resolve npx path robustly on Windows/PowerShell. Prefer PATH; fallback to default install path.
    """
    npx_path = shutil.which("npx") or r"C:\Program Files\nodejs\npx.CMD"
    if not Path(npx_path).exists():
        print("[error] npx not found in PATH and default fallback path does not exist", file=sys.stderr)
        raise FileNotFoundError("npx not found")
    return npx_path


def _run_mmdc_pdf(mmd_path: Path, out_pdf: Path, scale: float = 1.0, mermaid_config: Path | None = None) -> Path:
    """
    Use @mermaid-js/mermaid-cli to render PDF directly from .mmd.
    Strategy: cwd=out_pdf.parent + filenames (no absolute paths in cmd), shell=False.
    """
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    npx_path = _resolve_npx()

    cmd = [
        npx_path, "-y", "@mermaid-js/mermaid-cli",
        "-i", mmd_path.name,
        "-o", out_pdf.name,
        "--scale", str(scale),
    ]
    if mermaid_config:
        cmd += ["--configFile", str(mermaid_config)]

    print("[debug raw cmd]", cmd)
    subprocess.run(cmd, check=True, cwd=out_pdf.parent, shell=False)
    print(f"[ok] PDF written → {out_pdf}")
    return out_pdf


def _parse_margin_mm_from_env(env_key: str = "CODEFLOWAI_PDF_MARGIN_MM") -> float | None:
    """
    Read margin (mm) from environment. Clamp to [0, 40]. Return None if not set or invalid.
    """
    raw = os.getenv(env_key)
    if not raw:
        return None
    try:
        mm = float(raw)
    except ValueError:
        print(f"[warn] {env_key} is not a float: {raw!r}; ignore normalization", file=sys.stderr)
        return None
    mm = max(0.0, min(40.0, mm))
    return mm


def export_artifacts(
    out_base: Path,
    formats: list[str],
    scale: float = 1.0,
    mermaid_config: Path | None = None,
    *_, **__
) -> None:
    """
    Orchestrate exports based on already-written out_base.mmd.
    - SVG: uses svg_exporter (npx + cwd+filenames)
    - PDF: uses mmdc to produce PDF; optionally A4-normalize if CODEFLOWAI_PDF_MARGIN_MM is set
    Notes:
      * No shell=True, no absolute paths in CLI args (we rely on cwd).
      * Public API unchanged (name and semantics).
    """
    out_base = Path(out_base)
    mmd_path = out_base.with_suffix(".mmd")
    if not mmd_path.exists():
        raise FileNotFoundError(f".mmd not found: {mmd_path}")

    # Ensure parent dir exists (CLI should already do this; keep defensive)
    out_base.parent.mkdir(parents=True, exist_ok=True)

    want_svg = "svg" in formats
    want_pdf = "pdf" in formats

    # --- SVG stage ---
    if want_svg:
        out_svg = out_base.with_suffix(".svg")
        print("[stage] 1/2 svg …" if want_pdf else "[stage] svg …")
        export_svg_from_mmd(mmd_path=mmd_path, out_svg=out_svg, scale=scale, mermaid_config=mermaid_config)
        print("[stage] 1/2 svg done" if want_pdf else "[stage] svg done")

    # --- PDF stage ---
    if want_pdf:
        print("[stage] 2/2 pdf …" if want_svg else "[stage] pdf …")

        out_pdf = out_base.with_suffix(".pdf")
        margin_mm = _parse_margin_mm_from_env()

        # 如果设置了 A4 边距，直接调用 export_a4_pdf（单次渲染）
        if margin_mm is not None:
            export_a4_pdf(in_pdf=out_pdf, out_pdf=out_pdf, margin_mm=margin_mm, mermaid_config=mermaid_config)
        else:
            # 否则执行普通 mmdc PDF 渲染
            _run_mmdc_pdf(mmd_path=mmd_path, out_pdf=out_pdf, scale=scale, mermaid_config=mermaid_config)

        print("[stage] 2/2 pdf done" if want_svg else "[stage] pdf done")

