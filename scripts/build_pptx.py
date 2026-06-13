"""Build the Vietnamese method-writeup slide deck for HackAIthon 2026 Bang C.

Reproducible: `python scripts/build_pptx.py` -> docs/Neko-Core-Thuyet-minh-phuong-phap.pptx

Design follows the assertion-evidence method (Michael Alley, Penn State): every slide
headline is a full-sentence ASSERTION (the takeaway), the body is visual evidence, bullets
are minimized. Content mirrors docs/method-writeup-vi.md (measured 88.55 state). python-pptx only.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
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
CODEBG = RGBColor(0x11, 0x18, 0x27)
FONT = "Calibri"

prs = Presentation()
prs.slide_width = int(Inches(13.333))
prs.slide_height = int(Inches(7.5))
BLANK = prs.slide_layouts[6]


def _set(run, size, color=INK, bold=False, italic=False, font=FONT):
    run.font.size = Pt(size); run.font.color.rgb = color
    run.font.bold = bold; run.font.italic = italic; run.font.name = font


def box(slide, x, y, w, h, fill=None, line=None, line_w=0.75, shape=MSO_SHAPE.RECTANGLE):
    sp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
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


def text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=3.0, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = wrap; tf.vertical_anchor = anchor
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space); p.space_before = Pt(0)
        if isinstance(para, tuple):
            para = [para]
        for seg in para:
            s, size, color, bold, italic = (seg + (INK, False, False))[:5]
            r = p.add_run(); r.text = s; _set(r, size, color, bold, italic)
    return tb


def header(slide, kicker, assertion):
    """Assertion-evidence header: small section kicker + a full-sentence assertion headline."""
    box(slide, 0, 0, 13.333, 7.5, fill=WHITE)
    box(slide, 0, 0, 13.333, 0.16, fill=ORANGE)
    text(slide, 0.7, 0.46, 12.0, 0.35, [[(kicker.upper(), 11, ORANGE, True, False)]])
    text(slide, 0.7, 0.78, 12.2, 1.1, [[(assertion, 23, INK, True, False)]])


def table(slide, x, y, w, rows, col_w, header_fill=INK, font_sz=12, head_sz=12, row_h=0.42):
    nrows, ncols = len(rows), len(rows[0])
    gt = slide.shapes.add_table(nrows, ncols, Inches(x), Inches(y), Inches(w), Inches(row_h * nrows)).table
    for j, cw in enumerate(col_w):
        gt.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            c = gt.cell(i, j)
            c.margin_left = Inches(0.1); c.margin_right = Inches(0.06)
            c.margin_top = Inches(0.02); c.margin_bottom = Inches(0.02)
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


def page_no(slide, n):
    text(slide, 12.4, 7.05, 0.8, 0.3, [[(str(n), 10, GRAY, False, False)]], align=PP_ALIGN.RIGHT)


# ============================ 1 · COVER ============================
s = prs.slides.add_slide(BLANK)
box(s, 0, 0, 13.333, 7.5, fill=INK)
box(s, 0, 0, 13.333, 0.9, fill=ORANGE)
box(s, 0, 6.7, 13.333, 0.8, fill=ORANGE)
text(s, 0.9, 2.2, 11.5, 1.0, [[("NEKO CORE", 52, WHITE, True, False)]])
text(s, 0.9, 3.3, 11.6, 0.7, [[("AI Agent trắc nghiệm offline — thắng bằng kỷ luật đo‑thật, không bằng mô hình to hơn", 18, CREAM, False, False)]])
text(s, 0.9, 4.25, 11.5, 0.6, [[("Tài liệu thuyết minh phương pháp · HackAIthon 2026 — Bảng C (Innovator)", 17, ORANGE, True, False)]])
text(s, 0.9, 5.2, 11.5, 1.1, [
    [("Leaderboard: ", 15, CREAM, False, False), ("88.55", 19, WHITE, True, False),
     ("   ·   Mô hình: Gemma‑4‑26B‑A4B QAT‑Q4_0 (MoE ~15GB, offline)", 15, CREAM, False, False)],
    [("Đội: ____________   ·   Trường: ____________   ·   Liên hệ: ____________", 12, RGBColor(0xC9,0xCE,0xD6), False, True)],
])

# ============================ 2 · TÓM TẮT (exec summary) ============================
s = prs.slides.add_slide(BLANK)
header(s, "Tóm tắt", "Một Gemma offline 15GB đạt 88.55 nhờ ba thế mạnh — không phải nhờ mô hình lớn hơn.")
cards = [
    ("Engine đo‑thật", "Self‑consistency CoT đưa accuracy 77.11 → 88.55 trên leaderboard. Mỗi đòn bẩy chỉ giữ khi đo được nó sinh lời.", ORANGE),
    ("Bất khả xâm phạm", "Hợp đồng pred.csv: một câu lỗi không thể làm mất trắng 2000 câu. Retry → fallback → checkpoint‑resume ba lớp.", GREEN),
    ("Nhanh & khả thi", "MoE ~4B active + núm token phẳng → 2000 câu ~1.5h, điểm Time an toàn. MTP lossless để dành tăng tốc 1.4–2.2×.", INK),
]
for i, (t, d, c) in enumerate(cards):
    cx = 0.7 + i * 4.07
    box(s, cx, 2.2, 3.85, 3.6, fill=WHITE, line=c, line_w=1.5)
    box(s, cx, 2.2, 3.85, 0.16, fill=c)
    text(s, cx + 0.28, 2.55, 3.35, 0.7, [[(t, 17, c if c != INK else ORANGE_DK, True, False)]])
    text(s, cx + 0.28, 3.35, 3.35, 2.3, [[(d, 13, INK, False, False)]])
text(s, 0.7, 6.1, 12, 0.6, [[("Định vị trung thực: 88.55 là gần trần thật của một Gemma offline; phần còn lại là kiến‑thức‑VN không retrieval được. Chúng tôi báo số đo thật, không hứa số.", 12.5, GRAY, False, True)]])
page_no(s, 2)

# ============================ 3 · BÀI TOÁN ============================
s = prs.slides.add_slide(BLANK)
header(s, "01 · Bài toán", "Chấm 2000 câu private theo Accuracy 80 / Time 10 / Ý tưởng 10 — nên mọi đòn bẩy phải TỔNG QUÁT HOÁ.")
text(s, 0.7, 2.1, 7.3, 3.0, [
    [("Container ", 14, INK, False, False), ("offline, tự chứa", 14, ORANGE_DK, True, False),
     (" (không web, không API key) đọc ", 14, INK, False, False),
     ("/data/*_test.csv", 14, ORANGE_DK, True, False), (" → ghi ", 14, INK, False, False),
     ("/output/pred.csv", 14, ORANGE_DK, True, False), (" (qid,answer).", 14, INK, False, False)],
    [("", 8, INK, False, False)],
    [("Bộ private đa lĩnh vực / đa ngôn ngữ → bất cứ thứ gì gắn cứng vào một câu hay một ngôn ngữ là gánh nặng, sẽ bị loại bỏ hoặc tổng quát hoá qua config.", 14, INK, False, False)],
])
table(s, 8.3, 2.2, 4.4, [
    [("Tiêu chí Vòng‑2", WHITE, True), ("Điểm", WHITE, True)],
    [("Accuracy", INK, True), ("80đ",)],
    [("Thời gian inference", INK, True), ("10đ",)],
    [("Ý tưởng / tối ưu", ORANGE_DK, True), ("10đ ←",)],
], [3.1, 1.3], row_h=0.6, font_sz=13, head_sz=13)
text(s, 8.3, 5.0, 4.4, 0.4, [[("Tài liệu này ăn điểm Ý tưởng.", 11.5, ORANGE_DK, True, True)]])
page_no(s, 3)

# ============================ 4 · TRIẾT LÝ ============================
s = prs.slides.add_slide(BLANK)
header(s, "02 · Triết lý", "Để mô hình SUY LUẬN; harness chỉ điều phối và ĐO LƯỜNG.")
items = [
    ("Mô hình suy luận, harness đo", "Không nhồi đáp án/công thức viết tay — cho mô hình không gian lập luận rồi đo độ tin cậy."),
    ("Chống overfit bằng thước đo", "Một đòn bẩy chỉ ship khi tổng quát hoá, chứng minh bằng đo thật — không phải bằng một câu chuyện hợp lý."),
    ("Đo độ bất định thật", "Confidence = mức đồng thuận khi lấy mẫu → harness 'nhìn thấy' chỗ dễ sai, chỉ tốn compute ở đó."),
    ("Ranh giới runtime/dev cứng", "Container offline tự chứa; trace/review/phân tích chỉ ở dev, không bao giờ ship."),
]
for i, (t, d) in enumerate(items):
    cx = 0.7 + (i % 2) * 6.15
    cy = 2.25 + (i // 2) * 2.2
    box(s, cx, cy, 5.85, 1.95, fill=CREAM)
    box(s, cx, cy, 0.1, 1.95, fill=ORANGE)
    text(s, cx + 0.35, cy + 0.25, 5.3, 0.55, [[(f"{i+1} · {t}", 15, ORANGE_DK, True, False)]])
    text(s, cx + 0.35, cy + 0.82, 5.3, 1.0, [[(d, 12.5, INK, False, False)]])
page_no(s, 4)

# ============================ 5 · KIẾN TRÚC ============================
s = prs.slides.add_slide(BLANK)
header(s, "03 · Kiến trúc", "Một đường ống config‑first: thêm ngôn ngữ hay loại câu chỉ tốn MỘT dòng config.")
flow = ["/data CSV·JSON", "loader", "router / classifier", "solver — self‑consistency CoT",
        "answer normalizer", "constrained + contract repair", "/output/pred.csv"]
for i, step in enumerate(flow):
    cy = 2.2 + i * 0.62
    hot = i in (3, 6)
    box(s, 0.9, cy, 6.0, 0.5, fill=ORANGE if hot else CREAM)
    text(s, 1.15, cy + 0.06, 5.6, 0.4, [[(step, 13, WHITE if hot else INK, hot, False)]])
    if i < len(flow) - 1:
        text(s, 3.55, cy + 0.46, 1, 0.2, [[("▼", 9, ORANGE, True, False)]])
box(s, 7.5, 2.2, 5.2, 3.9, fill=LIGHT)
box(s, 7.5, 2.2, 5.2, 0.12, fill=INK)
text(s, 7.78, 2.45, 4.7, 3.6, [
    [("Vì sao thiết kế này thắng:", 14, ORANGE_DK, True, False)],
    [("Một hợp đồng complete() duy nhất → Gemma/Qwen hoán đổi, không sửa solver.", 12.5, INK, False, False)],
    [("Policy gate + registry → không khả năng 'chỉ‑dev' nào lọt vào container thi.", 12.5, INK, False, False)],
    [("Trace/review/checkpoint chỉ ở dev → image nộp luôn nhỏ gọn, tái lập.", 12.5, INK, False, False)],
])
page_no(s, 5)

# ============================ 6 · HÀNH TRÌNH ACCURACY ============================
s = prs.slides.add_slide(BLANK)
header(s, "04 · Kết quả", "Cho mô hình lập luận đưa accuracy 77.11 → 88.55 — đo thật trên leaderboard.")
bars = [("Letter‑only\n(baseline)", 77.11, GRAY), ("Self‑consistency\nCoT", 87.26, ORANGE), ("+ An‑toàn\ntừ chối", 88.55, GREEN)]
base_y = 6.0; scale = 3.3 / 90.0
for i, (lbl, val, col) in enumerate(bars):
    bx = 1.4 + i * 2.9
    bh = val * scale
    box(s, bx, base_y - bh, 1.9, bh, fill=col)
    text(s, bx - 0.25, base_y - bh - 0.5, 2.4, 0.4, [[(f"{val}", 23, col, True, False)]], align=PP_ALIGN.CENTER)
    text(s, bx - 0.25, base_y + 0.1, 2.4, 0.7, [[(lbl, 12, INK, False, False)]], align=PP_ALIGN.CENTER)
text(s, 10.3, 2.35, 2.8, 3.0, [
    [("+10.15pp", 19, ORANGE, True, False)],
    [("cho mô hình lập luận (CoT)", 12, GRAY, False, False)],
    [("", 10, INK, False, False)],
    [("+1.29pp", 19, GREEN, True, False)],
    [("đòn bẩy an‑toàn‑từ‑chối", 12, GRAY, False, False)],
])
text(s, 0.9, 6.7, 11.8, 0.4, [[("Mốc trần frontier (giải tay, chỉ làm tham chiếu — không ship): 91.79. Phần còn lại = kiến‑thức‑VN + defective gold.", 11.5, GRAY, False, True)]])
page_no(s, 6)

# ============================ 7 · ĐÒN BẨY ============================
s = prs.slides.add_slide(BLANK)
header(s, "05 · Phương pháp", "Sáu đòn bẩy — mỗi cái được giữ lại vì ĐO ĐƯỢC nó sinh lời.")
levers = [
    ("Chain‑of‑thought", "+10pp. Token lập luận chính là phép tính tạo ra đáp án."),
    ("Self‑consistency", "Bỏ phiếu đa số + confidence = tỉ lệ đồng thuận (thật)."),
    ("An‑toàn‑từ‑chối", "+1.29pp. Phán đoán theo nghĩa, không từ khoá → tổng quát."),
    ("TIR — chạy Python", "Lát toán ~25‑30%: sandbox offline, vote trên thiết lập bài."),
    ("Constrained decoding", "GBNF grammar ép chữ cái hợp lệ ở lượt sửa → 0 đoán mò."),
    ("Khử thiên lệch vị trí", "Hoán vị xoay vòng lựa chọn (29% câu là 10‑lựa‑chọn)."),
]
for i, (t, d) in enumerate(levers):
    cx = 0.7 + (i % 3) * 4.07
    cy = 2.25 + (i // 3) * 2.15
    box(s, cx, cy, 3.85, 1.85, fill=WHITE, line=LIGHT, line_w=1.0)
    box(s, cx, cy, 3.85, 0.1, fill=ORANGE)
    text(s, cx + 0.25, cy + 0.25, 3.4, 0.5, [[(t, 14, ORANGE_DK, True, False)]])
    text(s, cx + 0.25, cy + 0.8, 3.4, 1.0, [[(d, 11.5, INK, False, False)]])
page_no(s, 7)

# ============================ 8 · BULLETPROOF ============================
s = prs.slides.add_slide(BLANK)
header(s, "06 · Robustness", "pred.csv không bao giờ trống: một câu lỗi không thể làm mất trắng 2000 câu.")
two = [
    ("Mọi câu đều có đáp án", "Exception khi giải được bắt từng‑câu → thay bằng fallback tất định. Một câu lỗi không thể làm sập cả lần chạy."),
    ("Ghi pred.csv TRƯỚC mọi thứ có thể lỗi", "contract‑repair phủ đúng mọi qid với chữ cái hợp lệ (giữ nguyên dự đoán tốt); ghi trước, validate chỉ cảnh báo."),
]
for i, (t, d) in enumerate(two):
    cx = 0.7 + i * 6.15
    box(s, cx, 2.25, 5.85, 2.0, fill=CREAM, line=GREEN, line_w=1.5)
    text(s, cx + 0.3, 2.48, 5.3, 0.6, [[("✓ " + t, 15, GREEN, True, False)]])
    text(s, cx + 0.3, 3.2, 5.3, 1.0, [[(d, 12.5, INK, False, False)]])
text(s, 0.7, 4.55, 12, 0.4, [[("Tự động tiếp tục khi gặp sự cố — ba lớp:", 14, INK, True, False)]])
text(s, 0.9, 5.0, 12, 1.4, [
    [("①  Retry từng câu", 13, ORANGE_DK, True, False), ("  — lỗi tạm thời (timeout/connection) thử lại với backoff lũy thừa.", 12.5, INK, False, False)],
    [("②  Fallback từng câu", 13, ORANGE_DK, True, False), ("  — lỗi bất kỳ → đáp án heuristic tất định, không crash.", 12.5, INK, False, False)],
    [("③  Checkpoint + auto‑resume", 13, ORANGE_DK, True, False), ("  — container restart → tiếp tục từ câu cuối, không tính lại (cứu cả Time).", 12.5, INK, False, False)],
])
text(s, 0.7, 6.55, 12, 0.4, [[("Đã smoke đúng entrypoint Docker trên GPU thật: pred.csv hợp lệ, contract 40/40 · 211 test đơn vị xanh.", 11.5, GRAY, False, True)]])
page_no(s, 8)

# ============================ 9 · ANTI-OVERFIT ============================
s = prs.slides.add_slide(BLANK)
header(s, "07 · Kỷ luật", "Chúng tôi LOẠI nhiều đòn bẩy hơn là giữ — mỗi cái bị một phép ĐO giết.")
table(s, 0.7, 2.15, 12.0, [
    [("Đòn bẩy đã thử", WHITE, True), ("Kết quả đo", WHITE, True), ("Vì sao loại", WHITE, True)],
    ["RAG luật/hành chính", ("ÂM", RED, True), "civics −5pp, quant −7.5pp; trắc nghiệm đóng không có corpus để truy xuất."],
    ["maj@k voting (k=5)", ("HOÀ", GRAY, True), "Lỗi Gemma hệ thống → các mẫu đa dạng cùng đồng thuận cái SAI."],
    ["Quant cao hơn (Q6/Q8)", ("HOÀ/kém", GRAY, True), "Q4 là QAT (tối ưu sẵn 4‑bit); Q6/Q8 không hơn, 2× thời gian + VRAM."],
    ["Mô hình dense 31B", ("LOẠI: Time", RED, True), "~90s/câu → ~50h cho 2000 câu, mất trắng 10đ Time; chỉ hơn ~0.7pp."],
    ["Qwen3.5‑9B adjudicator", ("không nhận", GRAY, True), "Standalone kém hơn; vote chéo là tung đồng xu + rủi ro lật câu đang đúng."],
], [3.1, 1.95, 6.95], row_h=0.75, font_sz=12, head_sz=13)
text(s, 0.7, 6.85, 12, 0.4, [[("Kết quả âm cũng giá trị như kết quả dương — chúng ngăn ta ship tính năng có hại cho 2000 câu private.", 12.5, ORANGE_DK, True, True)]])
page_no(s, 9)

# ============================ 10 · TIME ============================
s = prs.slides.add_slide(BLANK)
header(s, "08 · Điểm Time", "Điểm Time an toàn ở độ sâu suy luận tối đa: núm token gần như PHẲNG.")
table(s, 0.7, 2.3, 6.4, [
    [("reasoning_max_tokens", WHITE, True), ("Thời gian 463 câu", WHITE, True)],
    [("768", INK, True), ("21.2 phút",)],
    [("1280", INK, True), ("22.1 phút",)],
    [("2048  (ship)", ORANGE_DK, True), ("22.6 phút",)],
], [3.9, 2.5], row_h=0.55, font_sz=13, head_sz=12)
text(s, 0.7, 4.9, 6.6, 1.5, [
    [("2048 chỉ chậm hơn 768 ", 12.5, INK, False, False), ("+6.7%", 13, ORANGE_DK, True, False),
     (" (MoE tự dừng sớm) → trần token gần như miễn phí.", 12.5, INK, False, False)],
    [("2000 câu private chạy ~1.5–1.6h ở mọi mức.", 12.5, INK, True, False)],
])
box(s, 7.5, 2.3, 5.2, 4.0, fill=CREAM, line=ORANGE, line_w=1.25)
text(s, 7.78, 2.55, 4.7, 3.7, [
    [("MTP — Multi‑Token Prediction", 15, ORANGE_DK, True, False)],
    [("Mô hình phác thảo token, mô hình gốc verify → output GIỐNG HỆT.", 12.5, INK, False, False)],
    [("→ 0 mất accuracy.", 13.5, GREEN, True, False)],
    [("→ Nhanh 1.4–2.2× (thuần tốc độ).", 13.5, GREEN, True, False)],
    [("Trực giao với quant → ship cả hai; đường Docker = provider local_server.", 12, GRAY, False, True)],
])
page_no(s, 10)

# ============================ 11 · TRẦN ============================
s = prs.slides.add_slide(BLANK)
header(s, "09 · Định vị", "88.55 là gần trần thật của Gemma offline — phần gỡ được là TOÁN (TIR), không phải kiến thức.")
stats = [("27/31", "frontier đúng\n(Gemma sai thật)", GRAY), ("16/463", "xác nhận gỡ được\n(toán + suy luận)", GREEN), ("13", "knowledge‑gap\nkhông gỡ được", RED)]
for i, (n, d, c) in enumerate(stats):
    cx = 0.9 + i * 4.0
    box(s, cx, 2.4, 3.6, 1.7, fill=WHITE, line=c, line_w=1.5)
    text(s, cx, 2.55, 3.6, 0.7, [[(n, 27, c, True, False)]], align=PP_ALIGN.CENTER)
    text(s, cx, 3.3, 3.6, 0.7, [[(d, 11.5, INK, False, False)]], align=PP_ALIGN.CENTER)
text(s, 0.7, 4.5, 12, 1.9, [
    [("Phần gỡ được là TOÁN/LÝ xác định + suy luận", 14, ORANGE_DK, True, False),
     (" (Henderson‑Hasselbalch, RPM động cơ, eigenvalue, kinh tế‑địa lý)…", 13, INK, False, False)],
    [("→ đúng thứ đòn bẩy TIR + CoT (đã xây) nhắm tới — KHÔNG phải thứ một adjudicator Qwen mở khoá.", 13.5, INK, True, False)],
    [("13 câu là fact hành chính VN‑2025 / trivia địa phương → không mô hình hợp lệ nào phá được rẻ.", 13, GRAY, False, False)],
    [("Chúng tôi báo SỐ ĐO THẬT, không hứa số.", 14, GREEN, True, False)],
])
page_no(s, 11)

# ============================ 12 · REPRODUCE ============================
s = prs.slides.add_slide(BLANK)
header(s, "10 · Bài nộp", "Tái lập kết quả trong container chỉ với HAI lệnh.")
box(s, 0.7, 2.2, 12.0, 1.95, fill=CODEBG)
text(s, 0.95, 2.4, 11.6, 1.75, [
    [("# 1 · kéo image tự chứa (model nướng sẵn bên trong)", 12.5, RGBColor(0x9C, 0xA3, 0xAF), False, False)],
    [("docker pull hacamy12345/neko-core:gemma26b-q4", 13.5, RGBColor(0x86, 0xEF, 0xAC), False, False)],
    [("# 2 · chạy trên thư mục chứa public_test.csv / private_test.csv", 12.5, RGBColor(0x9C, 0xA3, 0xAF), False, False)],
    [("docker run --rm --gpus all -v ./data:/data -v ./out:/output \\", 13.5, RGBColor(0x86, 0xEF, 0xAC), False, False)],
    [("    hacamy12345/neko-core:gemma26b-q4   →  ./out/pred.csv", 13.5, RGBColor(0x86, 0xEF, 0xAC), False, False)],
])
text(s, 0.7, 4.45, 12, 1.9, [
    [("Mô hình ship: Gemma‑4‑26B‑A4B QAT‑Q4_0 (MoE ~15GB) — chạy mọi GPU, 0 rủi ro OOM.", 13.5, INK, True, False)],
    [("Đường chạy: self‑consistency CoT (k=1, 2048) + an‑toàn‑từ‑chối + constrained‑repair + contract‑repair, gated TIR.", 13, INK, False, False)],
    [("Code + reproduce: README.md · Tài liệu đầy đủ: docs/method-writeup-vi.md · 211 test xanh.", 12, ORANGE_DK, False, True)],
])
page_no(s, 12)

# ============================ 13 · KẾT ============================
s = prs.slides.add_slide(BLANK)
box(s, 0, 0, 13.333, 7.5, fill=INK)
box(s, 0, 3.05, 13.333, 0.06, fill=ORANGE)
text(s, 0.9, 2.0, 11.5, 1.0, [[("Mô hình suy luận. Harness đo lường. Số liệu quyết định.", 27, WHITE, True, False)]])
text(s, 0.9, 3.4, 11.5, 1.6, [
    [("88.55 trên leaderboard · hợp đồng pred.csv bất khả xâm phạm · điểm Time bảo vệ bằng MoE + MTP", 16, CREAM, False, False)],
    [("· và một kỷ luật chống overfit đo‑thật cho 2000 câu private.", 16, CREAM, False, False)],
])
text(s, 0.9, 6.4, 11.5, 0.5, [[("Neko Core — HackAIthon 2026 · Bảng C (Innovator)", 13, GRAY, False, True)]])

out = Path(__file__).resolve().parents[1] / "docs" / "Neko-Core-Thuyet-minh-phuong-phap.pptx"
try:
    prs.save(str(out))
except PermissionError:
    out = out.with_name("Neko-Core-Thuyet-minh-phuong-phap-new.pptx")
    prs.save(str(out))
    print("(canonical file was locked/open — wrote -new variant)")
print(f"Wrote {out}  ({len(prs.slides._sldIdLst)} slides)")
