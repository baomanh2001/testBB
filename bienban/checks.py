"""Soát lại số liệu sau khi AI đọc ảnh — "log nhỏ cảnh báo" cho người dùng.

Hai lớp độc lập:

1. **Lớp quy tắc** (:func:`check_rules`) — không gọi mạng, luôn chạy, tức thì:

   * ``Kht`` phải bằng ``R60 / R15`` (sai lệch > 2% là đáng ngờ);
   * dòng trong cùng một bảng **giống hệt nhau** (trừ số tem / STT) — dấu hiệu
     AI chép lại dòng 1 cho mọi dòng;
   * giá trị chạm thang đo phải có dấu ``>`` (``5000`` khi thang là ``>5000``);
   * dãy nấc (tỉ số biến áp, R một chiều) lệch bất thường giữa hai nấc liền kề;
   * tổng số dòng khác với ``so_luong`` đã ghi;
   * số tem / số máy sai số chữ số; ngày sai hoặc không tồn tại.

2. **Lớp AI** (:func:`check_with_ai`) — tuỳ chọn, gửi lại chính các ảnh đã dùng
   để nhận dạng và hỏi model đối chiếu "trong JSON" với "trên ảnh". Chậm hơn
   (~10–30 giây) nhưng bắt được lỗi đọc chữ số mà quy tắc không thấy.

Mọi cảnh báo đều có ``where`` (đường dẫn dữ liệu) + ``field`` + ``form`` để giao
diện nhảy tới đúng ô và tô sáng ô đó.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from typing import Iterable

from .normalize import digits_only, norm_date
from .vision import call_gemini

# --------------------------------------------------------------------------- #
# Kiểu dữ liệu cảnh báo
# --------------------------------------------------------------------------- #


@dataclass
class Warning_:
    """Một cảnh báo trong "log nhỏ"."""

    level: str = "warn"          # "warn" | "info"
    where: str = ""              # đường dẫn trong JSON, ví dụ bien_ban_45_mccb.rows[2].rtx_a
    message: str = ""
    field: str = ""              # khoá ô cần tô sáng
    form: str = ""               # mẫu 44..48 (để giao diện mở đúng tab)
    source: str = dc_field(default="rule")   # "rule" | "ai"

    def as_dict(self) -> dict:
        return {"level": self.level, "where": self.where, "message": self.message,
                "field": self.field, "form": self.form, "source": self.source}


# --------------------------------------------------------------------------- #
# Đọc số kiểu Việt Nam
# --------------------------------------------------------------------------- #
_NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _num(value) -> float | None:
    """``"3,52"`` → 3.52; ``">5000"`` → 5000; không đọc được → ``None``."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    text = text.lstrip("><≥≤").replace("µ", "").replace("Ω", "").replace("M", "")
    m = _NUM_RE.search(text.replace(".", "").replace(",", ".")) if text.count(",") else _NUM_RE.search(text)
    if not m:
        return None
    try:
        # "1.234,5" -> 1234.5 ; "3.52" (kiểu US) -> 3.52
        raw = m.group(0)
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        return float(raw)
    except ValueError:
        return None


def _is_dash(value) -> bool:
    return str(value).strip() in ("-", "–", "—", "")


# --------------------------------------------------------------------------- #
# Truy cập dữ liệu chịu được nhiều hình dạng
# --------------------------------------------------------------------------- #
def _rows(data: dict, key: str) -> list[dict]:
    block = data.get(key) or {}
    raw = block.get("rows")
    if isinstance(raw, dict):
        raw = raw.get("rows")
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    # các khoá bảng cũ nằm rời
    for alt in (f"{key}_rows", "ket_qua_thu_nghiem"):
        if isinstance(block.get(alt), list):
            return [r for r in block[alt] if isinstance(r, dict)]
    return []


