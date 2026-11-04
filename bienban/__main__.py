"""Giao diện dòng lệnh.

Ví dụ::

    python -m bienban fill samples/e-green-01112026.json -o output/
    python -m bienban fill data.json --forms 44,48 --company-accent
    python -m bienban check data.json          # chỉ kiểm tra JSON, không ghi file
    cat data.json | python -m bienban fill - -o output/

Mã thoát: 0 = OK, 1 = có cảnh báo, 2 = dữ liệu không hợp lệ.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .fill import load_config, render_all
from .spec import TEMPLATES, TITLES
from .validate import validate

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _default_log(quiet: bool):
    def log(msg: str):
        if not quiet:
            print(msg)

    return log


def cmd_fill(args) -> int:
    data = _read_json(args.json)
    cfg = load_config(args.config)
    if args.company_accent:
        cfg["style"]["header_values"] = "bold_upper"
    if args.forms:
        cfg["forms"] = [f.strip() for f in args.forms.split(",") if f.strip()]
    log = _default_log(args.quiet)

    print(f"→ Điền biên bản từ {args.json}")
    paths, warnings = render_all(
        data,
        templates_dir=args.templates,
        out_dir=args.out,
        forms=cfg.get("forms"),
        cfg=cfg,
        log=log,
    )
    print()
    for p in paths:
        print(f"  ✔ {p}")
    if warnings:
        print("\nCảnh báo:")
        for w in warnings:
            print(f"  ! {w}")
        return 1
    print(f"\nXong: {len(paths)} biên bản đã được tạo trong {args.out}")
    return 0


def cmd_check(args) -> int:
    data = _read_json(args.json)
    problems = validate(data)
    if not problems:
        print("JSON hợp lệ theo cấu trúc biên bản 44–48.")
        return 0
    print("Phát hiện vấn đề:")
    for p in problems:
        print(f"  - {p.level}: {p.where}: {p.message}")
    return 2 if any(p.level == "error" for p in problems) else 1


def cmd_template(args) -> int:
    payload = {
        "thong_tin_chung": {
            "ten_cong_trinh": "Trạm biến áp 50kVA – DOANH NGHIỆP TƯ NHÂN E-GREEN",
            "dia_chi": "Khu phố Gia Huỳnh, Phường Trảng Bàng, Tỉnh Tây Ninh, Việt Nam",
            "don_vi_yeu_cau": "DOANH NGHIỆP TƯ NHÂN E-GREEN",
            "ly_do_kiem_dinh": "Sau sự cố",
            "noi_kiem_dinh": "Tại hiện trường",
            "ngay_kiem_dinh": "01/11/2026",
            "ngay_lap_bien_ban": "04/11/2026",
            "can_bo_ky_ten": {
                "nguoi_thu": "Nguyễn Trung Nghĩa",
                "nguoi_kiem_tra": "Nguyễn Minh Quân",
                "p_giam_doc": "Nguyễn Nhật Tân",
            },
        },
        "cong_to_dien": {},
        "bien_ban_44_mba": {"so_bien_ban": "50441126/BB-TC"},
        "bien_ban_45_mccb": {"so_bien_ban": "50451126/BB-TC"},
        "bien_ban_46_la": {"so_bien_ban": "50461126/BB-TC"},
        "bien_ban_47_fco": {"so_bien_ban": "50471126/BB-TC"},
        "bien_ban_48_tiep_dat": {"so_bien_ban": "50481126/BB-TC"},
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"Đã ghi khung JSON mẫu vào {args.out}")
    else:
        print(text)
    return 0


def cmd_forms(args) -> int:
    print(f"{'Mã':<4} {'Biên bản':<34} {'Mẫu Word'}")
    for key in sorted(TEMPLATES):
        print(f"{key:<4} {TITLES[key]:<34} templates/{TEMPLATES[key]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bienban",
        description="Tự động điền biên bản kiểm định thiết bị điện lực (mẫu 44–48)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("json", help="file JSON dữ liệu ('-' để đọc từ stdin)")
    common.add_argument("-c", "--config", help="file cấu hình JSON (tuỳ chọn)")
    common.add_argument("-q", "--quiet", action="store_true", help="không in tiến trình")

    f = sub.add_parser("fill", parents=[common], help="sinh file .docx")
    f.add_argument("-o", "--out", default="output", help="thư mục xuất (mặc định: output)")
    f.add_argument("-t", "--templates", default=str(ROOT / "templates"),
                   help="thư mục chứa mẫu Word")
    f.add_argument("--forms", help="chỉ sinh các biên bản này, ví dụ 44,45")
    f.add_argument("--company-accent", action="store_true",
                   help="in đậm + in hoa các biến tiêu đề (Tên công trình, Địa chỉ, Kết luận)")
    f.set_defaults(func=cmd_fill)

    c = sub.add_parser("check", parents=[common], help="kiểm tra JSON trước khi điền")
    c.set_defaults(func=cmd_check)

    t = sub.add_parser("template", help="in khung JSON mẫu")
    t.add_argument("-o", "--out", help="ghi ra file")
    t.set_defaults(func=cmd_template)

    fo = sub.add_parser("forms", help="liệt kê các mẫu biên bản")
    fo.set_defaults(func=cmd_forms)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
