# /src/codeflowai/parsers/python/python_parser.py

from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import ast

# ---------- Helpers ----------
class _IR:
    def __init__(self) -> None:
        self.nodes: List[Dict] = []
        self.edges: List[Dict] = []
        self._id = 0
        # Precreate entry/exit
        self.add_node("entry", "entry", ntype="start")
        self.add_node("exit", "exit", ntype="end")
        # Pending edge labels for “tails” that must connect with a label later (e.g., while-false, break)
        self._pending_labels: Dict[str, str] = {}
        # Collected break tails keyed by loop header id
        self._loop_breaks: Dict[str, List[str]] = {}

    def new_id(self, hint: str = "n") -> str:
        self._id += 1
        return f"{hint}{self._id}"

    def add_node(self, nid: str, label: str, ntype: Optional[str] = None) -> None:
        node = {"id": nid, "label": label}
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

    # synthesis helper kept; type can be used as “internal” when unavoidable
    def synth(self, label: str, shape: Optional[str] = None) -> str:
        nid = self.new_id("s")
        self.add_node(nid, label, ntype=shape)
        return nid


def _expr_label(node: ast.AST) -> str:
    """Best-effort pretty label for small expressions."""
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
    # Fallback to class name
    return node.__class__.__name__


# ---------- Core CFG builder ----------
def parse_python_to_ir(source_code: str) -> Dict:
    """
    IR v0.1 builder for a subset of Python:
      - sequential statements
      - if / elif / else
      - while
      - for ... in ...
      - return (jumps to exit)
    Produces: {version:"0.1", nodes:[{id,label,type?}], edges:[{src,dst,label?}]}
    """
    ir = _IR()
    entry, exit_ = "entry", "exit"

    try:
        mod: ast.Module = ast.parse(source_code)
    except SyntaxError:
        # Fallback to trivial linear IR on parse error
        return {
            "version": "0.1",
            "nodes": [{"id": "entry", "label": "entry", "type": "start"},
                      {"id": "exit",  "label": "exit",  "type": "end"}],
            "edges": [{"src": "entry", "dst": "exit"}],
        }

    # We support top-level straight-line + control-flow, and also descend into the
    # first function if there is one (common student code shape).
    body: List[ast.stmt] = mod.body
    func: Optional[ast.FunctionDef] = None
    for n in mod.body:
        if isinstance(n, ast.FunctionDef):
            func = n
            break
    if func:
        # Treat function entry as the graph's entry label (with args)
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
        ir.nodes = []  # reset to make function signature visible at top if present
        sig = f"function {func.name}({_fmt_args(func)})"
        ir.add_node(entry, sig, ntype="start")
        ir.add_node(exit_, "exit", ntype="end")
        body = func.body

    # Build CFG
    tail_ids = _build_block(ir, entry, body, exit_, loop_stack=[])
    # Connect any dangling tails to exit (if no explicit return)
    for tid in tail_ids:
        ir.add_edge(tid, exit_)

    return {"version": "0.1", "nodes": ir.nodes, "edges": ir.edges}


