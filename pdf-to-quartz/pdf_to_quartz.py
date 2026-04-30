#!/usr/bin/env python3
"""
pdf_to_quartz.py
Convert PDF → Markdown chuẩn Quartz và tự động đặt vào project.

Usage:
    python pdf_to_quartz.py <file.pdf> --project /path/to/quartz
    python pdf_to_quartz.py *.pdf --project /path/to/quartz
"""

import anthropic
import argparse
import base64
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import fitz  # pymupdf


# ── Cấu hình ──────────────────────────────────────────────────────────────────

CLAUDE_MODEL = "claude-sonnet-4-20250514"
IMAGE_MIN_SIZE = 5_000   # bytes — bỏ qua ảnh thumbnail quá nhỏ
IMAGE_FORMAT  = "webp"

SYSTEM_PROMPT = """Bạn là công cụ chuyển đổi PDF sang Markdown chuẩn Quartz (static site generator).
Nhiệm vụ: nhận nội dung text thô từ PDF và danh sách ảnh, trả về file Markdown hoàn chỉnh.

Quy tắc bắt buộc:
1. Bắt đầu bằng YAML frontmatter: title, date (YYYY-MM-DD), tags (list), draft: false
2. Tiêu đề chính dùng ## (không dùng #)
3. Trích dẫn dài dùng blockquote (>)
4. Footnote dùng cú pháp [^n] và định nghĩa ở cuối file
5. Placeholder ảnh: ![mô tả ngắn](assets/{slug}/{n}.webp) — đặt đúng vị trí xuất hiện trong text
6. Giữ nguyên ngôn ngữ gốc (không dịch)
7. Phân tách nhiều bài trong cùng PDF bằng --- và ghi rõ nguồn gốc bài
8. KHÔNG thêm bất kỳ text giải thích nào ngoài nội dung Markdown
9. Chỉ trả về Markdown thuần, không bọc trong code block"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Chuyển tên file/tiêu đề thành slug an toàn."""
    text = text.lower().strip()
    # Giữ ký tự tiếng Việt có dấu, chỉ xóa ký tự đặc biệt
    text = re.sub(r"[^\w\s\-àáâãèéêìíòóôõùúýăđơư]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:80]


def extract_pdf(pdf_path: Path) -> tuple[str, list[dict]]:
    """
    Trích xuất text và ảnh từ PDF.
    Trả về: (full_text, list of {index, data_b64, ext})
    """
    doc = fitz.open(str(pdf_path))
    pages_text = []
    images_out = []
    seen_xrefs = set()
    img_idx = 1

    for page_num, page in enumerate(doc):
        pages_text.append(f"\n--- Trang {page_num + 1} ---\n")
        pages_text.append(page.get_text("text"))

        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                base_img = doc.extract_image(xref)
                img_bytes = base_img["image"]
                if len(img_bytes) < IMAGE_MIN_SIZE:
                    continue

                images_out.append({
                    "index": img_idx,
                    "page": page_num + 1,
                    "data": img_bytes,
                    "ext": base_img["ext"],
                })
                img_idx += 1
            except Exception:
                pass

    doc.close()
    return "\n".join(pages_text), images_out


def images_to_b64_list(images: list[dict]) -> list[dict]:
    """Encode ảnh sang base64 để gửi Claude."""
    result = []
    for img in images:
        b64 = base64.standard_b64encode(img["data"]).decode()
        result.append({
            "index": img["index"],
            "page": img["page"],
            "b64": b64,
            "ext": img["ext"],
        })
    return result


def call_claude(text: str, images_b64: list[dict], slug: str) -> str:
    """Gửi text + ảnh tới Claude, nhận lại Markdown."""
    client = anthropic.Anthropic()  # đọc ANTHROPIC_API_KEY từ env

    # Xây content message
    content: list = []

    # Thêm ảnh trước (Claude sẽ thấy ảnh theo thứ tự trang)
    for img in images_b64:
        mime = "image/jpeg" if img["ext"] in ("jpg", "jpeg") else f"image/{img['ext']}"
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime,
                "data": img["b64"],
            },
        })

    # Thêm text + hướng dẫn
    img_map = "\n".join(
        f"  - Ảnh {img['index']} (trang {img['page']})" for img in images_b64
    )
    content.append({
        "type": "text",
        "text": (
            f"Slug của file này: {slug}\n"
            f"Danh sách ảnh đã đính kèm phía trên (theo thứ tự):\n{img_map}\n\n"
            f"Nội dung text từ PDF:\n\n{text}"
        ),
    })

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    return response.content[0].text


