# tools/run_export_from_source.py
# 作用：读取 Python 源码 -> 解析成 IR -> 渲染 Mermaid -> 调用 mmdc 导出
from pathlib import Path
from codeflowai.parser.py_to_ir import parse_python_to_ir
from codeflowai.renderer.render_mermaid import render_mermaid_from_ir
from codeflowai.exporters.mmdc import export_mermaid_and_artifacts
from codeflowai.utils.svg_tools import center_svg_canvas  # 如果你把函数放在同文件

ROOT = Path(__file__).resolve().parents[1]            # …/CodeFlowAI
MERMAID_CFG = ROOT / "configs" / "mermaid.config.json" # 注意是 config 不是 configs

# 1) 改成你的输入源码路径
SRC = Path(r"D:\UHD\Academic\2025 Fall\Senior Project\CodeFlowAI\tests\test_sample.py")

# 2) 改成你的输出前缀（不带后缀）
OUT = Path(r"D:\UHD\Academic\2025 Fall\Senior Project\CodeFlowAI\out\flowchart")

source = SRC.read_text(encoding="utf-8")
ir = parse_python_to_ir(source)
mermaid = render_mermaid_from_ir(ir, elk=True)

# 3) 想导出哪些格式就列哪些
#### paths = export_mermaid_and_artifacts(mermaid, out_base=OUT, formats=("mmd","svg","pdf"), mermaid_config=None, scale=1.0)
paths = export_mermaid_and_artifacts(
    mermaid, out_base=OUT, formats=("mmd","svg","pdf"), 
    mermaid_config=MERMAID_CFG if MERMAID_CFG.exists() else None,
    scale=1.0,
)

'''
print("[exported]")
for p in paths:
    print(" -", p.resolve())
'''

# 只对 SVG 做“居中后处理”
svg = OUT.with_suffix(".svg")
if svg.exists():
    center_svg_canvas(svg, canvas="A4")        # 或 center_svg_canvas(svg, canvas="A4")