def _build_block(ir: _IR, incoming: str, stmts: List[ast.stmt], exit_id: str,
                 loop_stack: Optional[List[str]] = None,
                 incoming_label: str = "") -> List[str]:
    """
    Build a straight-line block with control-flow splits/joins.
    Returns a list of "open tails" (node ids that still need to be connected by caller).
    Each “tail” may carry a pending label in ir._pending_labels that will be applied
    when this tail connects to the next newly created node.
    """
    if loop_stack is None:
        loop_stack = []

    tails = [incoming]
    for s in stmts:
        new_tails: List[str] = []
        # Dispatch
        if isinstance(s, ast.If):
            # condition node (diamond by renderer), no synthetic merge/else nodes here
            cond_id = ir.synth(f"if {_expr_label(s.test)}")
            for t in tails:
                # honor any pending label from t, else none
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, cond_id, lab if lab else "")
            # THEN branch: flow labeled true from cond into then-block
            then_tails = _build_block(ir, cond_id, s.body, exit_id, loop_stack=loop_stack, incoming_label="true")
            # ELIF chain handled by chaining conditions on the false edge
            orelse = s.orelse
            # Fold elif as: cond --false--> econd; econd --true--> body
            while orelse and len(orelse) == 1 and isinstance(orelse[0], ast.If):
                eif = orelse[0]
                econd = ir.synth(f"elif {_expr_label(eif.test)}")
                ir.add_edge(cond_id, econd, "false")
                # true branch of this elif
                _ = _build_block(ir, econd, eif.body, exit_id, loop_stack=loop_stack, incoming_label="true")
                # continue down the chain on false
                cond_id = econd
                orelse = eif.orelse
            # ELSE (if present) uses false-labeled flow into its body head
            if orelse:
                else_tails = _build_block(ir, cond_id, orelse, exit_id, loop_stack=loop_stack, incoming_label="false")
            else:
                # no else: false falls through; return the condition as an open tail
                else_tails = [cond_id]
            # Caller is responsible for any future joins; we just return all open tails
            new_tails = then_tails + else_tails

        elif isinstance(s, ast.While):
            head = ir.synth(f"while {_expr_label(s.test)}")
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, head, lab if lab else "")
            # body reached by a 'true' edge from header
            body_tails = _build_block(ir, head, s.body, exit_id, loop_stack=loop_stack + [head], incoming_label="true")
            for bt in body_tails:
                ir.add_edge(bt, head, "back")
            # loop exit is the header itself; mark its pending label as 'false' for the next connection
            ir._pending_labels[head] = "false"
            # also include any recorded breaks from inside the loop as open tails
            break_tails = ir.consume_breaks(head)
            new_tails = [head] + break_tails

        elif isinstance(s, ast.For):
            iter_label = f"for {_expr_label(s.target)} in {_expr_label(s.iter)}"
            head = ir.synth(iter_label)
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, head, lab if lab else "")
            body_tails = _build_block(ir, head, s.body, exit_id, loop_stack=loop_stack + [head], incoming_label="true")
            for bt in body_tails:
                ir.add_edge(bt, head, "back")
            ir._pending_labels[head] = "false"
            break_tails = ir.consume_breaks(head)
            new_tails = [head] + break_tails

        elif isinstance(s, ast.Return):
            ret = ir.synth(_stmt_label(s))
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, ret, lab if lab else "")
            ir.add_edge(ret, exit_id)  # end the path on return
            new_tails = []             # returns do not continue

        elif isinstance(s, ast.Try):
            # try header node
            try_id = ir.synth("try")
            for t in tails:
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, try_id, lab if lab else "")
            # try body (normal path)
            try_tails = _build_block(ir, try_id, s.body, exit_id, loop_stack=loop_stack, incoming_label="try")
            # else (runs only if no exception occurred)
            if s.orelse:
                else_head = ir.synth("else")
                for tt in try_tails:
                    ir.add_edge(tt, else_head, "else")
                try_tails = _build_block(ir, else_head, s.orelse, exit_id, loop_stack=loop_stack)
            # except handlers (0..n)
            exc_tails: List[str] = []
            for h in s.handlers:
                exc_lbl = "except"
                if h.type is not None:
                    exc_lbl = f"except { _expr_label(h.type) }"
                ehead = ir.synth(exc_lbl)
                ir.add_edge(try_id, ehead, "except")
                tails_h = _build_block(ir, ehead, h.body, exit_id, loop_stack=loop_stack)
                exc_tails.extend(tails_h)
            # finally (if present) swallows both normal and except paths, then continues
            if s.finalbody:
                fhead = ir.synth("finally")
                for tt in try_tails:
                    ir.add_edge(tt, fhead, "finally")
                for et in exc_tails:
                    ir.add_edge(et, fhead, "finally")
                new_tails = _build_block(ir, fhead, s.finalbody, exit_id, loop_stack=loop_stack)
            else:
                # no finally: open tails are both normal and exception paths
                new_tails = try_tails + exc_tails

        elif isinstance(s, ast.Continue):
            # continue jumps back to nearest loop head; no synthetic “after” nodes
            if not loop_stack:
                cnode = ir.synth("continue", shape="internal")
                for t in tails:
                    lab = ir._pending_labels.pop(t, "") or incoming_label
                    ir.add_edge(t, cnode, lab if lab else "")
                new_tails = [cnode]
            else:
                loop_head = loop_stack[-1]
                cnode = ir.synth("continue", shape="internal")
                for t in tails:
                    lab = ir._pending_labels.pop(t, "") or incoming_label
                    ir.add_edge(t, cnode, lab if lab else "")
                    ir.add_edge(cnode, loop_head, "continue")
                new_tails = []  # path cut here

        elif isinstance(s, ast.Break):
            # break exits nearest loop; we don't know successor yet, so:
            if not loop_stack:
                bnode = ir.synth("break", shape="internal")
                for t in tails:
                    lab = ir._pending_labels.pop(t, "") or incoming_label
                    ir.add_edge(t, bnode, lab if lab else "")
                # leave as open tail; next connection will carry pending 'break' if desired
                ir._pending_labels[bnode] = "break"
                new_tails = [bnode]
            else:
                loop_head = loop_stack[-1]
                bnode = ir.synth("break", shape="internal")
                for t in tails:
                    lab = ir._pending_labels.pop(t, "") or incoming_label
                    ir.add_edge(t, bnode, lab if lab else "")
                # record as loop exit tail; caller of the loop will connect it forward
                ir._pending_labels[bnode] = "break"
                ir.register_break(loop_head, bnode)
                new_tails = []  # cut inside the loop

        else:
            # Simple statement → single node
            nid = ir.synth(_stmt_label(s))
            for t in tails:
                # apply pending label (e.g., while-false, break) or incoming_label if present
                lab = ir._pending_labels.pop(t, "") or incoming_label
                ir.add_edge(t, nid, lab if lab else "")
            new_tails = [nid]

        tails = new_tails or tails

    return tails