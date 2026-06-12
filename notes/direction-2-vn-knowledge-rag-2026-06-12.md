# Hướng 2 — VN-knowledge RAG (lever ship-được duy nhất để qua 91.73)

Ghi ngày 2026-06-12. Trạng thái: ĐÃ GHI CHÚ, chưa code. Khởi động sau khi owner duyệt.

## Vì sao đây là lever đúng (bằng chứng leaderboard)

- Claude (frontier) giải tay 463 câu = **90.93**; ngưỡng qua vòng = **91.73**.
- Web-verify ~25 câu nghi ngờ: 4 lỗi chắc chắn **đều là fact VN đặc thù** (0254 sáp xã,
  0070 hồ sơ mầm non, 0354 thời hạn NĐ144, 0030 chùa An Phú). Sửa → **~91.8 ≈ chạm ngưỡng**.
- Kết luận: test là **knowledge-game VN**, không phải reasoning-game. Phần thiếu của Gemma
  = fact VN (hành chính 2025, số điều/thời hạn luật VN, chùa/địa phương). Gemma offline
  KHÔNG có sẵn → chỉ RAG nhồi kiến thức mới đẩy lên được.
- Đây là RE-TARGET của level-3 RAG (đã build, đo "âm"). RAG âm vì đo trên **proxy civics
  generic (ViGEText)**; gap THẬT là **slice VN-admin/legal** — đúng thứ RAG sinh ra để giải.

## Corpus cần xây (gom NGAY, freeze offline vào Docker)

1. **Hành chính 2025 (cao giá trị nhất):** toàn bộ nghị quyết sắp xếp ĐVHC cấp tỉnh + cấp xã
   2025 — NQ 1656 (Hà Nội), NQ 1664 (Gia Lai), và 34 tỉnh/thành: danh sách xã/phường sau
   sáp nhập + số đơn vị + mô hình 2 cấp (bỏ cấp huyện từ 1/7/2025) + tỉnh nào sáp tỉnh nào.
   Nguồn: xaydungchinhsach.chinhphu.vn, thuvienphapluat, vanban.chinhphu.vn.
2. **Luật VN tham chiếu (chunk theo Điều):** Luật BVMT 2020, NĐ 144/2020 (NTBD), NĐ 79/2012,
   Luật Đất đai 2024, Luật Căn cước 2023, Bộ luật Hình sự, Bộ luật Dân sự 2015, QĐ 146/QĐ-TTg,
   NĐ 125/2025, Luật Tài nguyên nước, các NĐ/TT về thủ tục (bưu chính, đường ngang, kiểm định
   GD mầm non, hộ chiếu...). Corpus YuITC MIT đã có (344k chunks) — bổ sung các văn bản còn thiếu.
3. **Bách khoa/địa phương (khó, ưu tiên thấp):** chùa, địa lý, văn hóa VN — vi-wiki parquet
   lọc stub <500 ký tự. Slice này hẻo, RAG khó bắt ổn định; chấp nhận bỏ một phần.

## Kiến trúc (tái dùng level-3 đã build)

- **Gate (đã có):** `has_legal_admin_strong` (≥2 markers) + classifier VN-admin. CHỈ retrieve
  trên câu VN-legal/admin/local-fact. TUYỆT ĐỐI không bật trên reading-comp/math (RAG đo hại
  ở đó: civics −5pp, quant −7.5pp). Đây là lý do RAG-blanket trước đây âm.
- **Retrieval:** BM25 stdlib (đã có, giữ diacritics) + tùy chọn BGE-m3 GGUF (llama-server
  --embedding) hybrid; Qwen3-Reranker nếu cần.
- **Prompt:** fallible-excerpt (đã có) → degrade về self-consistency khi miss/fail.
- **Model nền:** 26B-A4B (MoE 14.4GB, chạy mọi GPU) — KHÔNG dùng 31B (rủi ro OOM 24GB).

## Đo & promote

- Đo PER-BUCKET trên VN-admin/legal slice, KHÔNG đo blanket. Promote chỉ khi thắng slice đó
  + không regression tổng. Dùng dè 5 lần nộp (còn ~3 sau khi nộp v2).
- Proxy mislead (đã rõ): chỉ tin LEADERBOARD. ViGEText/ViMMRC không track distribution thật.

## Caveat trung thực (đừng quên)

- Corrected-frontier mới CHẠM ngưỡng (~91.8); nhiều đội ở TRÊN xa → qua vòng chưa chắc đủ.
- Gemma 88.12 cần TRỌN gói RAG để tới ngưỡng — gap +3.6pp, lớn. Không bảo đảm.
- **Time-score cost:** retrieval + ~2.5GB RAM + chậm hơn → trừ điểm Time (10đ). Cân nhắc khi
  promote: chỉ retrieve trên ~15-20% câu (gate chặt) để giảm cost.
- Defective-gold chặn trần tuyệt đối (~vài câu key sai, không sửa được).
- 2025-facts phải scrape NGAY và freeze; corpus bundle offline trong image (không web lúc chấm).

## Bước 1 cụ thể (khi khởi động)

1. Scrape corpus hành chính 2025 (34 tỉnh) → `data/rag/vn_admin_2025.jsonl` (structured: tỉnh,
   xã mới, đơn vị cũ sáp nhập, số đơn vị, NQ số hiệu).
2. Bổ sung văn bản luật còn thiếu vào corpus legal.
3. Wire vào `_solve_rag` với gate VN-admin; unit test + policy gate.
4. Đo 1 probe leaderboard (26B + VN-RAG gated) vs baseline 87.26. Pause chờ owner trước nộp.

Liên quan: `notes/worklog.md` (2026-06-12), `notes/pseudo-label-analysis-2026-06-12.md`,
level-3 RAG code đã có (commit 880fe83).