def _seq(data: dict, key: str, path: str) -> list:
    block = data.get(key) or {}
    cur = block
    for part in path.split("."):
        if not isinstance(cur, dict):
            return []
        cur = cur.get(part)
    return cur if isinstance(cur, list) else []


# --------------------------------------------------------------------------- #
# Lớp quy tắc
# --------------------------------------------------------------------------- #
def check_rules(data: dict) -> list[Warning_]:
    """Soát bằng quy tắc (không gọi mạng). Trả về danh sách :class:`Warning_`."""
    out: list[Warning_] = []

    # ---------- Kht = R60 / R15 (mẫu 44) ----------
    b44 = data.get("bien_ban_44_mba") or {}
    rcd = b44.get("r_cach_dien_Mohm")
    items44 = rcd.get("rows") if isinstance(rcd, dict) else (rcd or [])
    for i, it in enumerate(items44 or []):
        if not isinstance(it, dict):
            continue
        r60, r15, kht = _num(it.get("r60")), _num(it.get("r15")), _num(it.get("knt"))
        name = it.get("key") or f"dòng {i + 1}"
        if not r60 or not r15:
            continue
        calc = r60 / r15
        if kht is None:
            out.append(Warning_(
                "info", f"bien_ban_44_mba.r_cach_dien_Mohm[{i}].knt",
                f"{name}: để trống Kht — tự tính được {calc:.2f}".replace(".", ","),
                field="knt", form="44"))
        elif abs(kht - calc) / calc > 0.02:
            out.append(Warning_(
                "warn", f"bien_ban_44_mba.r_cach_dien_Mohm[{i}].knt",
                f"Kht ghi {it.get('knt')} nhưng R60/R15 = {r60:g}/{r15:g} = "
                f"{calc:.2f}".replace(".", ",") + " — kiểm tra lại",
                field="knt", form="44"))

    # ---------- MBA 3 PHA (mẫu 49): kiểm chéo số liệu ----------
    b49 = data.get("bien_ban_49_mba_3p") or {}
    if b49:
        rcd49 = b49.get("r_cach_dien_Mohm")
        items49 = rcd49.get("rows") if isinstance(rcd49, dict) else (rcd49 or [])
        ten_dong = {"cao_vo": "Cao – Vỏ", "cao_ha": "Cao – Hạ", "ha_vo": "Hạ – Vỏ"}
        for i, it in enumerate(items49 or []):
            if not isinstance(it, dict):
                continue
            r60, r15, kht = _num(it.get("r60")), _num(it.get("r15")), _num(it.get("knt"))
            name = ten_dong.get(it.get("key") or "", it.get("key") or f"dòng {i + 1}")
            if r60 and r15:
                calc = r60 / r15
                if kht is None:
                    out.append(Warning_(
                        "info", f"bien_ban_49_mba_3p.r_cach_dien_Mohm[{i}].knt",
                        f"{name}: để trống Kht — tự tính được {calc:.2f}".replace(".", ","),
                        field="knt", form="49"))
                elif abs(calc - kht) > 0.05:
                    out.append(Warning_(
                        "warn", f"bien_ban_49_mba_3p.r_cach_dien_Mohm[{i}].knt",
                        f"{name}: Kht ghi {it.get('knt')} nhưng R60/R15 = "
                        f"{calc:.2f}".replace(".", ",") + " — kiểm tra lại",
                        field="knt", form="49"))
                if r60 < r15:
                    out.append(Warning_(
                        "warn", f"bien_ban_49_mba_3p.r_cach_dien_Mohm[{i}].r60",
                        f"{name}: R60 ({it.get('r60')}) nhỏ hơn R15 ({it.get('r15')}) — "
                        "thường phải ngược lại, có thể đọc nhầm cột",
                        field="r60", form="49"))
        # 3 pha của cùng một nấc phải xấp xỉ bằng nhau
        phases = (b49.get("r_cuon_day_1_chieu_ohm") or {}).get("cao_ap") or {}
        if isinstance(phases, dict):
            seqs = {k: [_num(v) for v in (phases.get(k) or [])]
                    for k in ("ab", "bc", "ca")}
            for i in range(5):
                vals = [s[i] for s in seqs.values() if len(s) > i and s[i] is not None]
                if len(vals) < 2:
                    continue
                lo, hi = min(vals), max(vals)
                if lo and (hi - lo) / lo > 0.10:
                    out.append(Warning_(
                        "warn", f"bien_ban_49_mba_3p.r_cuon_day_1_chieu_ohm.cao_ap[{i}]",
                        f"Nấc {i + 1}: AB/BC/CA chênh tới {(hi - lo) / lo * 100:.0f}% "
                        f"({lo:g} … {hi:g}) — 3 pha thường xấp xỉ bằng nhau",
                        field="ab", form="49"))
                    break
            # dãy nấc phải đơn điệu
            for ph, seq in seqs.items():
                clean = [v for v in seq if v is not None]
                for j in range(1, len(clean)):
                    if clean[j - 1] and abs(clean[j] - clean[j - 1]) / clean[j - 1] > 0.25:
                        out.append(Warning_(
                            "warn",
                            f"bien_ban_49_mba_3p.r_cuon_day_1_chieu_ohm.cao_ap.{ph}[{j}]",
                            f"Cột {ph.upper()}: nấc {j + 1} = {clean[j]:g} lệch "
                            f"{abs(clean[j] - clean[j - 1]) / clean[j - 1] * 100:.0f}% so "
                            f"với nấc {j} = {clean[j - 1]:g} — có thể đọc nhầm chữ số",
                            field=ph, form="49"))
                        break
        # K1 ≈ K2 ≈ K3 ở mỗi nấc
        ratios = b49.get("ti_so_bien_ap") or {}
        if isinstance(ratios, dict):
            rseq = {k: [_num(v) for v in (ratios.get(k) or [])] for k in ("k1", "k2", "k3")}
            for i in range(5):
                vals = [s[i] for s in rseq.values() if len(s) > i and s[i] is not None]
                if len(vals) < 2:
                    continue
                lo, hi = min(vals), max(vals)
                if lo and (hi - lo) / lo > 0.02:
                    out.append(Warning_(
                        "warn", f"bien_ban_49_mba_3p.ti_so_bien_ap[{i}]",
                        f"Nấc {i + 1}: K1/K2/K3 chênh tới {(hi - lo) / lo * 100:.1f}% "
                        f"({lo:g} … {hi:g}) — ba pha thường gần như bằng nhau",
                        field="k1", form="49"))
                    break
        # số pha / tổ đấu dây
        so_pha = digits_only(b49.get("so_pha") or "")
        if so_pha and so_pha not in ("03", "3", "003"):
            out.append(Warning_(
                "warn", "bien_ban_49_mba_3p.so_pha",
                f"Mẫu 49 là MBA 3 pha nhưng Số pha = {so_pha}", field="so_pha", form="49"))
        to_dau = str(b49.get("to_dau_day") or "").strip()
        if to_dau and re.match(r"^I{1,2}/I", to_dau, re.I):
            out.append(Warning_(
                "warn", "bien_ban_49_mba_3p.to_dau_day",
                f"Tổ đấu dây {to_dau!r} là của MBA 1 pha — kiểm tra lại mẫu",
                field="to_dau_day", form="49"))

    # ---------- dãy nấc lệch bất thường (mẫu 44) ----------
    for key, label, path in (
        ("bien_ban_44_mba", "Tỉ số biến áp – Hạ 1", "ti_so_bien_ap.ha_1"),
        ("bien_ban_44_mba", "Tỉ số biến áp – Hạ 2", "ti_so_bien_ap.ha_2"),
        ("bien_ban_44_mba", "R một chiều – cao áp", "r_cuon_day_1_chieu_ohm.cao_ap"),
    ):
        seq = [_num(v) for v in _seq(data, key, path)]
        for i in range(1, len(seq)):
            cur, prev = seq[i], seq[i - 1]
            if cur is None or prev in (None, 0):
                continue
            jump = abs(cur - prev) / abs(prev)
            if jump > 0.25:
                out.append(Warning_(
                    "warn", f"{key}.{path}[{i}]",
                    f"{label}: nấc {i + 1} = {cur:g} lệch {jump * 100:.0f}% so với "
                    f"nấc {i} = {prev:g} — có thể đọc nhầm chữ số", form="44"))
                break

    # ---------- bảng nhiều dòng: dòng giống hệt + số dòng vs số lượng ----------
    for form, key, cols in (
        ("45", "bien_ban_45_mccb", ["rcd_close", "rcd_open", "rtx_a", "rtx_b", "rtx_c",
                                    "utest", "dong_cat", "ket_qua"]),
        ("46", "bien_ban_46_la", ["r_cach_dien", "dong_ro", "u_ac"]),
        ("47", "bien_ban_47_fco", ["rcd_truoc", "rcd_sau", "ac_kho", "ac_uot", "dong_cat"]),
        ("48", "bien_ban_48_tiep_dat", ["ket_noi_trung_tinh", "loai_tiep_dat", "gia_tri_do"]),
    ):
        block = data.get(key) or {}
        items = _rows(data, key)
        sig = [tuple(str(it.get(c, "")).strip() for c in cols) for it in items]
        for i in range(1, len(sig)):
            if sig[i] and sig[i] == sig[i - 1] and any(sig[i]):
                out.append(Warning_(
                    "warn", f"{key}.rows[{i}]",
                    f"Dòng {i + 1} giống hệt dòng {i} (mọi cột số liệu) — AI có thể "
                    f"đã chép lại dòng trên", form=form))
        # số dòng vs số lượng (chạy cả khi bảng chỉ có 1 dòng)
        so_luong = digits_only(block.get("so_luong") or "")
        if so_luong and sig and int(so_luong) != len(sig):
            out.append(Warning_(
                "warn", f"{key}.so_luong",
                f"Số lượng ghi {so_luong} nhưng bảng có {len(sig)} dòng — kiểm tra lại",
                field="so_luong", form=form))

    # ---------- giá trị chạm thang đo nhưng thiếu dấu '>' ----------
    def _thang(value, nguong):
        n = _num(value)
        if n is not None and n >= nguong and ">" not in str(value):
            return n
        return None

    for i, it in enumerate(_rows(data, "bien_ban_45_mccb")):
        for col in ("rcd_close", "rcd_open"):
            if _thang(it.get(col), 5000):
                out.append(Warning_(
                    "info", f"bien_ban_45_mccb.rows[{i}].{col}",
                    f"R cách điện {it.get(col)} ≥ 5000 nhưng thiếu dấu '>' — mẫu ghi '>5000'",
                    field=col, form="45"))
    for form, key, col in (("46", "bien_ban_46_la", "r_cach_dien"),
                           ("47", "bien_ban_47_fco", "rcd_truoc"),
                           ("47", "bien_ban_47_fco", "rcd_sau")):
        for i, it in enumerate(_rows(data, key)):
            if _thang(it.get(col), 10000):
                out.append(Warning_(
                    "info", f"{key}.rows[{i}].{col}",
                    f"Giá trị {it.get(col)} ≥ 10000 nhưng thiếu dấu '>' — mẫu ghi '>10000'",
                    field=col, form=form))

    # ---------- số tem / số máy / ngày ----------
    for form, key, field_name, length in (
        ("44", "bien_ban_44_mba", "so_may", 8),
        ("44", "bien_ban_44_mba", "so_tem", 6),
        ("45", "bien_ban_45_mccb", "so_tem", 6),
    ):
        block = data.get(key) or {}
        val = block.get(field_name)
        if val in (None, ""):
            continue
        digits = digits_only(val)
        if len(digits) != length:
            out.append(Warning_(
                "warn", f"{key}.{field_name}",
                f"{field_name} = {val!r} chỉ có {len(digits)} chữ số (mẫu cần {length})",
                field=field_name, form=form))

    tt = data.get("thong_tin_chung") or {}
    for k, label in (("ngay_kiem_dinh", "Ngày kiểm định"),
                     ("ngay_lap_bien_ban", "Ngày lập biên bản")):
        v = tt.get(k)
        if v in (None, ""):
            continue
        n = norm_date(v)
        good = bool(re.fullmatch(r"\d{2}/\d{2}/\d{4}", n or ""))
        if good:
            try:
                datetime.strptime(n, "%d/%m/%Y")      # chặn 32/11, 31/02…
            except ValueError:
                good = False
        if not good:
            out.append(Warning_("warn", f"thong_tin_chung.{k}",
                                f"{label} = {v!r} không đúng dạng dd/mm/yyyy",
                                field=k))

    return out


