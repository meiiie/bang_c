"""Build the Vietnamese method-writeup slide deck for HackAIthon 2026 Bang C.

Reproducible: `python scripts/build_pptx.py` -> docs/Neko-Core-Thuyet-minh-phuong-phap.pptx
Content mirrors docs/method-writeup-vi.md (measured 88.55 state). python-pptx only.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---- brand palette ----
ORANGE = RGBColor(0xF9, 0x73, 0x16)
ORANGE_DK = RGBColor(0xC2, 0x55, 0x0B)
CREAM = RGBColor(0xFA, 0xF5, 0xEE)
INK = RGBColor(0x1F, 0x29, 0x37)
GRAY = RGBColor(0x6B, 0x72, 0x80)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x15, 0x80, 0x3D)
RED = RGBColor(0xB9, 0x1C, 0x1C)
LIGHT = RGBColor(0xF3, 0xF4, 0xF6)
FONT = "Calibri"

EMU_W, EMU_H = Inches(13.333), Inches(7.5)
prs = Presentation()
prs.slide_width = int(EMU_W)
prs.slide_height = int(EMU_H)
BLANK = prs.slide_layouts[6]


def _set(run, size, color=INK, bold=False, italic=False, font=FONT):
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font


def box(slide, x, y, w, h, fill=None, line=None, line_w=0.75):
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.shadow.inherit = False
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(line_w)
    return sp


def text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=2.0, wrap=True):
    """runs: list of paragraphs; each paragraph is list of (str, size, color, bold, italic)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space); p.space_before = Pt(0)
        if isinstance(para, tuple):
            para = [para]
        for seg in para:
            s, size, color, bold, italic = (seg + (INK, False, False))[:5]
            r = p.add_run(); r.text = s; _set(r, size, color, bold, italic)
    return tb


def header(slide, kicker, title):
    box(slide, 0, 0, 13.333, 7.5, fill=WHITE)              # bg
    box(slide, 0, 0, 0.28, 7.5, fill=ORANGE)               # left accent
    text(slide, 0.7, 0.42, 12, 0.4, [[(kicker.upper(), 12, ORANGE, True, False)]])
    text(slide, 0.7, 0.72, 12.2, 0.9, [[(title, 27, INK, True, False)]])
    box(slide, 0.72, 1.55, 2.0, 0.05, fill=ORANGE)


def table(slide, x, y, w, rows, col_w, header_fill=INK, font_sz=12, head_sz=12, row_h=0.42):
    nrows, ncols = len(rows), len(rows[0])
    gt = slide.shapes.add_table(nrows, ncols, Inches(x), Inches(y), Inches(w), Inches(row_h * nrows)).table
    for j, cw in enumerate(col_w):
        gt.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            c = gt.cell(i, j)
            c.margin_left = Inches(0.08); c.margin_right = Inches(0.06)
            c.margin_top = Inches(0.03); c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            txt, *style = (cell if isinstance(cell, tuple) else (cell,))
            color = style[0] if style else (WHITE if i == 0 else INK)
            bold = style[1] if len(style) > 1 else (i == 0)
            c.fill.solid()
            c.fill.fore_color.rgb = header_fill if i == 0 else (LIGHT if i % 2 == 0 else WHITE)
            p = c.text_frame.paragraphs[0]
            r = p.add_run(); r.text = str(txt)
            _set(r, head_sz if i == 0 else font_sz, color, bold)
    return gt