def save_outputs(
    md_content: str,
    images: list[dict],
    slug: str,
    project_root: Path,
) -> dict:
    """
    Lưu file .md vào content/ và ảnh vào static/assets/{slug}/.
    Trả về dict tóm tắt kết quả.
    """
    content_dir = project_root / "content"
    assets_dir  = project_root / "static" / "assets" / slug

    content_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Lưu Markdown
    md_path = content_dir / f"{slug}.md"
    md_path.write_text(md_content, encoding="utf-8")

    # Lưu ảnh
    saved_imgs = []
    for img in images:
        img_name = f"{img['index']}.{IMAGE_FORMAT}"
        img_path = assets_dir / img_name

        # Convert sang webp nếu cần (dùng pymupdf pixmap)
        if img["ext"].lower() not in ("webp",):
            try:
                pix = fitz.Pixmap(img["data"])
                if pix.n > 4:          # CMYK → RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                pix.save(str(img_path))
            except Exception:
                # Fallback: lưu nguyên định dạng gốc
                img_path = assets_dir / f"{img['index']}.{img['ext']}"
                img_path.write_bytes(img["data"])
        else:
            img_path.write_bytes(img["data"])

        saved_imgs.append(img_path.name)

    return {
        "md": str(md_path),
        "assets_dir": str(assets_dir),
        "images": saved_imgs,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def process_pdf(pdf_path: Path, project_root: Path) -> None:
    pdf_path = Path(pdf_path).expanduser().resolve()
    project_root = Path(project_root).expanduser().resolve()

    if not pdf_path.exists():
        print(f"[LỖI] Không tìm thấy file: {pdf_path}")
        sys.exit(1)

    slug = slugify(pdf_path.stem)
    print(f"\n📄 Xử lý: {pdf_path.name}  →  slug: {slug}")

    # 1. Extract
    print("   ↳ Đang trích xuất text và ảnh từ PDF...")
    text, images = extract_pdf(pdf_path)
    print(f"   ✓ {len(text):,} ký tự | {len(images)} ảnh")

    # 2. Encode ảnh
    images_b64 = images_to_b64_list(images)

    # 3. Gọi Claude
    print("   ↳ Đang gửi sang Claude để format Markdown...")
    md_content = call_claude(text, images_b64, slug)
    print(f"   ✓ Nhận về {len(md_content):,} ký tự Markdown")

    # 4. Lưu
    print("   ↳ Đang lưu vào project...")
    result = save_outputs(md_content, images, slug, project_root)

    print(f"   ✓ Markdown : {result['md']}")
    print(f"   ✓ Ảnh ({len(result['images'])}): {result['assets_dir']}/")
    print("   🎉 Xong!\n")


def main():
    parser = argparse.ArgumentParser(
        description="Chuyển PDF → Markdown chuẩn Quartz"
    )
    parser.add_argument(
        "pdfs",
        nargs="+",
        help="Đường dẫn tới file PDF (hỗ trợ nhiều file)",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Đường dẫn tới thư mục gốc của Quartz project",
    )
    args = parser.parse_args()

    project_root = Path(args.project).expanduser().resolve()
    if not project_root.exists():
        print(f"[LỖI] Không tìm thấy project: {project_root}")
        sys.exit(1)

    for pdf in args.pdfs:
        process_pdf(Path(pdf), project_root)


if __name__ == "__main__":
    main()
