"""Sinh ``prompts/gemini.md`` từ :mod:`bienban.schema`.

Prompt gửi Gemini không được viết tay: nó phải khớp đúng các ô của biểu mẫu.
Sửa ``bienban/schema.py`` rồi chạy::

    python tools/gen_prompt.py

Web UI cũng đọc thẳng từ schema (``GET /api/ai/prompt``) nên hai bên luôn khớp.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bienban.vision import build_prompt  # noqa: E402

HEAD = (
    "<!-- Sinh tự động từ bienban/schema.py — đừng sửa tay.\n"
    "     Chạy lại: python tools/gen_prompt.py -->\n\n"
)


def main() -> int:
    out = ROOT / "prompts" / "gemini.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(HEAD + build_prompt() + "\n", encoding="utf-8")
    print(f"✓ {out.relative_to(ROOT)}  ({len(HEAD + build_prompt())} ký tự)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