# ============================ SLIDE 1 — TITLE ============================
s = prs.slides.add_slide(BLANK)
box(s, 0, 0, 13.333, 7.5, fill=INK)
box(s, 0, 0, 13.333, 0.9, fill=ORANGE)
box(s, 0, 6.7, 13.333, 0.8, fill=ORANGE)
text(s, 0.9, 2.25, 11.5, 1.0, [[("NEKO CORE", 50, WHITE, True, False)]])
text(s, 0.9, 3.3, 11.5, 0.7, [[("Harness suy luận config‑first cho AI Agent trắc nghiệm — HackAIthon 2026, Bảng C", 19, CREAM, False, False)]])
text(s, 0.9, 4.25, 11.5, 0.6, [[("Tài liệu thuyết minh phương pháp", 22, ORANGE, True, False)]])
text(s, 0.9, 5.15, 11.5, 1.2, [
    [("Leaderboard đã xác nhận: ", 15, CREAM, False, False), ("88.55", 18, WHITE, True, False),
     ("   ·   Mô hình: Gemma‑4‑26B‑A4B QAT‑Q4_0 (MoE, offline)", 15, CREAM, False, False)],
    [("Đội: ____________   ·   Trường: ____________   ·   Liên hệ: ____________", 12, GRAY, False, True)],
])

# ============================ SLIDE 2 — BÀI TOÁN ============================
s = prs.slides.add_slide(BLANK)
header(s, "01 · Bài toán", "Một Docker offline, tự chứa — đọc /data, ghi /output/pred.csv")
text(s, 0.7, 1.85, 7.4, 3.0, [
    [("Container offline (không web, không API key) đọc ", 14, INK, False, False),
     ("/data/*_test.csv", 14, ORANGE_DK, True, False),
     (", ghi ", 14, INK, False, False), ("/output/pred.csv", 14, ORANGE_DK, True, False),
     (" gồm 2 cột qid,answer (một chữ cái mỗi dòng).", 14, INK, False, False)],
    [("", 6, INK, False, False)],
    [("Chấm trên 2000 câu private đa lĩnh vực / đa ngôn ngữ.", 14, INK, True, False)],
    [("Mô hình cho phép: Gemma‑4 và Qwen3.5 ≤9B.", 13, GRAY, False, False)],
    [("Thí sinh ship Gemma‑4‑26B‑A4B — MoE ~4B active, ~15GB, chạy local llama.cpp.", 13, GRAY, False, False)],
])
table(s, 8.4, 1.95, 4.3, [
    [("Tiêu chí", WHITE, True), ("Điểm", WHITE, True)],
    [("Accuracy", INK, True), ("80đ",)],
    [("Thời gian inference", INK, True), ("10đ",)],
    [("Ý tưởng / tối ưu", INK, True), ("10đ",)],
], [3.0, 1.3], row_h=0.55, font_sz=13, head_sz=13)
text(s, 8.4, 4.7, 4.3, 0.5, [[("← Tài liệu này ăn điểm Ý tưởng", 11, ORANGE_DK, True, True)]])

