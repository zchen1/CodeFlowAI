from __future__ import annotations

def parse_python_to_ir(source_code: str) -> dict:
    """
    最小占位：不解析 Python，直接返回一个固定 IR。
    后面再把这里替换成 AST -> IR 的真实实现。
    """
    return {
        "version": "0.1",
        "nodes": [
            {"id": "start", "label": "Start", "shape": "circle"},
            {"id": "file", "label": "file", "shape": "rect"},
            {"id": "end", "label": "End", "shape": "circle"},
        ],
        "edges": [
            {"source": "start", "target": "file", "label": ""},
            {"source": "file", "target": "end", "label": ""},
        ],
    }
