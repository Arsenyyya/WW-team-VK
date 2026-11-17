"""Render every final PDF page and make contact sheets for visual review."""

import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

from vk_case.pipeline import latest

root = Path(__file__).resolve().parents[1]
run = latest(root/"outputs")
out = root/"qa/pdf_preview"
out.mkdir(parents=True, exist_ok=True)
summary = []
paths = [run/"slides/strategy_draft.pdf", run/"reports/report.pdf", run/"reports/appendix.pdf"]
for path in paths:
    doc = fitz.open(path)
    page_dir = out/path.stem
    page_dir.mkdir(exist_ok=True)
    for old in page_dir.glob("page-*.png"):
        old.unlink()
    thumbs = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
        pix.save(str(page_dir/f"page-{i+1:02}.png"))
        image = Image.open(page_dir/f"page-{i+1:02}.png").convert("RGB")
        image.thumbnail((440, 540))
        thumb = Image.new("RGB", (460, 570), "#DFE6EF")
        thumb.paste(image, ((460-image.width)//2, 12))
        ImageDraw.Draw(thumb).text((14, 548), f"{path.stem} / {i+1}", fill="#15263E")
        thumbs.append(thumb)
    for start in range(0, len(thumbs), 12):
        chunk = thumbs[start:start+12]
        contact = Image.new("RGB", (460*3, 570*((len(chunk)+2)//3)), "#DFE6EF")
        for j, thumb in enumerate(chunk):
            contact.paste(thumb, ((j%3)*460, (j//3)*570))
        contact.save(out/f"{path.stem}-contact-{start//12+1}.png")
    extracted = "\n".join(p.get_text() for p in doc)
    summary.append({"file": str(path.relative_to(root)), "pages": len(doc),
                    "all_pages_rendered": True, "has_cyrillic": "заказ" in extracted.lower(),
                    "replacement_characters": extracted.count("\ufffd")})
source_doc = fitz.open(root/"data/raw/case.pdf")
source_doc[13].get_pixmap(matrix=fitz.Matrix(1.3, 1.3)).save(out/"source-case-page14.png")
(out/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps(summary, ensure_ascii=False, indent=2))