# --------------------------------------------------------------------------- #
# Lớp AI: đối chiếu lại chính các ảnh đã đọc
# --------------------------------------------------------------------------- #
CHECK_PROMPT = """Bạn đang SOÁT LẠI một biên bản vừa được máy đọc từ ảnh.

Nhiệm vụ: đối chiếu từng số liệu trong JSON dưới đây với ảnh gửi kèm, tìm những
chỗ đọc SAI (nhầm chữ số, nhầm dấu phẩy, nhầm dòng, thiếu dấu '>', sai đơn vị).

QUY TẮC:
1. Chỉ báo những chỗ THỰC SỰ khác giữa JSON và ảnh. Không góp ý văn phong.
2. Không báo lỗi nếu ảnh mờ/không đọc được — khi đó bỏ qua.
3. ``in_json`` là giá trị đang có trong JSON; ``on_image`` là giá trị đọc được
   trên ảnh. Nếu bạn thấy JSON đúng thì KHÔNG đưa vào kết quả.
4. Tối đa 12 mục. Trả về JSON thuần, không markdown.

CẤU TRÚC TRẢ VỀ:
{"checks": [{"where": "bien_ban_45_mccb.rows[0].rtx_a", "in_json": "273",
             "on_image": "278", "note": "chữ số cuối bị đọc nhầm"}]}

Nếu không có gì sai: {"checks": []}

=== JSON ĐANG CẦN SOÁT ===
{data}
"""


