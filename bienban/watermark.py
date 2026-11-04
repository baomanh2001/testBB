"""Hình nền chính thống: logo công ty làm dấu chìm (watermark) trên mọi trang.

Vì sao dùng **header** của Word
------------------------------
Trong Word, dấu chìm chuẩn của mọi bản in là ảnh floating neo trong *header*
của section — nó tự lặp lại ở **mọi trang**, không đè lên nội dung (nằm dưới
chữ, ``behindDoc="1"``), và người dùng mở file vẫn sửa/xoá được như watermark
thật (Double-click vùng header → chọn ảnh). Cách này bền hơn là chèn ảnh nổi
vào thân bài (dễ lệch trang, dễ bị coi là nội dung).

Logo lấy **ngay từ file mẫu** (``word/media``) nên không cần thêm tài nguyên:
mỗi mẫu 44–48 đều đã có sẵn logo độ phân giải cao.

Cấu hình trong ``config/*.json``::

    "watermark": {
        "enabled": true,
        "opacity": 0.06,          # 0.04–0.10 là vừa mắt khi in
        "scale": 0.62,            # tỉ lệ so với bề ngang vùng in
        "dpi": 96                 # ảnh được hạ xuống để file .docx nhẹ
    }
"""

from __future__ import annotations

import copy
import io
from pathlib import Path

from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
V_NS = "urn:schemas-microsoft-com:vml"

DEFAULTS = {"enabled": True, "opacity": 0.06, "scale": 0.62, "dpi": 96,
            "pages": "all"}


# --------------------------------------------------------------------------- #
# Lấy logo từ chính file mẫu
# --------------------------------------------------------------------------- #
def find_logo(doc) -> bytes | None:
    """Trả về ảnh logo lớn nhất nhúng trong .docx (bỏ qua chữ ký/con dấu).

    Logo công ty là ảnh **có tỉ lệ gần vuông và nhiều điểm ảnh**; chữ ký là ảnh
    rất dẹt (cao/rộng < 0,35). Nhờ vậy không cần đường dẫn cấu hình.
    """
    best: tuple[float, bytes] | None = None
    rels = list(doc.part.rels.values())
    # logo lớn thường được neo trong header (bìa in) chứ không nằm ở thân bài
    for section in getattr(doc, "sections", []):
        for hdr in (getattr(section, "header", None),
                    getattr(section, "first_page_header", None),
                    getattr(section, "even_page_header", None)):
            try:
                rels += list(hdr.part.rels.values())
            except Exception:
                continue
    for rel in rels:
        if rel.reltype != RT.IMAGE or rel.is_external:
            continue
        blob = getattr(rel.target_part, "blob", b"")
        if not blob:
            continue
        try:
            from PIL import Image

            with Image.open(io.BytesIO(blob)) as im:
                w, h = im.size
                if not w or not h or h / w < 0.45:
                    continue          # chữ ký / dải chữ: bỏ qua
                score = _logo_score(im)
        except Exception:
            continue
        if score <= 0:
            continue              # gần như đơn sắc -> chữ ký, con dấu
        # đã loại chữ ký bằng màu: chọn ảnh NHIỀU ĐIỂM ẢNH NHẤT để in cho nét
        # (mẫu có 2 bản logo: 212×188 ở đầu trang và 1227×1091 — chọn bản lớn)
        if best is None or w * h > best[0]:
            best = (w * h, blob)
    return best[1] if best else None


def _logo_score(im) -> float:
    """Chấm điểm "đây có phải logo không": logo có cả đỏ lẫn xanh navy.

    Chữ ký / con dấu chỉ có một màu mực nên điểm = 0.
    """
    try:
        small = im.convert("RGB")
        small.thumbnail((64, 64))
        # Pillow >= 11 khuyến nghị get_flattened_data; bản cũ vẫn dùng getdata
        getter = getattr(small, "get_flattened_data", None) or small.getdata
        px = list(getter())
    except Exception:
        return 0.0
    red = navy = 0
    for r, g, b in px:
        if r > 140 and g < 110 and b < 110:
            red += 1
        elif b > 60 and b > r + 25 and g < b:
            navy += 1
    total = max(1, len(px))
    red_ratio, navy_ratio = red / total, navy / total
    if red_ratio < 0.01 or navy_ratio < 0.01:
        return 0.0
    return min(red_ratio, navy_ratio) * 100


