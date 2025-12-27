from __future__ import annotations
from pathlib import Path
from codeflowai.parsers.python.python_parser import parse_python_to_ir
from typing import Dict, Any, List

def _sanitize_label(text: str) -> str:
    """
    Make labels safe for Mermaid:
    - remove newlines
    - remove or neutralize punctuation that may confuse the parser
    """
    # 基本清洗
    text = text.replace("\n", " ")
    text = text.replace('"', "'")

    # 把容易搞乱 Mermaid 语法的符号都换成空格
    # 比如函数签名里的 ()[]{} , : 等
    for ch in "()[]{},:":   # 可以按需要再加
        text = text.replace(ch, " ")

    # 压缩多余空格
    text = " ".join(text.split())
    return text.strip()


def _node_shape(node: Dict[str, Any]) -> str:
    """
    Map IR node → Mermaid node syntax.
    - type == "start"  → rounded box  ([Start])
    - type == "end"    → circle       ((End))
    - if/elif/while/for/try/except…  → diamond {cond}
    - default          → rectangle    [stmt]
    """
    nid = node["id"]
    raw_label = str(node.get("label", ""))
    label = _sanitize_label(raw_label)
    ntype = node.get("type", "")

    # Start / End
    if ntype == "start":
        return f"  {nid}([{label}])"
    if ntype == "end":
        return f"  {nid}(({label}))"

    # Heuristic: decision / control nodes → diamond
    lower = raw_label.lstrip().lower()
    if (
        lower.startswith("if ")
        or lower.startswith("elif ")
        or lower.startswith("while ")
        or lower.startswith("for ")
        or lower.startswith("try")
        or lower.startswith("except")
        or lower.startswith("finally")
        or lower.startswith("else")
    ):
        return f"  {nid}{{{label}}}"

    # Default: normal statement box
    return f"  {nid}[{label}]"


def _edge_line(edge: Dict[str, Any]) -> str:
    """
    Map IR edge → Mermaid edge.
    If label exists, use:  A -- label --> B
    Otherwise:             A --> B
    """
    src = edge["src"]
    dst = edge["dst"]
    lbl = _sanitize_label(str(edge.get("label", "")))

    if lbl:
        return f"  {src} -- {lbl} --> {dst}"
    else:
        return f"  {src} --> {dst}"


def ir_to_mermaid(ir: Dict[str, Any]) -> str:
    """
    Convert IR dict {version,nodes,edges} → Mermaid flowchart text.
    """
    lines: List[str] = ["flowchart TD"]

    # 不要渲染模块级 entry/exit
    hidden_ids: set[str] = {"entry", "exit"}

    # 1) Nodes
    for node in ir.get("nodes", []):
        nid = str(node.get("id"))
        raw_label = str(node.get("label", ""))
        lower_label = raw_label.lower()

        # 1) 过滤模块级 entry / exit
        if nid in hidden_ids:
            continue

        # 2) 过滤 import / import-from 语句
        #    _stmt_label 对 Import / ImportFrom 会给出 "Import" / "ImportFrom"
        if lower_label.startswith("import"):
            hidden_ids.add(nid)   # 记住这个 id，后面边也不画
            continue

        lines.append(_node_shape(node))

    # 2) Edges
    for edge in ir.get("edges", []):
        src = str(edge.get("src"))
        dst = str(edge.get("dst"))

        # 任意一端是隐藏节点（entry/exit 或 import 节点），就不画
        if src in hidden_ids or dst in hidden_ids:
            continue

        lines.append(_edge_line(edge))

    return "\n".join(lines)

def render_mermaid_from_source(source_path: str) -> str:
    """
    Real renderer: source.py → IR → Mermaid.
    """
    source_code = Path(source_path).read_text(encoding="utf-8")
    ir = parse_python_to_ir(source_code)
    return ir_to_mermaid(ir)

def write_mermaid_file(mermaid_text: str, out_mmd: str) -> None:
    out = Path(out_mmd).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(mermaid_text, encoding="utf-8")
