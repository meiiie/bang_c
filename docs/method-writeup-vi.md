# Neko Core — Thuyết minh phương pháp (HackAIthon 2026, Bảng C)

Trạng thái: Đã xác nhận trên leaderboard — CoT đạt **87.26** (so với baseline cùng mô hình 77.11)
Cập nhật: 2026-06-10

> Mọi con số dưới đây là **đo thật trên mô hình thi đấu** (Gemma‑4‑26B‑A4B‑Q4 GGUF chạy
> local trên GPU NVIDIA A40), không phỏng đoán. Phần nào chưa đo được ghi rõ "đang chờ".

## 1. Bài toán & hợp đồng

Bảng C yêu cầu một **Docker container tự chứa, chạy offline**: đọc `/data/public_test.csv`
hoặc `private_test.csv`, ghi `/output/pred.csv` gồm hai cột `qid,answer` (chữ cái lựa chọn
theo từng dòng). Chấm trên bộ private **2000 câu, đa lĩnh vực/đa ngôn ngữ**: Accuracy 80đ,
thời gian suy luận 10đ, ý tưởng 10đ. Mô hình cho phép: **Gemma‑4** và **Qwen3.5 ≤9B**
(embed/rerank BGE‑m3 / Qwen‑Rerank). Runtime đã chọn: **Gemma‑4‑26B‑A4B‑QAT‑Q4_0 GGUF**
chạy llama.cpp local — không cần API key khi chấm.

## 2. Triết lý thiết kế

Neko Core là **harness suy luận config‑first**, cố ý nhỏ gọn và tái lập. Bốn nguyên tắc:

1. **Để mô hình SUY LUẬN; harness điều phối và ĐO LƯỜNG.** Không nhồi đáp án hay công thức
   viết tay; cho mô hình mạnh không gian lập luận, rồi đo độ tin cậy.
2. **Chống overfit.** Bộ private đa lĩnh vực/đa ngôn ngữ — bất cứ thứ gì gắn cứng vào một
   câu cụ thể hay một ngôn ngữ đều bị loại bỏ hoặc tổng quát hoá qua config. Thêm ngôn ngữ
   hay loại câu = một dòng config, không sửa mã.
3. **Đo độ bất định thật.** Thay confidence tuỳ tiện bằng tín hiệu quan sát được (mức đồng
   thuận khi lấy mẫu), để harness "nhìn thấy" được chỗ nó có thể sai.
4. **Ranh giới runtime/offline cứng.** Container nộp bài offline, tự chứa — không web,
   không dịch vụ ngoài. Mọi thử nghiệm/trace/phân tích diễn ra ở khâu phát triển, không
   bao giờ ship.

## 3. Kiến trúc (đường ống phân tầng, cấu hình trong `configs/default.json`)

```
/data (CSV|JSON)
  → loader            (Problem: qid, câu hỏi, lựa chọn — theo từng dòng)
  → router/classifier (tín hiệu cấu trúc, language‑agnostic)
  → solver            (chain‑of‑thought reasoning; các strategy cũ vẫn giữ)
  → answer normalizer (trích chữ cái từ lập luận, kể cả "ANSWER: X")
  → calibration       (confidence = tỉ lệ đồng thuận khi lấy mẫu)
  → exporter          → /output/pred.csv
  → (chỉ dev) trace / review / eval / checkpoint / manifest
```

Tầng provider trừu tượng sau một hợp đồng `complete()` duy nhất, nên Gemma‑4 (local GGUF) và
Qwen3.5 hoán đổi được mà không đụng logic solver. Một policy gate + các registry
(agents/tools/commands) bảo đảm không có khả năng "chỉ‑dành‑cho‑dev" lọt vào container.

## 4. Chiến lược tối ưu — và BẰNG CHỨNG THỰC NGHIỆM

Điểm xuất phát: **85.53** trên public test (đã biết). Soi trace cho thấy điểm này được chống
đỡ bởi **heuristic riêng cho tiếng Việt + adjudicator gắn cứng vào câu public** (sẽ không
chuyển giao sang private), và **confidence bị gắn cứng** nên ~57/463 câu sai mà harness
không thấy ("lỗi im lặng"). Chiến lược nhắm đúng các lớp lỗi *có thể cứu*:

