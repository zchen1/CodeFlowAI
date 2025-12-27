# -*- coding: utf-8 -*-
"""
DEPRECATED MODULE – DO NOT USE IN THE MAIN PIPELINE.

This exporter is retained ONLY for historical reference and should NOT be called.
The current, supported pipeline is:

  - SVG: codeflowai.exporters.svg_exporter.export_svg_from_mmd
  - PDF: codeflowai.exporters.pdf_exporter.export_a4_pdf  (single pass with --pdfFit)
  - Mermaid config (style, arrows, widths, etc.) must come ONLY from
    configs/mermaid.config.json (single source of truth).

Why deprecated?
- This module represents an alternate/older path that may diverge from the
  current Architecture Guardian rules (Renderer → Config → Exporter separation).
- Keeping it callable risks bypassing the unified config and single-render PDF rules.

SAFE BEHAVIOR:
- Any attempt to call the functions in this module will raise a RuntimeError
  with guidance on what to use instead.

If you really need to inspect older logic, see the git history.
"""

from __future__ import annotations


def _deprecated_error(what: str) -> None:
    raise RuntimeError(
        f"[DEPRECATED] {what} is no longer supported.\n"
        "Use the maintained exporters instead:\n"
        "  - SVG: codeflowai.exporters.svg_exporter.export_svg_from_mmd\n"
        "  - PDF: codeflowai.exporters.pdf_exporter.export_a4_pdf\n"
        "All styling must come from configs/mermaid.config.json via --configFile.\n"
    )


# helpers removed: runner detection will be inlined inside run_mmdc()

# single-call logic will be inlined inside run_mmdc()

# tail-lines helper removed

def run_mmdc(mermaid_path, svg_path, pdf_path, mermaid_config, scale=1.0):
    mmd = str(Path(mermaid_path).resolve())
    mdir = str(Path(mmd).parent)
    runner = shutil.which("mmdc")
    if runner:
        runner = [runner]
    else:
        npx = shutil.which("npx")
        runner = [npx, "-y", "@mermaid-js/mermaid-cli"] if npx else None
    if not runner:
        print("[warn] Mermaid CLI not found. Keeping .mmd only.", file=sys.stderr); return
    for out_path in (svg_path, pdf_path):
        if not out_path: continue
        cmd = [*runner, "-i", Path(mmd).name, "-o", Path(out_path).name, "--scale", str(scale)]
        if mermaid_config and Path(mermaid_config).exists():
            cmd += ["-c", str(Path(mermaid_config).resolve())]
        subprocess.run(cmd, check=True, cwd=mdir)
        # --- 自动调整 PDF 到 A4 (单页, 等比缩放, 可选边距) ---
        if out_path and str(out_path).lower().endswith(".pdf"):
            try:
                import os
                margin_mm = float(os.environ.get("CODEFLOWAI_PDF_MARGIN_MM", "12"))
                fit_pdf_to_a4(out_path, dst_pdf=None, margin_mm=margin_mm, overwrite=True, silent=False)
            except Exception as e:
                print(f"[warn] PDF A4 normalization failed: {e}")

def export_mermaid_and_artifacts(mermaid, out_base, formats, mermaid_config, scale=1.0):
    out = Path(out_base).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    mmd_path = out.with_suffix(".mmd").resolve()
    mmd_path.write_text(mermaid, encoding="utf-8")
    print(f"[ok] Mermaid written → {mmd_path}")

    fmt = {str(f).lower() for f in formats}
    svg_path = str(out.with_suffix(".svg").resolve()) if "svg" in fmt else None
    pdf_path = str(out.with_suffix(".pdf").resolve()) if "pdf" in fmt else None

    # call exporter only if at least one output is requested
    if svg_path or pdf_path:
        run_mmdc(str(mmd_path), svg_path, pdf_path, mermaid_config, scale)
