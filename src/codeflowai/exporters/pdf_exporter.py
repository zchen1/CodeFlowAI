# src/codeflowai/exporters/pdf_exporter.py
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _resolve_npx_executable() -> str:
    """
    Windows-safe resolver for NPX when shell=False.
    Returns absolute path to npx(.cmd/.exe) if possible,
    otherwise raises a RuntimeError with guidance.
    """
    # 1) Try PATH
    for cand in ("npx.cmd", "npx.exe", "npx"):
        p = shutil.which(cand)
        if p:
            return p

    # 2) Common Windows install locations
    candidates: list[str] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(os.path.join(appdata, "npm", "npx.cmd"))
        candidates.append(os.path.join(appdata, "npm", "npx.exe"))

    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.append(os.path.join(program_files, "nodejs", "npx.cmd"))
        candidates.append(os.path.join(program_files, "nodejs", "npx.exe"))

    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    if program_files_x86:
        candidates.append(os.path.join(program_files_x86, "nodejs", "npx.cmd"))
        candidates.append(os.path.join(program_files_x86, "nodejs", "npx.exe"))

    for p in candidates:
        if p and os.path.exists(p):
            return p

    raise RuntimeError(
        "[error] Could not locate NPX executable.\n"
        "Please ensure Node.js is installed and that npx is on PATH, or "
        "install to the default location (e.g. %APPDATA%\\npm)."
    )


def export_pdf_with_mmdc(
    mmd_file: str,
    out_pdf: str,
    scale: float,
    mermaid_config_abs: str,
    mermaid_css_abs: str,
    use_engine_b: bool = False,
) -> None:
    """
    Render PDF via Mermaid CLI with --pdfFit.
    For Engine B (v11+), you may still want to patch SVG first for arrow geometry.
    """
    mmd = Path(mmd_file).resolve()
    out_pdf_path = Path(out_pdf).resolve()
    out_dir = out_pdf_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    in_name = mmd.name
    out_name = out_pdf_path.name

    cli_pkg = "@mermaid-js/mermaid-cli@10.9.1" if not use_engine_b else "@mermaid-js/mermaid-cli"
    npx_exec = _resolve_npx_executable()

    cmd = [npx_exec, "-y", cli_pkg, "-i", in_name, "-o", out_name, "--scale", str(scale), "--pdfFit"]
    if mermaid_config_abs:
        cmd += ["--configFile", mermaid_config_abs]
    if mermaid_css_abs and os.path.exists(mermaid_css_abs):
        cmd += ["--cssFile", mermaid_css_abs]

    print(f"[debug raw cmd] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(out_dir), check=True, shell=False)
    print(f"[ok] PDF written (mmdc pdfFit) → {out_pdf_path}")