def _shrink(blob: bytes, dpi: int, target_px: int = 900) -> bytes:
    """Hạ độ phân giải logo để file .docx không phình."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(blob)) as im:
            im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
            w, h = im.size
            if max(w, h) <= target_px:
                out = io.BytesIO()
                im.save(out, format="PNG" if im.mode == "RGBA" else "JPEG", quality=88)
                return out.getvalue()
            ratio = target_px / max(w, h)
            im = im.resize((max(1, int(w * ratio)), max(1, int(h * ratio))),
                           Image.LANCZOS)
            out = io.BytesIO()
            im.save(out, format="PNG" if im.mode == "RGBA" else "JPEG", quality=88)
            return out.getvalue()
    except Exception:
        return blob


# --------------------------------------------------------------------------- #
# Sinh XML ảnh floating (watermark)
# --------------------------------------------------------------------------- #
_RUN_XML = """<w:r xmlns:w="{w}" xmlns:wp="{wp}" xmlns:a="{a}" xmlns:v="{v}"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:rPr><w:noProof/></w:rPr>
  <w:drawing>
    <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="1"
        behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1">
      <wp:simplePos x="0" y="0"/>
      <wp:positionH relativeFrom="page"><wp:align>center</wp:align></wp:positionH>
      <wp:positionV relativeFrom="page"><wp:align>center</wp:align></wp:positionV>
      <wp:extent cx="{cx}" cy="{cy}"/>
      <wp:effectExtent l="0" t="0" r="0" b="0"/>
      <wp:wrapNone/>
      <wp:docPr id="{pid}" name="Logo chìm {pid}" descr="Logo công ty (dấu chìm)"/>
      <wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>
      <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
        <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
          <pic:nvPicPr><pic:cNvPr id="{pid}" name="logo-watermark"/><pic:cNvPicPr/></pic:nvPicPr>
          <pic:blipFill>
            <a:blip r:embed="{rid}"><a:alphaModFix amt="{alpha}"/></a:blip>
            <a:stretch><a:fillRect/></a:stretch>
          </pic:blipFill>
          <pic:spPr>
            <a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
            <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          </pic:spPr>
        </pic:pic>
      </a:graphicData></a:graphic>
    </wp:anchor>
  </w:drawing>
</w:r>"""


def _page_geometry(section) -> tuple[int, int, int, int]:
    """(rộng, cao) vùng in + (lề trái, lề phải) — đơn vị twip."""
    try:
        pw, ph = section.page_width, section.page_height
        ml, mr = section.left_margin, section.right_margin
        tm, bm = section.top_margin, section.bottom_margin
        return (int(pw), int(ph), int(ml), int(mr), int(tm), int(bm))
    except Exception:
        return (11906 * 635, 16838 * 635, 1, 1, 1, 1)


def apply_watermark(doc, logo: bytes | None = None, *,
                    opacity: float = 0.06, scale: float = 0.62,
                    dpi: int = 96) -> bool:
    """Chèn logo làm dấu chìm vào header của **mọi section**. Trả về True nếu đã chèn."""
    logo = logo or find_logo(doc)
    if not logo:
        return False
    blob = _shrink(logo, dpi)
    try:
        from PIL import Image

        with Image.open(io.BytesIO(blob)) as im:
            px_w, px_h = im.size
    except Exception:
        px_w, px_h = 4, 3

    alpha = max(0, min(100, int(round(opacity * 100))))
    done = False
    for sec_idx, section in enumerate(doc.sections):
        header = section.header
        header.is_linked_to_previous = False if sec_idx == 0 else True
        if sec_idx and section.header.is_linked_to_previous:
            continue
        # đã có watermark rồi thì thôi (không chèn chồng khi render lại)
        if any("Logo chìm" in (el.get("name") or "")
               for el in header.part.element.iter(qn("wp:docPr"))):
            continue
        pw, ph, ml, mr, tm, bm = _page_geometry(section)
        text_w = max(1, pw - ml - mr)
        cx = int(text_w * max(0.1, min(1.0, scale)))
        cy = int(cx * (px_h / px_w)) if px_w else cx
        # không để logo cao hơn vùng in
        if cy > ph - tm - bm:
            ratio = (ph - tm - bm) / cy
            cx, cy = int(cx * ratio), int(cy * ratio)

        rid, image = header.part.get_or_add_image(io.BytesIO(blob))
        pid = 9000 + sec_idx
        from lxml import etree

        xml = _RUN_XML.format(w=W.strip("{}"), wp=WP_NS, a=A_NS, v=V_NS,
                              cx=cx, cy=cy, pid=pid, rid=rid, alpha=alpha)
        run = etree.fromstring(xml)
        para = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        para._p.append(run)
        done = True
    return done


def watermark_css(logo_bytes: bytes | None, opacity: float = 0.06) -> str:
    """CSS để bản xem trước trên web cũng có đúng dấu chìm như bản in."""
    if not logo_bytes:
        return ""
    import base64

    b64 = base64.b64encode(logo_bytes).decode()
    mime = "image/png" if logo_bytes[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return (
        ".doc-page::before{"
        "content:\"\";position:absolute;inset:0;pointer-events:none;z-index:0;"
        f"opacity:{opacity};background:url(data:{mime};base64,{b64}) center/52% no-repeat;"
        "}\n.doc-page{position:relative}\n.doc-page > *{position:relative;z-index:1}\n"
    )
