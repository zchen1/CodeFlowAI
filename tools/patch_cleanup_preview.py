# tools/cleanup_preview.py
# Run:  python tools/cleanup_preview.py examples/your_example.py -o out/preview --export mmd,svg,pdf --elk
# This script DOES NOT modify your package. It post-processes the IR to hide
# Merge/Finally/meaningless Expr nodes, rewires edges, then renders via your renderer.

import argparse
from typing import Any, Dict, List, Set, Tuple
# tools/patch_cleanup_preview.py

import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from codeflowai.parser.py_to_ir import parse_python_to_ir
from codeflowai.renderer.render_mermaid import render_mermaid_from_ir
from codeflowai.exporters.mmdc import export_mermaid_and_artifacts


def _normalize_label(label: str) -> str:
    """Remove non-letters and lowercase, so '\"Expr\", \"Expr\"' -> 'expr'."""
    if not label:
        return ""
    return "".join(ch for ch in label if ch.isalpha()).lower()


def _filter_ir(ir: Dict[str, Any],
               hide_merge: bool = True,
               hide_finally: bool = True,
               deexpr: bool = True) -> Dict[str, Any]:
    """
    Visual cleanup filter (non-breaking):
      - Drop Merge / Finally
      - Drop 'meaningless' Expr (label normalizes to 'expr')
      - Keep actionable Expr whose label starts with Call:/Await/Yield
      - Rewire preds -> succs when dropping nodes; dedupe edges.
    """
    nodes = list(ir.get("nodes", []))
    edges = list(ir.get("edges", []))

    incoming: Dict[str, List[Dict[str, Any]]] = {}
    outgoing: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        incoming.setdefault(e["dst"], []).append(e)
        outgoing.setdefault(e["src"], []).append(e)

    def is_actionable_expr(n: Dict[str, Any]) -> bool:
        if n.get("type") != "Expr":
            return False
        lbl = (n.get("label") or "").strip().lower()
        return lbl.startswith("call:") or lbl.startswith("await") or lbl.startswith("yield")

    def is_meaningless_expr(n: Dict[str, Any]) -> bool:
        if n.get("type") != "Expr":
            return False
        # If already labeled as an action, keep it.
        if is_actionable_expr(n):
            return False
        # Normalize and compare. This catches: 'Expr', '"Expr", "Expr"', 'Expr ,', etc.
        norm = _normalize_label(str(n.get("label") or ""))
        return norm == "expr"

    def should_drop(n: Dict[str, Any]) -> bool:
        t = n.get("type")
        if hide_merge and t == "Merge":
            return True
        if hide_finally and t == "Finally":
            return True
        if deexpr and is_meaningless_expr(n):
            return True
        return False

    # Rewire around dropped nodes
    to_drop: Set[str] = {n["id"] for n in nodes if should_drop(n)}
    new_edges: List[Dict[str, Any]] = []

    if to_drop:
        for d in to_drop:
            preds = incoming.get(d, [])
            succs = outgoing.get(d, [])
            for p in preds:
                for s in succs:
                    new_edges.append({"src": p["src"], "dst": s["dst"], "label": s.get("label")})
        for e in edges:
            if e["src"] in to_drop or e["dst"] in to_drop:
                continue
            new_edges.append(e)
    else:
        new_edges = edges

    # Keep surviving nodes; also relabel actionable Expr for clarity (no-op if none)
    new_nodes: List[Dict[str, Any]] = []
    for n in nodes:
        if n["id"] in to_drop:
            continue
        if is_actionable_expr(n):
            # Normalize common spacing (just cosmetic)
            n = {**n, "label": (n.get("label") or "").strip()}
        new_nodes.append(n)

    # Deduplicate edges
    seen: Set[Tuple[str, str, Any]] = set()
    dedup_edges: List[Dict[str, Any]] = []
    for e in new_edges:
        key = (e["src"], e["dst"], e.get("label"))
        if key in seen:
            continue
        seen.add(key)
        dedup_edges.append(e)

    rest = {k: v for k, v in ir.items() if k not in {"version", "nodes", "edges"}}
    return {"version": ir.get("version", "0.1"), "nodes": new_nodes, "edges": dedup_edges, **rest}


def main():
    ap = argparse.ArgumentParser(description="Preview cleaned CodeFlowAI flowchart without modifying package code.")
    ap.add_argument("source", help="Python source file to parse")
    ap.add_argument("-o", "--out", dest="out_base", required=True, help="Output base path (no extension)")
    ap.add_argument("--export", default="mmd,svg", help="Comma list: mmd,svg,pdf")
    ap.add_argument("--elk", action="store_true", help="Use ELK layout in Mermaid")
    ap.add_argument("--hide-merge", dest="hide_merge", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--hide-finally", dest="hide_finally", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--deexpr", dest="deexpr", action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args()

    # 1) Parse → IR
    with open(args.source, "r", encoding="utf-8") as f:
        src = f.read()
    ir = parse_python_to_ir(src)

    # 2) Visual cleanup
    ir_clean = _filter_ir(ir, hide_merge=args.hide_merge, hide_finally=args.hide_finally, deexpr=args.deexpr)

    # 3) Render → Mermaid
    mermaid = render_mermaid_from_ir(ir_clean, elk=args.elk)

    # 4) Decide mermaid config path (auto-detect)
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = [
        os.path.join(root_dir, "configs", "mermaid.config.json"),
        os.path.join(root_dir, "config", "mermaid.config.json"),
    ]
    mermaid_cfg = next((p for p in candidates if os.path.exists(p)), None)

    # 5) Export
    formats = [x.strip() for x in args.export.split(",") if x.strip()]
    export_mermaid_and_artifacts(
        mermaid,
        args.out_base,
        formats=formats,
        mermaid_config=mermaid_cfg,
        scale=1.0,
    )

    print("\n===== Mermaid (cleaned) =====\n")
    print(mermaid)


if __name__ == "__main__":
    main()
