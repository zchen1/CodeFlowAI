# codeflowai/utils/sanitize.py
import re

_RESERVED_IDS = {"end", "subgraph", "class", "style", "click", "linkStyle"}

def ascii_text(s: str) -> str:
    """Normalize unicode dashes/arrows to ASCII for Mermaid."""
    if s is None:
        return ""
    s = str(s)
    s = (s
         .replace("→", "-->")
         .replace("—", "-")
         .replace("–", "-")
         .replace("−", "-"))
    return s

def mermaid_safe_id(raw: str) -> str:
    """Make a Mermaid-safe identifier without changing IR semantics."""
    s = re.sub(r"[^\w]", "_", str(raw).strip())  # keep [A-Za-z0-9_]
    if not s:
        s = "n"
    if s[0].isdigit():
        s = "n_" + s
    if s.lower() in _RESERVED_IDS:
        s = s + "_node"
    return s

def mermaid_safe_label(raw: str) -> str:
    """Escape quotes and normalize unicode in labels."""
    s = ascii_text("" if raw is None else str(raw))
    return s.replace('"', r'\"')
