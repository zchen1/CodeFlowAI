from __future__ import annotations
from pathlib import Path

# A4 in points
_A4_W = 595.275590551  # 210 mm
_A4_H = 841.88976378   # 297 mm

def _pt_from_mm(mm: float) -> float:
    return float(mm) * 72.0 / 25.4

def fit_pdf_to_a4(
    src_pdf: str | Path,
    dst_pdf: str | Path | None = None,
    margin_mm: float = 12.0,
    overwrite: bool = True,
    silent: bool = False,
) -> Path:
    """
    将现有单页 PDF 等比缩放并居中到 A4 纸面，留边距；默认覆盖原文件。
    返回输出 Path。若依赖缺失或失败，原样返回 src 路径。
    """
    src = Path(src_pdf).resolve()
    out = Path(dst_pdf).resolve() if dst_pdf else src

    if not src.exists():
        if not silent:
            print(f"[warn] fit_pdf_to_a4: source not found → {src}")
        return src

    # 惰性依赖：缺失则跳过，不破坏导出主流程
    try:
        from pypdf import PdfReader, PdfWriter
        try:
            from pypdf import Transformation  # 新版 API
            _has_transform = True
        except Exception:
            _has_transform = False
    except Exception:
        if not silent:
            print("[warn] fit_pdf_to_a4: pypdf not installed; run `pip install -U pypdf` to enable A4 normalization")
        return src

    try:
        reader = PdfReader(str(src))
        if len(reader.pages) < 1:
            if not silent:
                print("[warn] fit_pdf_to_a4: empty PDF")
            return src

        page = reader.pages[0]
        x0, y0, x1, y1 = page.mediabox
        pw, ph = float(x1 - x0), float(y1 - y0)

        # 目标内容区（A4 扣边距）
        margin_pt = max(0.0, float(margin_mm)) * 72.0 / 25.4
        cw = max(1.0, _A4_W - 2 * margin_pt)
        ch = max(1.0, _A4_H - 2 * margin_pt)

        # 等比缩放与居中
        s = min(cw / pw, ch / ph)
        ox = margin_pt + (cw - pw * s) / 2.0
        oy = margin_pt + (ch - ph * s) / 2.0

        writer = PdfWriter()
        new_page = writer.add_blank_page(width=_A4_W, height=_A4_H)

        if _has_transform:
            from pypdf import Transformation
            t = Transformation().scale(s).translate(tx=ox, ty=oy)
            if hasattr(new_page, "merge_transformed_page"):
                new_page.merge_transformed_page(page, t, expand=False)
            elif hasattr(new_page, "mergeTransformedPage"):
                new_page.mergeTransformedPage(page, t, expand=False)
            else:
                # Fallback：直接复制页面对象（防止空白）
                new_page.merge_page(page)

        else:
            # 老 API 兼容：先缩放再平移合并
            if hasattr(page, "scale_by"):
                page.scale_by(s)
            elif hasattr(page, "scaleBy"):
                page.scaleBy(s)
            else:
                if not silent:
                    print("[warn] fit_pdf_to_a4: pypdf version too old (no scale_by)")
                return src
            if hasattr(new_page, "merge_translated_page"):
                new_page.merge_translated_page(page, ox, oy)
            elif hasattr(new_page, "mergeTranslatedPage"):
                new_page.mergeTranslatedPage(page, ox, oy, expand=False)
            else:
                if not silent:
                    print("[warn] fit_pdf_to_a4: pypdf version too old (no merge_translated_page)")
                return src

        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "wb") as f:
            writer.write(f)

        if not silent:
            mode = "(overwrite)" if out == src else f"→ {out.name}"
            print(f"[ok] A4 normalized {mode}: {out}  margin_mm={margin_mm:.1f}")
        return out

    except Exception as e:
        if not silent:
            print(f"[warn] fit_pdf_to_a4: failed with {e.__class__.__name__}: {e}")
        return src
