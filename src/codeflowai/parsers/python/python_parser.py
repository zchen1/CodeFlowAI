from __future__ import annotations
from typing import Dict, List, Optional
import ast
import json

# ---------- Helpers ----------


class _IR:
    def __init__(self) -> None:
        self.nodes: List[Dict] = []
        self.edges: List[Dict] = []
        self._id = 0
        # Pre-create module entry/exit; loc 用 0,0 占位，保证所有节点都有 loc
        self.add_node("entry", "entry", ntype="start", loc={"line": 0, "col": 0})
        self.add_node("exit", "exit", ntype="end", loc={"line": 0, "col": 0})
        # Pending edge labels for “tails” that must connect with a label later (e.g., while-false, break)
        self._pending_labels: Dict[str, str] = {}
        # Collected break tails keyed by loop header id
        self._loop_breaks: Dict[str, List[str]] = {}

    def new_id(self, hint: str = "n") -> str:
        self._id += 1
        return f"{hint}{self._id}"

    def add_node(
        self,
        nid: str,
        label: str,
        ntype: Optional[str] = None,
        loc: Optional[Dict[str, int]] = None,
    ) -> None:
        if loc is None:
            loc = {"line": 0, "col": 0}
        node = {
            "id": nid,
            "label": label,
            "loc": {"line": int(loc["line"]), "col": int(loc["col"])},
        }
        if ntype:
            node["type"] = ntype
        self.nodes.append(node)

    def add_edge(self, src: str, dst: str, label: str = "") -> None:
        e = {"src": src, "dst": dst}
        if label:
            e["label"] = label
        self.edges.append(e)

    def register_break(self, loop_head: str, tail_id: str) -> None:
        self._loop_breaks.setdefault(loop_head, []).append(tail_id)

    def consume_breaks(self, loop_head: str) -> List[str]:
        return self._loop_breaks.pop(loop_head, [])

    def synth(
        self,
        label: str,
        shape: Optional[str] = None,
        loc: Optional[Dict[str, int]] = None,
    ) -> str:
        nid = self.new_id("s")
        self.add_node(nid, label, ntype=shape, loc=loc)
        return nid


def _expr_label(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def _stmt_label(node: ast.stmt) -> str:
    if isinstance(node, ast.Assign):
        return _expr_label(node)
    if isinstance(node, ast.AugAssign):
        return _expr_label(node)
    if isinstance(node, ast.Return):
        return f"return {_expr_label(node.value) if node.value else ''}".strip()
    if isinstance(node, ast.Expr):
        return _expr_label(node.value)
    return node.__class__.__name__


def _node_loc(node: ast.AST) -> Dict[str, int]:
    return {
        "line": int(getattr(node, "lineno", 0) or 0),
        "col": int(getattr(node, "col_offset", 0) or 0),
    }


def _is_recursive(fn: ast.FunctionDef) -> bool:
    name = fn.name

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.recursive = False

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name) and node.func.id == name:
                self.recursive = True
            elif isinstance(node.func, ast.Attribute) and node.func.attr == name:
                self.recursive = True
            if not self.recursive:
                self.generic_visit(node)

    v = _Visitor()
    v.visit(fn)
    return v.recursive


# ---------- Core CFG builder ----------


