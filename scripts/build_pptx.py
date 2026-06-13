"""Build the Vietnamese method-writeup slide deck for HackAIthon 2026 Bang C.

Reproducible: `python scripts/build_pptx.py` -> docs/Neko-Core-Thuyet-minh-phuong-phap.pptx

Layout follows the assertion-evidence method (Michael Alley): each slide headline is a
full sentence, the body is visual evidence. Copy register: academic / technical Vietnamese
(measured tone, precise terminology, minimal emphasis caps and arrows). Content mirrors
docs/method-writeup-vi.md (measured 88.55 state). python-pptx only.
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
    box(slide, 0, 0, 13.333, 7.5, fill=WHITE)
    box(slide, 0, 0, 13.333, 0.16, fill=ORANGE)
    text(slide, 0.7, 0.46, 12.0, 0.35, [[(kicker, 11, ORANGE, True, False)]])
    text(slide, 0.7, 0.78, 12.2, 1.1, [[(assertion, 22, INK, True, False)]])


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
text(s, 0.9, 3.3, 11.6, 0.7, [[("Hệ thống suy luận trắc nghiệm vận hành ngoại tuyến, tối ưu theo phương pháp luận đo lường thực nghiệm", 17, CREAM, False, False)]])
text(s, 0.9, 4.3, 11.5, 0.6, [[("Tài liệu thuyết minh phương pháp · HackAIthon 2026 — Bảng C (Innovator)", 16, ORANGE, True, False)]])
text(s, 0.9, 5.25, 11.5, 1.1, [
    [("Kết quả leaderboard: ", 15, CREAM, False, False), ("88.55", 18, WHITE, True, False),
     ("   ·   Mô hình: Gemma‑4‑26B‑A4B QAT‑Q4_0 (kiến trúc MoE, ~15GB, ngoại tuyến)", 14, CREAM, False, False)],
    [("Đội: ____________   ·   Trường: ____________   ·   Liên hệ: ____________", 12, RGBColor(0xC9, 0xCE, 0xD6), False, True)],
])

# ============================ 2 · TÓM TẮT ============================
s = prs.slides.add_slide(BLANK)
header(s, "Tóm tắt", "Mô hình Gemma‑4 ngoại tuyến (~15GB) đạt 88.55 nhờ ba trụ cột phương pháp.")
cards = [
    ("Suy luận tự nhất quán", "Cơ chế chain‑of‑thought tự nhất quán nâng độ chính xác từ 77.11 lên 88.55 (đo trên leaderboard). Mỗi cải tiến chỉ được giữ lại sau khi đo lường xác nhận hiệu quả.", ORANGE),
    ("Bảo đảm tính toàn vẹn", "Hợp đồng đầu ra bảo đảm tệp pred.csv luôn hợp lệ; một lỗi cục bộ không làm mất toàn bộ kết quả. Ba lớp phục hồi: thử lại, dự phòng và khôi phục theo checkpoint.", GREEN),
    ("Hiệu năng và khả thi", "Kiến trúc MoE (~4B tham số kích hoạt) hoàn tất 2000 câu trong khoảng 1,5 giờ, bảo đảm điểm thời gian. Kỹ thuật MTP tăng tốc 1,4–2,2 lần mà không suy giảm độ chính xác.", INK),
]
for i, (t, d, c) in enumerate(cards):
    cx = 0.7 + i * 4.07
    ch = 3.15
    tc = c if c != INK else ORANGE_DK
    box(s, cx, 2.25, 3.85, ch, fill=WHITE, line=c, line_w=1.5)
    box(s, cx, 2.25, 3.85, 0.16, fill=c)
    text(s, cx + 0.32, 2.45, 3.25, ch - 0.35,
         [[(t, 16, tc, True, False)], [("", 9, INK, False, False)], [(d, 12.5, INK, False, False)]],
         anchor=MSO_ANCHOR.MIDDLE, space=4.0)
text(s, 0.7, 6.05, 12, 0.7, [[("Định vị khách quan: 88.55 tiệm cận giới hạn thực tế của một mô hình Gemma ngoại tuyến; phần sai số còn lại chủ yếu thuộc tri thức đặc thù không truy hồi được. Tài liệu trình bày số liệu đo được, không cam kết số liệu chưa kiểm chứng.", 12, GRAY, False, True)]])
page_no(s, 2)

# ============================ 3 · BÀI TOÁN ============================
s = prs.slides.add_slide(BLANK)
header(s, "01 · Bài toán", "Bài toán yêu cầu tổng quát hóa trên 2000 câu hỏi đa lĩnh vực; chấm theo Độ chính xác 80, Thời gian 10, Ý tưởng 10.")
text(s, 0.7, 2.25, 7.3, 3.0, [
    [("Hệ thống được đóng gói trong một container ", 14, INK, False, False),
     ("ngoại tuyến, tự chứa", 14, ORANGE_DK, True, False),
     (" (không truy cập mạng, không cần khóa API), đọc tệp ", 14, INK, False, False),
     ("/data/*_test.csv", 14, ORANGE_DK, True, False), (" và ghi kết quả ra ", 14, INK, False, False),
     ("/output/pred.csv", 14, ORANGE_DK, True, False), (" với hai cột qid, answer.", 14, INK, False, False)],
    [("", 8, INK, False, False)],
    [("Do tập kiểm thử đa lĩnh vực và đa ngôn ngữ, mọi kỹ thuật gắn cứng với một câu hỏi hay một ngôn ngữ cụ thể đều bị loại bỏ hoặc tổng quát hóa thông qua cấu hình.", 14, INK, False, False)],
])
table(s, 8.3, 2.35, 4.4, [
    [("Tiêu chí Vòng 2", WHITE, True), ("Điểm", WHITE, True)],
    [("Độ chính xác", INK, True), ("80",)],
    [("Thời gian inference", INK, True), ("10",)],
    [("Ý tưởng / tối ưu", ORANGE_DK, True), ("10",)],
], [3.1, 1.3], row_h=0.6, font_sz=13, head_sz=13)
text(s, 8.3, 5.15, 4.4, 0.4, [[("Tài liệu này tương ứng với tiêu chí Ý tưởng.", 11.5, ORANGE_DK, False, True)]])
page_no(s, 3)

# ============================ 4 · TRIẾT LÝ ============================
s = prs.slides.add_slide(BLANK)
header(s, "02 · Nguyên tắc thiết kế", "Mô hình đảm nhận suy luận; hệ thống điều phối và đo lường.")
items = [
    ("Phân tách vai trò", "Không mã hóa cứng đáp án hay công thức; mô hình thực hiện suy luận, hệ thống đo lường độ tin cậy của kết quả."),
    ("Chống quá khớp bằng đo lường", "Một kỹ thuật chỉ được triển khai khi chứng minh được khả năng tổng quát hóa bằng kết quả thực nghiệm, không dựa trên giả định."),
    ("Hiệu chỉnh độ bất định", "Độ tin cậy được ước lượng từ mức đồng thuận giữa các mẫu suy luận, cho phép tập trung tài nguyên tính toán vào câu hỏi khó."),
    ("Ranh giới triển khai", "Container ngoại tuyến và tự chứa; các công cụ truy vết, đánh giá, phân tích chỉ tồn tại trong môi trường phát triển."),
]
for i, (t, d) in enumerate(items):
    cx = 0.7 + (i % 2) * 6.15
    cy = 2.25 + (i // 2) * 2.2
    box(s, cx, cy, 5.85, 1.95, fill=CREAM)
    box(s, cx, cy, 0.1, 1.95, fill=ORANGE)
    text(s, cx + 0.35, cy + 0.2, 5.3, 1.6,
         [[(f"{i+1}. {t}", 15, ORANGE_DK, True, False)], [("", 6, INK, False, False)], [(d, 12.5, INK, False, False)]],
         anchor=MSO_ANCHOR.MIDDLE, space=4.0)
page_no(s, 4)

# ============================ 5 · KIẾN TRÚC ============================
s = prs.slides.add_slide(BLANK)
header(s, "03 · Kiến trúc", "Đường ống cấu hình hóa: bổ sung ngôn ngữ hoặc dạng câu hỏi chỉ yêu cầu thay đổi cấu hình.")
flow = ["/data CSV·JSON", "loader", "router / classifier", "solver — self‑consistency CoT",
        "answer normalizer", "constrained + contract repair", "/output/pred.csv"]
for i, step in enumerate(flow):
    cy = 2.2 + i * 0.62
    hot = i in (3, 6)
    box(s, 0.9, cy, 6.0, 0.5, fill=ORANGE if hot else CREAM)
    text(s, 1.15, cy + 0.06, 5.6, 0.4, [[(step, 13, WHITE if hot else INK, hot, False)]])
    if i < len(flow) - 1:
        text(s, 3.55, cy + 0.46, 1, 0.2, [[("▼", 9, ORANGE, True, False)]])
box(s, 7.5, 2.2, 5.2, 3.95, fill=LIGHT)
box(s, 7.5, 2.2, 5.2, 0.12, fill=INK)
text(s, 7.78, 2.45, 4.7, 3.6, [
    [("Đặc điểm thiết kế", 14, ORANGE_DK, True, False)],
    [("Tầng giao tiếp mô hình được trừu tượng hóa qua một giao diện complete() thống nhất, cho phép thay thế Gemma hoặc Qwen mà không sửa logic suy luận.", 12, INK, False, False)],
    [("Cổng kiểm soát chính sách và các registry ngăn mọi thành phần chỉ phục vụ phát triển lọt vào container thi đấu.", 12, INK, False, False)],
    [("Các thành phần truy vết và checkpoint chỉ hoạt động ở môi trường phát triển, giữ kích thước ảnh nộp tối thiểu.", 12, INK, False, False)],
])
page_no(s, 5)

# ============================ 6 · KẾT QUẢ ============================
s = prs.slides.add_slide(BLANK)
header(s, "04 · Kết quả", "Việc cho phép mô hình suy luận nâng độ chính xác từ 77.11 lên 88.55, đo trực tiếp trên leaderboard.")
bars = [("Letter‑only\n(baseline)", 77.11, GRAY), ("Self‑consistency\nCoT", 87.26, ORANGE), ("+ An‑toàn\ntừ chối", 88.55, GREEN)]
base_y = 6.0; scale = 3.3 / 90.0
for i, (lbl, val, col) in enumerate(bars):
    bx = 1.4 + i * 2.9
    bh = val * scale
    box(s, bx, base_y - bh, 1.9, bh, fill=col)
    text(s, bx - 0.25, base_y - bh - 0.5, 2.4, 0.4, [[(f"{val}", 23, col, True, False)]], align=PP_ALIGN.CENTER)
    text(s, bx - 0.25, base_y + 0.1, 2.4, 0.7, [[(lbl, 12, INK, False, False)]], align=PP_ALIGN.CENTER)
text(s, 10.3, 2.4, 2.85, 3.0, [
    [("+10,15 điểm", 18, ORANGE, True, False)],
    [("nhờ cơ chế suy luận", 12, GRAY, False, False)],
    [("", 10, INK, False, False)],
    [("+1,29 điểm", 18, GREEN, True, False)],
    [("nhờ an‑toàn‑từ‑chối", 12, GRAY, False, False)],
])
text(s, 0.9, 6.7, 11.8, 0.4, [[("Giới hạn tham chiếu (giải thủ công, chỉ dùng định mốc, không nộp): 91.79. Phần sai số còn lại thuộc tri thức đặc thù và một số đáp án chuẩn bị lỗi.", 11.5, GRAY, False, True)]])
page_no(s, 6)

# ============================ 7 · PHƯƠNG PHÁP ============================
s = prs.slides.add_slide(BLANK)
header(s, "05 · Phương pháp", "Sáu kỹ thuật được áp dụng; mỗi kỹ thuật được giữ lại sau khi đo lường xác nhận hiệu quả.")
levers = [
    ("Chain‑of‑thought", "Tăng 10,15 điểm. Các token lập luận chính là quá trình tính toán dẫn tới đáp án."),
    ("Self‑consistency", "Lấy mẫu nhiều lần và bỏ phiếu đa số; độ tin cậy được tính từ tỉ lệ đồng thuận."),
    ("An‑toàn‑từ‑chối", "Tăng 1,29 điểm. Phán đoán theo ngữ nghĩa thay vì từ khóa nên tổng quát hóa được."),
    ("TIR — thực thi Python", "Cho nhóm câu định lượng (~25–30%): chạy mã trong môi trường cô lập, bỏ phiếu trên bước thiết lập bài toán."),
    ("Constrained decoding", "Văn phạm GBNF ràng buộc đầu ra về một chữ cái hợp lệ ở bước hiệu chỉnh, loại bỏ phỏng đoán."),
    ("Khử thiên lệch vị trí", "Hoán vị tuần hoàn thứ tự lựa chọn; 29% câu hỏi có tới mười phương án."),
]
for i, (t, d) in enumerate(levers):
    cx = 0.7 + (i % 3) * 4.07
    cy = 2.35 + (i // 3) * 2.05
    ch = 1.8
    box(s, cx, cy, 3.85, ch, fill=WHITE, line=LIGHT, line_w=1.0)
    box(s, cx, cy, 3.85, 0.1, fill=ORANGE)
    text(s, cx + 0.28, cy + 0.1, 3.32, ch - 0.2,
         [[(t, 14, ORANGE_DK, True, False)], [("", 6, INK, False, False)], [(d, 11.5, INK, False, False)]],
         anchor=MSO_ANCHOR.MIDDLE, space=4.0)
page_no(s, 7)

# ============================ 8 · ROBUSTNESS ============================
s = prs.slides.add_slide(BLANK)
header(s, "06 · Tính bền vững", "Cơ chế bảo đảm tính toàn vẹn của pred.csv: một lỗi cục bộ không làm mất toàn bộ kết quả.")
two = [
    ("Mọi câu đều có đáp án", "Ngoại lệ phát sinh khi giải được bắt ở cấp từng câu và thay bằng đáp án dự phòng tất định, nên một câu lỗi không làm dừng toàn bộ tiến trình."),
    ("Ghi kết quả trước khâu kiểm tra", "Bước hiệu chỉnh hợp đồng bảo đảm pred.csv phủ đúng toàn bộ qid với chữ cái hợp lệ; tệp được ghi trước, khâu kiểm tra chỉ phát cảnh báo."),
]
for i, (t, d) in enumerate(two):
    cx = 0.7 + i * 6.15
    ch = 1.7
    box(s, cx, 2.3, 5.85, ch, fill=CREAM, line=GREEN, line_w=1.5)
    text(s, cx + 0.32, 2.3 + 0.1, 5.25, ch - 0.2,
         [[(t, 15, GREEN, True, False)], [("", 6, INK, False, False)], [(d, 12.5, INK, False, False)]],
         anchor=MSO_ANCHOR.MIDDLE, space=4.0)
text(s, 0.7, 4.5, 12, 0.4, [[("Khả năng tự khôi phục khi gặp sự cố gồm ba lớp:", 14, INK, True, False)]])
text(s, 0.9, 4.95, 12, 1.5, [
    [("1.  Thử lại từng câu", 13, ORANGE_DK, True, False), (": các lỗi tạm thời (hết thời gian, mất kết nối) được thử lại với khoảng chờ tăng dần.", 12.5, INK, False, False)],
    [("2.  Dự phòng từng câu", 13, ORANGE_DK, True, False), (": mọi lỗi khác được thay bằng đáp án heuristic tất định, không gây dừng tiến trình.", 12.5, INK, False, False)],
    [("3.  Checkpoint và khôi phục", 13, ORANGE_DK, True, False), (": khi container khởi động lại, tiến trình tiếp tục từ câu cuối cùng, không tính toán lại.", 12.5, INK, False, False)],
])
text(s, 0.7, 6.6, 12, 0.4, [[("Đã kiểm thử đúng entrypoint Docker trên GPU thực tế (pred.csv hợp lệ, hợp đồng 40/40); 211 ca kiểm thử đơn vị đạt.", 11.5, GRAY, False, True)]])
page_no(s, 8)

# ============================ 9 · KỶ LUẬT ============================
s = prs.slides.add_slide(BLANK)
header(s, "07 · Chống quá khớp", "Phần lớn kỹ thuật khảo sát bị loại bỏ dựa trên kết quả đo lường thực nghiệm.")
table(s, 0.7, 2.15, 12.0, [
    [("Kỹ thuật đã khảo sát", WHITE, True), ("Kết quả đo", WHITE, True), ("Lý do loại bỏ", WHITE, True)],
    ["RAG luật / hành chính", ("âm", RED, True), "civics −5 điểm, định lượng −7,5 điểm; trắc nghiệm đóng không có ngữ liệu để truy hồi."],
    ["Bỏ phiếu đa dạng (k=5)", ("không đổi", GRAY, True), "Sai số của mô hình mang tính hệ thống; các mẫu cùng đồng thuận một đáp án sai."],
    ["Lượng tử hóa cao hơn (Q6/Q8)", ("không đổi / kém", GRAY, True), "Q4 là QAT (tối ưu sẵn cho 4‑bit); Q6/Q8 không cải thiện mà tốn gấp đôi thời gian và bộ nhớ."],
    ["Mô hình dense 31B", ("loại: thời gian", RED, True), "≈90 giây/câu, tương đương ~50 giờ cho 2000 câu; chỉ cao hơn ~0,7 điểm."],
    ["Mô hình thẩm định Qwen3.5‑9B", ("chưa chấp nhận", GRAY, True), "Bản độc lập kém hơn; thẩm định chéo không ổn định và có nguy cơ đảo đáp án đang đúng."],
], [3.4, 2.0, 6.6], row_h=0.75, font_sz=12, head_sz=13)
text(s, 0.7, 6.85, 12, 0.4, [[("Kết quả phủ định có giá trị ngang kết quả khẳng định: chúng ngăn việc triển khai các kỹ thuật bất lợi cho tập kiểm thử riêng.", 12, ORANGE_DK, False, True)]])
page_no(s, 9)

# ============================ 10 · THỜI GIAN ============================
s = prs.slides.add_slide(BLANK)
header(s, "08 · Điểm thời gian", "Điểm thời gian được bảo đảm ở độ sâu suy luận tối đa do tham số token gần như không ảnh hưởng thời gian.")
table(s, 0.7, 2.4, 6.4, [
    [("reasoning_max_tokens", WHITE, True), ("Thời gian (463 câu)", WHITE, True)],
    [("768", INK, True), ("21,2 phút",)],
    [("1280", INK, True), ("22,1 phút",)],
    [("2048  (triển khai)", ORANGE_DK, True), ("22,6 phút",)],
], [3.9, 2.5], row_h=0.55, font_sz=13, head_sz=12)
text(s, 0.7, 4.95, 6.6, 1.5, [
    [("Mức 2048 chỉ chậm hơn mức 768 khoảng 6,7% do mô hình MoE thường dừng sớm. Tập 2000 câu hoàn tất trong khoảng 1,5–1,6 giờ ở mọi mức.", 13, INK, False, False)],
])
box(s, 7.5, 2.4, 5.2, 3.9, fill=CREAM, line=ORANGE, line_w=1.25)
text(s, 7.78, 2.62, 4.7, 3.6, [
    [("MTP — Multi‑Token Prediction", 15, ORANGE_DK, True, False)],
    [("Mô hình phác thảo nhiều token và mô hình gốc kiểm chứng, nên đầu ra không thay đổi.", 12.5, INK, False, False)],
    [("Không suy giảm độ chính xác.", 13, GREEN, True, False)],
    [("Tăng tốc 1,4–2,2 lần.", 13, GREEN, True, False)],
    [("Trực giao với lượng tử hóa nên triển khai đồng thời; tích hợp qua provider local_server.", 12, GRAY, False, True)],
])
page_no(s, 10)

# ============================ 11 · ĐỊNH VỊ ============================
s = prs.slides.add_slide(BLANK)
header(s, "09 · Định vị kết quả", "88.55 tiệm cận giới hạn thực tế của mô hình Gemma ngoại tuyến; phần khắc phục được thuộc về suy luận định lượng.")
stats = [("27/31", "mô hình tham chiếu đúng\n(Gemma sai thực sự)", GRAY), ("16/463", "xác nhận khắc phục được\n(định lượng + suy luận)", GREEN), ("13", "thiếu hụt tri thức\nkhông khắc phục được", RED)]
for i, (n, d, c) in enumerate(stats):
    cx = 0.9 + i * 4.0
    box(s, cx, 2.45, 3.6, 1.7, fill=WHITE, line=c, line_w=1.5)
    text(s, cx, 2.45, 3.6, 1.7,
         [[(n, 27, c, True, False)], [(d, 11.5, INK, False, False)]],
         anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER, space=4.0)
text(s, 0.7, 4.55, 12, 1.9, [
    [("Phần khắc phục được là các bài toán định lượng xác định", 14, ORANGE_DK, True, False),
     (" (Henderson–Hasselbalch, tốc độ động cơ, trị riêng, kinh tế – địa lý),", 13, INK, False, False)],
    [("đúng phạm vi mà kỹ thuật TIR và CoT (đã xây dựng) hướng tới, không phải phần một mô hình thẩm định Qwen có thể bổ sung.", 13, INK, False, False)],
    [("13 câu còn lại thuộc tri thức hành chính 2025 và dữ kiện địa phương, không mô hình hợp lệ nào khắc phục được với chi phí thấp.", 13, GRAY, False, False)],
    [("Tài liệu trình bày số liệu đo được, không cam kết số liệu chưa kiểm chứng.", 13, GREEN, False, True)],
])
page_no(s, 11)

# ============================ 12 · TÁI LẬP ============================
s = prs.slides.add_slide(BLANK)
header(s, "10 · Bài nộp", "Tái lập kết quả trong container bằng hai câu lệnh.")
box(s, 0.7, 2.35, 12.0, 1.95, fill=CODEBG)
text(s, 0.95, 2.55, 11.6, 1.75, [
    [("# 1. Tải ảnh tự chứa (mô hình đã đóng gói sẵn bên trong)", 12.5, RGBColor(0x9C, 0xA3, 0xAF), False, False)],
    [("docker pull hacamy12345/neko-core:gemma26b-q4", 13.5, RGBColor(0x86, 0xEF, 0xAC), False, False)],
    [("# 2. Chạy trên thư mục chứa public_test.csv hoặc private_test.csv", 12.5, RGBColor(0x9C, 0xA3, 0xAF), False, False)],
    [("docker run --rm --gpus all -v ./data:/data -v ./out:/output \\", 13.5, RGBColor(0x86, 0xEF, 0xAC), False, False)],
    [("    hacamy12345/neko-core:gemma26b-q4       (kết quả: ./out/pred.csv)", 13.5, RGBColor(0x86, 0xEF, 0xAC), False, False)],
])
text(s, 0.7, 4.6, 12, 1.9, [
    [("Mô hình triển khai: Gemma‑4‑26B‑A4B QAT‑Q4_0 (kiến trúc MoE, ~15GB), chạy được trên mọi GPU, không rủi ro tràn bộ nhớ.", 13.5, INK, False, False)],
    [("Quy trình suy luận: chain‑of‑thought tự nhất quán (k=1, 2048 token), an‑toàn‑từ‑chối, hiệu chỉnh ràng buộc và hiệu chỉnh hợp đồng, kèm TIR có điều kiện.", 13, INK, False, False)],
    [("Mã nguồn và hướng dẫn tái lập: README.md. Tài liệu đầy đủ: docs/method-writeup-vi.md. 211 ca kiểm thử đạt.", 12, ORANGE_DK, False, True)],
])
page_no(s, 12)

# ============================ 13 · KẾT LUẬN ============================
s = prs.slides.add_slide(BLANK)
box(s, 0, 0, 13.333, 7.5, fill=INK)
box(s, 0, 3.05, 13.333, 0.06, fill=ORANGE)
text(s, 0.9, 1.95, 11.5, 1.1, [[("Phương pháp luận: mô hình suy luận, hệ thống đo lường, quyết định dựa trên số liệu thực nghiệm.", 25, WHITE, True, False)]])
text(s, 0.9, 3.45, 11.5, 1.6, [
    [("Kết quả 88.55 trên leaderboard, cơ chế bảo đảm tính toàn vẹn của pred.csv, điểm thời gian được bảo vệ bằng kiến trúc MoE và MTP,", 16, CREAM, False, False)],
    [("cùng kỷ luật chống quá khớp dựa trên đo lường cho tập 2000 câu hỏi riêng.", 16, CREAM, False, False)],
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