- **Cho mô hình lập luận (chain‑of‑thought).** Đáp án cuối là 1 chữ cái, nhưng *các token lập
  luận chính là phép tính tạo ra chữ cái đó*. Bản gốc ép trả lời chỉ‑1‑chữ‑cái → mô hình nhỏ
  giải sai bài nhiều bước. **Đo thật trên Gemma‑4‑26B**, CoT sửa đúng những câu baseline sai:

  | Câu | Baseline (chỉ chữ cái) | CoT | Đáp án đúng (kiểm tra tay) |
  |---|---|---|---|
  | Độ co giãn của cầu | C = 2.0 ✗ | **B = 1.0** ✓ | (100/200)/(2/4) = 1.0 |
  | Giãn nở thời gian, v=0.6c | G = 1.33 ✗ | **F = 1.25** ✓ | 1/√(1−0.36) = 1.25 |
  | Doanh thu tăng thêm, 50→75 đv | A = 750 ✗ | **B = 1500** ✓ | 25 × 60 = 1500 |

- **Tự‑nhất‑quán (self‑consistency) + confidence thật.** Lấy mẫu k lần, bỏ phiếu đa số;
  confidence = tỉ lệ đồng thuận. Đo thật cho thấy với `temperature=0` các mẫu gần như giống
  nhau, nên **k=1 (một lượt CoT) là lựa chọn hiệu quả** cho contest (chính xác như k=5,
  nhanh gấp ~4 lần, tái lập). Calibration thật cần `temperature>0` (mở rộng sau).

- **Routing language‑agnostic + giữ dấu tiếng Việt.** Định tuyến dựa trên tín hiệu cấu trúc
  độc lập ngôn ngữ (số lựa chọn, dấu hiệu tính toán thật, độ dài ngữ cảnh) thay vì keyword
  bỏ‑dấu dễ va chạm. Đã sửa: câu hỏi "công thức hoá học của nước" không còn bị nhận nhầm là
  bài tính toán chỉ vì có chữ số trong đáp án.

- **Loại bỏ overfit.** Gỡ các solver công thức viết tay và rule gắn cứng vào câu public —
  chúng đóng góp ~0 trên câu lạ và có rủi ro bắn nhầm. Để mô hình tự suy luận thay thế.

- **Không dùng web/rerank.** Container offline nên không search mạng. Đề là trắc nghiệm
  *đóng* (tự chứa) nên embedding/rerank (BGE‑m3/Qwen‑Rerank) không có corpus để truy xuất →
  không thêm; giữ runtime gọn.

## 5. Kết quả thực nghiệm (đo trên A40 + Gemma‑4‑26B, 2026‑06‑10)

- **Sửa bug thật:** `reasoning_max_tokens=512` cắt cụt lập luận trước khi mô hình viết
  "ANSWER:" → 30% fallback + sai. Nâng **2048** → fallback còn 1.5%, độ chính xác tăng.
- **CoT vs baseline (full 463 câu, cùng mô hình):** CoT đúng **5/5** câu gold (baseline 4/5),
  đổi đáp án ở **91/463 câu (19.7%)**, tập trung ở **calculation (42/111 = 38%)** — đúng nơi
  lập luận phát huy; spot‑check tay xác nhận CoT đúng ở các câu baseline sai (bảng trên).
- **Thời gian:** baseline ~0.8s/câu, CoT ~4.6s/câu (sinh cả lập luận). Đánh đổi cố ý:
  Accuracy 80đ ≫ Time 10đ. Đòn bẩy thời gian (để dành): **tiering** — CoT chỉ cho câu khó.
- **Robustness chủ đề nhạy cảm:** câu chủ quyền Hoàng Sa/Trường Sa → mô hình trả lời **đúng
  lập trường Việt Nam**, không cần can thiệp prompt.

## 6. Runtime & tái lập

Runtime: Gemma‑4‑26B‑A4B‑QAT‑Q4_0 GGUF qua llama.cpp, đóng trong Docker image tự chứa
(`hacamy12345/neko-core:...`). Sampling tất định (temperature 0). Mỗi lần chạy ghi manifest
(hash config/input, mô hình, strategy, argv) + trace bất biến; output được kiểm tra đúng hợp
đồng `qid,answer` trước khi ghi `pred.csv`. Bộ test đơn vị 108 ca + dry‑run contract + policy
audit.

## 7. Kết quả leaderboard (đã xác nhận)

Nộp cả hai cách lên leaderboard, cùng mô hình Gemma‑4‑26B:

| Cách (cùng mô hình) | Điểm leaderboard |
|---|---|
| Letter‑only (baseline) | 77.11 |
| **Chain‑of‑thought (cách của chúng tôi)** | **87.26** |

**CoT vượt +10.15 điểm** so với baseline cùng mô hình (và +1.73 so với 85.53 trước đó). Phán
quyết chính thức trên đúng thước đo chấm điểm xác nhận luận điểm cốt lõi: *cho mô hình suy
luận*. Bài nộp cuối: image `hacamy12345/neko-core:gemma26b-q4-cot-20260610`. Không con số nào
trong tài liệu này là phỏng đoán.