# ============================ SLIDE 3 — TRIẾT LÝ ============================
s = prs.slides.add_slide(BLANK)
header(s, "02 · Triết lý thiết kế", "Để mô hình suy luận; harness điều phối và ĐO LƯỜNG")
items = [
    ("1 · Mô hình suy luận, harness đo lường", "Không nhồi đáp án/công thức viết tay. Cho mô hình không gian lập luận, rồi đo độ tin cậy."),
    ("2 · Chống overfit bằng thước đo", "Mọi đòn bẩy chỉ ship khi tổng quát hoá — chứng minh bằng đo thật, không phải câu chuyện hợp lý."),
    ("3 · Đo độ bất định thật", "Confidence = mức đồng thuận khi lấy mẫu → harness 'nhìn thấy' chỗ dễ sai, chỉ tốn compute ở đó."),
    ("4 · Ranh giới runtime/dev CỨNG", "Container offline tự chứa. Trace/review/phân tích chỉ ở khâu phát triển, không bao giờ ship."),
]
for i, (t, d) in enumerate(items):
    cx = 0.7 + (i % 2) * 6.15
    cy = 2.0 + (i // 2) * 2.35
    box(s, cx, cy, 5.85, 2.05, fill=CREAM, line=ORANGE, line_w=1.0)
    text(s, cx + 0.3, cy + 0.22, 5.3, 0.6, [[(t, 15, ORANGE_DK, True, False)]])
    text(s, cx + 0.3, cy + 0.85, 5.3, 1.1, [[(d, 12.5, INK, False, False)]])

# ============================ SLIDE 4 — KIẾN TRÚC ============================
s = prs.slides.add_slide(BLANK)
header(s, "03 · Kiến trúc", "Đường ống phân tầng, config‑first (configs/default.json)")
flow = ["/data CSV·JSON", "loader", "router / classifier", "solver (self‑consistency CoT)",
        "answer normalizer", "constrained + contract repair", "/output/pred.csv"]
y = 2.1
for i, stepname in enumerate(flow):
    cy = y + i * 0.66
    fill = ORANGE if i in (3, 6) else CREAM
    tc = WHITE if i in (3, 6) else INK
    box(s, 0.9, cy, 6.2, 0.54, fill=fill, line=ORANGE if fill == CREAM else None, line_w=0.75)
    text(s, 1.15, cy + 0.07, 5.8, 0.42, [[(stepname, 13, tc, i in (3, 6), False)]])
    if i < len(flow) - 1:
        text(s, 3.7, cy + 0.5, 1, 0.2, [[("▼", 10, ORANGE, True, False)]])
box(s, 7.7, 2.1, 5.0, 4.0, fill=LIGHT)
text(s, 7.95, 2.3, 4.6, 3.7, [
    [("Vì sao kiến trúc này 'sáng tạo':", 14, ORANGE_DK, True, False)],
    [("• Tầng provider sau 1 hợp đồng complete() → Gemma/Qwen hoán đổi không sửa solver.", 12.5, INK, False, False)],
    [("• Policy gate + registry chặn khả năng 'chỉ‑dev' lọt vào container thi.", 12.5, INK, False, False)],
    [("• Thêm ngôn ngữ / loại câu = 1 dòng config, không sửa mã.", 12.5, INK, False, False)],
    [("• Trace / review / checkpoint chỉ ở dev — image nộp luôn nhỏ gọn.", 12.5, INK, False, False)],
])

# ============================ SLIDE 5 — HÀNH TRÌNH ACCURACY ============================
s = prs.slides.add_slide(BLANK)
header(s, "04 · Hành trình Accuracy", "Đo trên leaderboard — thước đo duy nhất chúng tôi tin")
bars = [("Letter‑only\n(baseline)", 77.11, GRAY), ("Self‑consistency\nCoT", 87.26, ORANGE), ("+ An‑toàn\ntừ chối", 88.55, GREEN)]
base_y = 5.9; maxh = 3.4; scale = maxh / 90.0
for i, (lbl, val, col) in enumerate(bars):
    bx = 1.5 + i * 3.1
    bh = val * scale
    box(s, bx, base_y - bh, 2.0, bh, fill=col)
    text(s, bx - 0.2, base_y - bh - 0.5, 2.4, 0.4, [[(f"{val}", 22, col, True, False)]], align=PP_ALIGN.CENTER)
    text(s, bx - 0.2, base_y + 0.1, 2.4, 0.7, [[(lbl, 12, INK, False, False)]], align=PP_ALIGN.CENTER)
text(s, 10.6, 2.2, 2.5, 2.0, [
    [("+10.15pp", 18, ORANGE, True, False)],
    [("cho mô hình lập luận", 12, GRAY, False, False)],
    [("", 8, INK, False, False)],
    [("+1.29pp", 18, GREEN, True, False)],
    [("đòn bẩy an‑toàn", 12, GRAY, False, False)],
])
text(s, 1.0, 6.75, 11.5, 0.5, [[("Trần frontier (giải tay, chỉ làm mốc — không ship): 91.79. Phần còn lại = kiến‑thức‑VN + defective gold.", 11.5, GRAY, False, True)]])

# ============================ SLIDE 6 — ĐÒN BẨY THẮNG ============================
s = prs.slides.add_slide(BLANK)
header(s, "05 · Các đòn bẩy thắng", "Sáu kỹ thuật — mỗi cái đo thật, giữ lại cái sinh lời")
levers = [
    ("Chain‑of‑thought", "+10pp. Token lập luận chính là phép tính tạo ra đáp án."),
    ("Self‑consistency", "Bỏ phiếu đa số + confidence = tỉ lệ đồng thuận (thật)."),
    ("An‑toàn‑từ‑chối", "+1.29pp. Phán đoán theo nghĩa, không từ khoá → tổng quát."),
    ("TIR (chạy Python)", "Lát toán ~25‑30%: sandbox offline, vote trên thiết lập bài."),
    ("Constrained decoding", "GBNF grammar ép chữ cái hợp lệ ở lượt sửa → 0 đoán mò."),
    ("Khử thiên lệch vị trí", "Hoán vị xoay vòng lựa chọn (29% câu là 10‑lựa‑chọn)."),
]
for i, (t, d) in enumerate(levers):
    cx = 0.7 + (i % 3) * 4.07
    cy = 2.0 + (i // 3) * 2.25
    box(s, cx, cy, 3.85, 1.95, fill=WHITE, line=ORANGE, line_w=1.0)
    box(s, cx, cy, 3.85, 0.12, fill=ORANGE)
    text(s, cx + 0.25, cy + 0.28, 3.4, 0.6, [[(t, 14, ORANGE_DK, True, False)]])
    text(s, cx + 0.25, cy + 0.85, 3.4, 1.0, [[(d, 11.5, INK, False, False)]])

# ============================ SLIDE 7 — BULLETPROOF CONTRACT ============================
s = prs.slides.add_slide(BLANK)
header(s, "06 · Robustness", "Hợp đồng pred.csv bất khả xâm phạm — chống 0 điểm")
text(s, 0.7, 1.95, 12, 0.6, [[("Lỗi tệ nhất của bài thi: file thiếu/sót = 0 điểm cả 2000 câu. Hai đảm bảo loại bỏ khả năng đó:", 14, INK, False, False)]])
two = [
    ("Mọi câu đều trả lời được", "Exception khi giải được bắt từng‑câu → thay bằng fallback tất định. Một câu lỗi không thể làm sập cả lần chạy."),
    ("Ghi pred.csv TRƯỚC mọi thứ có thể raise", "Bước contract‑repair phủ đúng mọi qid với chữ cái hợp lệ (giữ nguyên dự đoán tốt). Ghi trước, validate chỉ cảnh báo."),
]
for i, (t, d) in enumerate(two):
    cx = 0.7 + i * 6.15
    box(s, cx, 2.75, 5.85, 2.2, fill=CREAM, line=GREEN, line_w=1.25)
    text(s, cx + 0.3, 2.98, 5.3, 0.7, [[("✓ " + t, 15, GREEN, True, False)]])
    text(s, cx + 0.3, 3.75, 5.3, 1.1, [[(d, 12.5, INK, False, False)]])
text(s, 0.7, 5.35, 12, 1.0, [
    [("Đã smoke đúng entrypoint Docker trên GPU thật: pred.csv hợp lệ, contract 40/40 · 211 test đơn vị xanh.", 13, ORANGE_DK, True, False)],
    [("Loader khoan dung input: BOM‑safe, NFC dấu tiếng Việt, tên cột linh hoạt, số lựa chọn động (không gắn cứng A–D).", 12.5, GRAY, False, False)],
])

# ============================ SLIDE 8 — ANTI-OVERFIT (DIFFERENTIATOR) ============================
s = prs.slides.add_slide(BLANK)
header(s, "07 · Kỷ luật chống overfit", "Đã LOẠI gì — và vì sao (mỗi đòn bị một phép ĐO giết)")
table(s, 0.7, 1.9, 12.0, [
    [("Đòn bẩy", WHITE, True), ("Kết quả đo", WHITE, True), ("Vì sao loại", WHITE, True)],
    ["RAG luật/hành chính", ("ÂM", RED, True), "civics −5pp, quant −7.5pp; trắc nghiệm đóng không có corpus để truy xuất."],
    ["maj@k voting (k=5)", ("HOÀ", GRAY, True), "Lỗi Gemma hệ thống → mẫu đa dạng cùng đồng thuận cái SAI."],
    ["Quant cao hơn (Q6/Q8)", ("HOÀ/kém", GRAY, True), "Q4 là QAT (tối ưu sẵn 4‑bit); Q6/Q8 không hơn, 2× thời gian + VRAM."],
    ["Mô hình dense 31B", ("LOẠI (Time)", RED, True), "~90s/câu → ~50h cho 2000 câu, mất trắng 10đ Time; chỉ hơn ~0.7pp."],
    ["Qwen3.5‑9B adjudicator", ("không nhận", GRAY, True), "Standalone kém hơn; vote chéo là tung đồng xu + rủi ro lật câu đúng."],
], [3.1, 1.9, 7.0], row_h=0.78, font_sz=12, head_sz=13)
text(s, 0.7, 6.65, 12, 0.5, [[("Kết quả âm cũng giá trị như kết quả dương — chúng ngăn ta ship tính năng có hại cho 2000 câu private.", 12.5, ORANGE_DK, True, True)]])

# ============================ SLIDE 9 — TỐI ƯU TIME ============================
s = prs.slides.add_slide(BLANK)
header(s, "08 · Tối ưu điểm Time", "MoE + núm token phẳng + MTP lossless")
table(s, 0.7, 2.0, 6.5, [
    [("reasoning_max_tokens", WHITE, True), ("Thời gian 463", WHITE, True)],
    [("768", INK, True), ("21.2 phút",)],
    [("1280", INK, True), ("22.1 phút",)],
    [("2048  (ship)", ORANGE_DK, True), ("22.6 phút",)],
], [4.0, 2.5], row_h=0.52, font_sz=13, head_sz=12)
text(s, 0.7, 4.55, 6.6, 1.6, [
    [("Núm token gần như PHẲNG: 2048 chỉ chậm hơn 768 +6.7% (MoE tự dừng sớm).", 12.5, INK, False, False)],
    [("→ Trần token gần như miễn phí; 2000 câu private chạy ~1.5–1.6h ở mọi mức.", 12.5, INK, True, False)],
])
box(s, 7.6, 2.0, 5.1, 4.2, fill=CREAM, line=ORANGE, line_w=1.0)
text(s, 7.85, 2.25, 4.6, 3.9, [
    [("MTP — Multi‑Token Prediction", 15, ORANGE_DK, True, False)],
    [("Speculative decoding: mô hình phác thảo token, mô hình gốc verify.", 12.5, INK, False, False)],
    [("→ Output GIỐNG HỆT — 0 mất accuracy.", 13, GREEN, True, False)],
    [("→ Nhanh 1.4–2.2× (thuần tốc độ).", 13, GREEN, True, False)],
    [("Trực giao với quant → ship cả hai.", 12.5, INK, False, False)],
    [("Đã hợp nhất llama.cpp; offload GPU xác nhận; đường Docker = provider local_server.", 12, GRAY, False, True)],
])

# ============================ SLIDE 10 — PHÂN TÍCH TRẦN ============================
s = prs.slides.add_slide(BLANK)
header(s, "09 · Phân tích cấu trúc lỗi", "88.55 gần trần thật — và phần gỡ được là TIR, không phải Qwen")
text(s, 0.7, 1.9, 12, 0.6, [[("Phân tích 31 câu mà bản 88.55 khác bản tham chiếu 91.79 (giám định độc lập + phản biện hoài nghi):", 13.5, INK, False, False)]])
stats = [("27/31", "frontier đúng", GRAY), ("16/463", "xác nhận gỡ được", GREEN), ("13", "knowledge‑gap\nkhông gỡ được", RED)]
for i, (n, d, c) in enumerate(stats):
    cx = 0.9 + i * 4.0
    box(s, cx, 2.7, 3.6, 1.5, fill=WHITE, line=c, line_w=1.25)
    text(s, cx, 2.85, 3.6, 0.7, [[(n, 26, c, True, False)]], align=PP_ALIGN.CENTER)
    text(s, cx, 3.55, 3.6, 0.6, [[(d, 12, INK, False, False)]], align=PP_ALIGN.CENTER)
text(s, 0.7, 4.55, 12, 1.8, [
    [("Phần gỡ được là TOÁN/LÝ xác định + suy luận", 14, ORANGE_DK, True, False),
     (" (Henderson‑Hasselbalch, RPM động cơ, eigenvalue, kinh tế‑địa lý)", 13, INK, False, False)],
    [("→ đúng thứ đòn bẩy TIR + CoT (đã xây) nhắm tới — KHÔNG phải thứ adjudicator Qwen mở khoá.", 13.5, INK, True, False)],
    [("13 câu là fact hành chính VN‑2025 / trivia địa phương → xác nhận 88.55 gần trần thật của Gemma offline.", 13, GRAY, False, False)],
    [("Định vị trung thực: chúng tôi báo SỐ ĐO THẬT, không hứa số.", 13.5, GREEN, True, False)],
])

# ============================ SLIDE 11 — BÀI NỘP & REPRODUCE ============================
s = prs.slides.add_slide(BLANK)
header(s, "10 · Bài nộp cuối", "Reproduce trong container — 2 lệnh")
box(s, 0.7, 2.0, 12.0, 1.9, fill=INK)
text(s, 0.95, 2.18, 11.6, 1.7, [
    [("# 1 · kéo image tự chứa (model nướng sẵn bên trong)", 12.5, RGBColor(0x9C,0xA3,0xAF), False, False)],
    [("docker pull hacamy12345/neko-core:gemma26b-q4", 13.5, RGBColor(0x86,0xEF,0xAC), False, False)],
    [("# 2 · chạy trên thư mục chứa public_test.csv / private_test.csv", 12.5, RGBColor(0x9C,0xA3,0xAF), False, False)],
    [("docker run --rm --gpus all -v ./data:/data -v ./out:/output \\", 13.5, RGBColor(0x86,0xEF,0xAC), False, False)],
    [("    hacamy12345/neko-core:gemma26b-q4   →  ./out/pred.csv", 13.5, RGBColor(0x86,0xEF,0xAC), False, False)],
])
text(s, 0.7, 4.25, 12, 2.0, [
    [("Mô hình ship: Gemma‑4‑26B‑A4B QAT‑Q4_0 (MoE ~15GB) — chạy mọi GPU, 0 rủi ro OOM.", 13.5, INK, True, False)],
    [("Đường chạy: self‑consistency CoT (k=1, 2048) + an‑toàn‑từ‑chối + constrained‑repair + contract‑repair, gated TIR.", 13, INK, False, False)],
    [("Leaderboard 88.55. Mọi đòn bẩy âm giữ OFF — anti‑overfit cho 2000 câu private.", 13, GRAY, False, False)],
    [("Tài liệu đầy đủ: docs/method-writeup-vi.md · Code + reproduce: README.md · 211 test xanh.", 12, ORANGE_DK, False, True)],
])

# ============================ SLIDE 12 — KẾT ============================
s = prs.slides.add_slide(BLANK)
box(s, 0, 0, 13.333, 7.5, fill=INK)
box(s, 0, 3.0, 13.333, 0.06, fill=ORANGE)
text(s, 0.9, 2.0, 11.5, 1.0, [[("Mô hình suy luận. Harness đo lường. Số liệu quyết định.", 26, WHITE, True, False)]])
text(s, 0.9, 3.3, 11.5, 1.6, [
    [("Neko Core = ", 16, CREAM, False, False), ("88.55", 18, ORANGE, True, False),
     (" trên leaderboard, hợp đồng pred.csv bất khả xâm phạm, điểm Time bảo vệ bằng MoE + MTP,", 16, CREAM, False, False)],
    [("và một kỷ luật chống overfit đo‑thật cho 2000 câu private.", 16, CREAM, False, False)],
])
text(s, 0.9, 6.4, 11.5, 0.6, [[("HackAIthon 2026 · Bảng C — Innovator", 13, GRAY, False, True)]])

out = Path(__file__).resolve().parents[1] / "docs" / "Neko-Core-Thuyet-minh-phuong-phap.pptx"
prs.save(str(out))
print(f"Wrote {out}  ({len(prs.slides._sldIdLst)} slides)")