def parse_python_to_ir(source_code: str) -> Dict:
    ir = _IR()
    entry, exit_ = "entry", "exit"

    try:
        mod: ast.Module = ast.parse(source_code)
    except SyntaxError:
        return {
            "version": "0.1",
            "nodes": [
                {
                    "id": "entry",
                    "label": "entry",
                    "type": "start",
                    "loc": {"line": 0, "col": 0},
                },
                {
                    "id": "exit",
                    "label": "exit",
                    "type": "end",
                    "loc": {"line": 0, "col": 0},
                },
            ],
            "edges": [{"src": "entry", "dst": "exit"}],
        }

    module_stmts = []
    functions = []

    for n in mod.body:
        if isinstance(n, ast.FunctionDef):
            functions.append(n)
        else:
            module_stmts.append(n)

    if module_stmts:
        tails = _build_block(
            ir,
            incoming=entry,
            stmts=module_stmts,
            exit_id=exit_,
            loop_stack=[],
            incoming_label="",
            func_entry=None,
            func_is_recursive=False,
        )
        for tid in tails:
            ir.add_edge(tid, exit_)
    else:
        ir.add_edge(entry, exit_)

    def _fmt_args(fn: ast.FunctionDef) -> str:
        names = []
        for a in fn.args.args:
            names.append(a.arg)
        if fn.args.vararg:
            names.append("*" + fn.args.vararg.arg)
        for a in fn.args.kwonlyargs:
            names.append(a.arg)
        if fn.args.kwarg:
            names.append("**" + fn.args.kwarg.arg)
        return ", ".join(names)

    for fn in functions:
        func_entry = f"{fn.name}_entry"
        func_exit = f"{fn.name}_exit"

        # ---- new formatting for function label ----
        args = _fmt_args(fn).split(", ")
        sig = "function: " + fn.name
        for a in args:
            if a:
                sig += f"\\n+ {a}"

        ir.add_node(func_entry, sig, ntype="start", loc=_node_loc(fn))
        end_line = int(getattr(fn, "end_lineno", getattr(fn, "lineno", 0)) or 0)
        end_col = int(getattr(fn, "end_col_offset", getattr(fn, "col_offset", 0)) or 0)
        ir.add_node(func_exit, "exit", ntype="end", loc={"line": end_line, "col": end_col})

        tails = _build_block(
            ir,
            incoming=func_entry,
            stmts=fn.body,
            exit_id=func_exit,
            loop_stack=[],
            incoming_label="",
            func_entry=func_entry,
            func_is_recursive=_is_recursive(fn),
        )
        for tid in tails:
            ir.add_edge(tid, func_exit)
    
    # ---- DEBUG: print IR output ----
    ir_result = {"version": "0.1", "nodes": ir.nodes, "edges": ir.edges}

    # Pretty-print IR for debugging / PPT extraction
    import json
    print("\n======= IR OUTPUT =======")
    print(json.dumps(ir_result, indent=2, ensure_ascii=False))
    print("==========================\n")

    return {"version": "0.1", "nodes": ir.nodes, "edges": ir.edges}


