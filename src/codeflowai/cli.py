from __future__ import annotations
import argparse
from pathlib import Path

from codeflowai.renderer.mermaid_renderer import (
    render_mermaid_from_source,
    write_mermaid_file,
)
from codeflowai.exporters.svg_exporter import export_svg_with_mmdc
from codeflowai.exporters.pdf_exporter import export_pdf_with_mmdc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser("CodeFlowAI CLI")

    # 基本参数：输入源码 + 输出目录
    parser.add_argument("source", help="Path to source file.")
    parser.add_argument(
        "-o", "--out",
        default="out/a4_final",
        help="Output directory (default: out/a4_final).",
    )

    # 可选参数：格式 / 缩放 / 引擎 / 配置文件
    parser.add_argument(
        "--formats",
        default="mmd,svg,pdf",
        help="Comma-separated output formats: mmd,svg,pdf (default: mmd,svg,pdf).",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Mermaid CLI scale (default: 1.0).",
    )
    parser.add_argument(
        "--engine",
        choices=["a", "b"],
        default="a",
        help="a = pinned v10.9.1, b = latest CLI (optional).",
    )
    parser.add_argument(
        "--config",
        default="configs/mermaid.config.json",
        help="Absolute/relative path to Mermaid config JSON.",
    )
    parser.add_argument(
        "--css",
        default="configs/mermaid.css",
        help="Absolute/relative path to Mermaid CSS file.",
    )

    args = parser.parse_args(argv)

    # ---- 准备输出目录 ----
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1) 源码 → Mermaid 文本 → .mmd ----
    mermaid_text = render_mermaid_from_source(args.source)
    out_mmd = out_dir / "a4_final.mmd"
    write_mermaid_file(mermaid_text, str(out_mmd))
    print(f"[stage] mmd → [ok] {out_mmd}")

    # 解析格式列表，做一个小 set，避免重复
    formats = {
        fmt.strip()
        for fmt in str(args.formats).split(",")
        if fmt.strip()
    }

    config_path = str(Path(args.config).resolve())
    css_path = str(Path(args.css).resolve())
    use_engine_b = args.engine == "b"

    # ---- 2) 可选：导出 SVG ----
    if "svg" in formats:
        out_svg = out_dir / "a4_final.svg"
        export_svg_with_mmdc(
            str(out_mmd),
            str(out_svg),
            args.scale,
            config_path,
            css_path,
            use_engine_b=use_engine_b,
        )
        print(f"[stage] svg → [ok] {out_svg}")

    # ---- 3) 可选：导出 PDF ----
    if "pdf" in formats:
        out_pdf = out_dir / "a4_final.pdf"
        export_pdf_with_mmdc(
            str(out_mmd),
            str(out_pdf),
            args.scale,
            config_path,
            css_path,
            use_engine_b=use_engine_b,
        )
        print(f"[stage] pdf → [ok] {out_pdf}")


if __name__ == "__main__":
    main()