def check_with_ai(data: dict, images: Iterable[bytes], *, key: str | None = None,
                  model: str | None = None, forms: list[str] | None = None) -> list[Warning_]:
    """Hỏi lại model với chính các ảnh đã dùng để nhận dạng (tuỳ chọn)."""
    blobs = [b for b in images if b][:8]
    if not blobs:
        return []
    payload = json.dumps(data, ensure_ascii=False)
    if len(payload) > 60000:                    # prompt quá dài: cắt bớt cho an toàn
        payload = payload[:60000]
    prompt = CHECK_PROMPT.replace("{data}", payload)
    raw = call_gemini(blobs, key=key, model=model, prompt_override=prompt,
                      max_tokens=4096)
    checks = raw.get("checks") if isinstance(raw, dict) else None
    out: list[Warning_] = []
    for item in (checks or [])[:12]:
        if not isinstance(item, dict):
            continue
        where = str(item.get("where") or "")
        form = ""
        m = re.search(r"bien_ban_(\d\d)", where)
        if m:
            form = m.group(1)
        note = str(item.get("note") or "").strip()
        in_json, on_image = item.get("in_json"), item.get("on_image")
        msg = f"Trên ảnh là {on_image!r} nhưng JSON ghi {in_json!r}"
        if note:
            msg += f" ({note})"
        out.append(Warning_("warn", where, msg, field="", form=form, source="ai"))
    return out
