# src/codeflowai/exporters/svg_exporter.py
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
    appdata = os.environ.get("APPDATA")  # e.g. C:\Users\<user>\AppData\Roaming
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


def export_svg_with_mmdc(
    mmd_file: str,
    out_svg: str,
    scale: float,
    mermaid_config_abs: str,
    mermaid_css_abs: str,
    use_engine_b: bool = False,
) -> None:
    """
    Render SVG via Mermaid CLI.

    Engine A (default): pins @mermaid-js/mermaid-cli@10.9.1 → arrow size honored via config.
    Engine B: latest @mermaid-js/mermaid-cli (v11+) → recommended only if you will patch SVG markers later.
    """
    mmd = Path(mmd_file).resolve()
    out_svg_path = Path(out_svg).resolve()
    out_dir = out_svg_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    in_name = mmd.name
    out_name = out_svg_path.name

    cli_pkg = "@mermaid-js/mermaid-cli@10.9.1" if not use_engine_b else "@mermaid-js/mermaid-cli"
    npx_exec = _resolve_npx_executable()

    cmd = [npx_exec, "-y", cli_pkg, "-i", in_name, "-o", out_name, "--scale", str(scale)]
    if mermaid_config_abs:
        cmd += ["--configFile", mermaid_config_abs]
    if mermaid_css_abs and os.path.exists(mermaid_css_abs):
        cmd += ["--cssFile", mermaid_css_abs]

    print(f"[debug raw cmd] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(out_dir), check=True, shell=False)
    print(f"[ok] SVG written → {out_svg_path}")