def _build_block(
    ir: _IR,
    incoming: str,
    stmts: List[ast.stmt],
    exit_id: str,
    loop_stack: Optional[List[str]] = None,
    incoming_label: str = "",
    func_entry: Optional[str] = None,
    func_is_recursive: bool = False,
) -> List[str]:
    if loop_stack is None:
        loop_stack = []

    tails = [incoming]
    for s in stmts:
        new_tails = []

        if isinstance(s, ast.If):
            cond_id = ir.synth(f"if {_expr_label(s.test)}", loc=_node_loc(s))
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, cond_id, lab if lab else "")

            then_tails = _build_block(
                ir,
                incoming=cond_id,
                stmts=s.body,
                exit_id=exit_id,
                loop_stack=loop_stack,
                incoming_label="true",
                func_entry=func_entry,
                func_is_recursive=func_is_recursive,
            )

            orelse = s.orelse
            while orelse and len(orelse) == 1 and isinstance(orelse[0], ast.If):
                eif = orelse[0]
                econd = ir.synth(f"elif {_expr_label(eif.test)}", loc=_node_loc(eif))
                ir.add_edge(cond_id, econd, "false")
                _ = _build_block(
                    ir,
                    incoming=econd,
                    stmts=eif.body,
                    exit_id=exit_id,
                    loop_stack=loop_stack,
                    incoming_label="true",
                    func_entry=func_entry,
                    func_is_recursive=func_is_recursive,
                )
                cond_id = econd
                orelse = eif.orelse

            if orelse:
                else_tails = _build_block(
                    ir,
                    incoming=cond_id,
                    stmts=orelse,
                    exit_id=exit_id,
                    loop_stack=loop_stack,
                    incoming_label="false",
                    func_entry=func_entry,
                    func_is_recursive=func_is_recursive,
                )
            else:
                ir._pending_labels[cond_id] = "false"
                else_tails = [cond_id]

            new_tails = then_tails + else_tails

        elif isinstance(s, ast.While):
            head = ir.synth(f"while {_expr_label(s.test)}", loc=_node_loc(s))
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, head, lab if lab else "")

            body_tails = _build_block(
                ir,
                incoming=head,
                stmts=s.body,
                exit_id=exit_id,
                loop_stack=loop_stack + [head],
                incoming_label="true",
                func_entry=func_entry,
                func_is_recursive=func_is_recursive,
            )
            for bt in body_tails:
                ir.add_edge(bt, head, "back")

            ir._pending_labels[head] = "false"
            break_tails = ir.consume_breaks(head)
            new_tails = [head] + break_tails

        elif isinstance(s, ast.For):
            iter_label = f"for {_expr_label(s.target)} in {_expr_label(s.iter)}"
            head = ir.synth(iter_label, loc=_node_loc(s))
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, head, lab if lab else "")

            body_tails = _build_block(
                ir,
                incoming=head,
                stmts=s.body,
                exit_id=exit_id,
                loop_stack=loop_stack + [head],
                incoming_label="true",
                func_entry=func_entry,
                func_is_recursive=func_is_recursive,
            )
            for bt in body_tails:
                ir.add_edge(bt, head, "back")

            ir._pending_labels[head] = "false"
            break_tails = ir.consume_breaks(head)
            new_tails = [head] + break_tails

        elif isinstance(s, ast.Return):
            ret = ir.synth(_stmt_label(s), loc=_node_loc(s))
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, ret, lab if lab else "")
            ir.add_edge(ret, exit_id)
            if func_entry and func_is_recursive:
                ir.add_edge(ret, func_entry, "recur")
            new_tails = []

        elif isinstance(s, ast.Try):
            try_id = ir.synth("try", loc=_node_loc(s))
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, try_id, lab if lab else "")

            try_tails = _build_block(
                ir,
                incoming=try_id,
                stmts=s.body,
                exit_id=exit_id,
                loop_stack=loop_stack,
                incoming_label="try",
                func_entry=func_entry,
                func_is_recursive=func_is_recursive,
            )

            if s.orelse:
                else_head = ir.synth("else", loc=_node_loc(s))
                for tt in try_tails:
                    ir.add_edge(tt, else_head, "else")
                try_tails = _build_block(
                    ir,
                    incoming=else_head,
                    stmts=s.orelse,
                    exit_id=exit_id,
                    loop_stack=loop_stack,
                    incoming_label="",
                    func_entry=func_entry,
                    func_is_recursive=func_is_recursive,
                )

            exc_tails = []
            for h in s.handlers:
                exc_lbl = "except"
                if h.type is not None:
                    exc_lbl = f"except {_expr_label(h.type)}"
                ehead = ir.synth(exc_lbl, loc=_node_loc(h))
                ir.add_edge(try_id, ehead, "except")
                tails_h = _build_block(
                    ir,
                    incoming=ehead,
                    stmts=h.body,
                    exit_id=exit_id,
                    loop_stack=loop_stack,
                    incoming_label="",
                    func_entry=func_entry,
                    func_is_recursive=func_is_recursive,
                )
                exc_tails.extend(tails_h)

            if s.finalbody:
                fhead = ir.synth("finally", loc=_node_loc(s))

                # 🆕 无论如何，保证 try 头节点连到 finally
                ir.add_edge(try_id, fhead, "finally")

                # 如果某些分支有 tail，也一起连过来
                for tt in try_tails:
                    ir.add_edge(tt, fhead, "finally")
                for et in exc_tails:
                    ir.add_edge(et, fhead, "finally")
                new_tails = _build_block(
                    ir,
                    incoming=fhead,
                    stmts=s.finalbody,
                    exit_id=exit_id,
                    loop_stack=loop_stack,
                    incoming_label="",
                    func_entry=func_entry,
                    func_is_recursive=func_is_recursive,
                )
            else:
                new_tails = try_tails + exc_tails

        elif isinstance(s, ast.Continue):
            if not loop_stack:
                cnode = ir.synth("continue", shape="internal", loc=_node_loc(s))
                for t in tails:
                    lab = ir._pending_labels.pop(t, "") or incoming_label
                    ir.add_edge(t, cnode, lab if lab else "")
                new_tails = [cnode]
            else:
                loop_head = loop_stack[-1]
                cnode = ir.synth("continue", shape="internal", loc=_node_loc(s))
                for t in tails:
                    lab = ir._pending_labels.pop(t, "") or incoming_label
                    ir.add_edge(t, cnode, lab if lab else "")
                    ir.add_edge(cnode, loop_head, "continue")
                new_tails = []

        elif isinstance(s, ast.Break):
            if not loop_stack:
                bnode = ir.synth("break", shape="internal", loc=_node_loc(s))
                for t in tails:
                    lab = ir._pending_labels.pop(t, "") or incoming_label
                    ir.add_edge(t, bnode, lab if lab else "")
                ir._pending_labels[bnode] = "break"
                new_tails = [bnode]
            else:
                loop_head = loop_stack[-1]
                bnode = ir.synth("break", shape="internal", loc=_node_loc(s))
                for t in tails:
                    lab = ir._pending_labels.pop(t, "") or incoming_label
                    ir.add_edge(t, bnode, lab if lab else "")
                ir._pending_labels[bnode] = "break"
                ir.register_break(loop_head, bnode)
                new_tails = []

        else:
            nid = ir.synth(_stmt_label(s), loc=_node_loc(s))
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, nid, lab if lab else "")
            new_tails = [nid]

        tails = new_tails

    return tails
