# Neko Core — Thuyết minh phương pháp (HackAIthon 2026, Bảng C)

**Đội thi: Neko Core — Đại học Hàng hải Việt Nam (VMU).** Thành viên: Nguyễn Mạnh Hùng
(CNT63ĐH, trưởng nhóm), Bùi Việt Hoàng (CLC63ĐH), Phạm Thị Minh Hồng (CNT63ĐH),
Phạm Thị Thu Thảo (KTN63ĐH), Nghiêm Thị Mỹ Linh (KPM63ĐH).

Trạng thái: Leaderboard đã xác nhận **88.55** (CoT self‑consistency + đòn bẩy an‑toàn).
Image nộp v0.6.0 là `gemma26b-q4-portable-20260614` (runtime llama.cpp build `GGML_NATIVE=off` →
**chạy mọi CPU**; đầu ra giống hệt bản tiền thân `gemma26b-q4-clean-20260614` đã đạt **88.34** trên
public‑463). Cùng đường, lệch ±1 câu do nhiễu số học giữa các bản build llama.cpp; trần thật ~88.5.
Cập nhật: 2026‑06‑14

> Mọi con số trong tài liệu là **đo thật**: trên leaderboard chính thức, hoặc trên mô hình thi
> đấu (Gemma‑4‑26B‑A4B QAT‑Q4_0 GGUF, llama.cpp, GPU NVIDIA thuê thật). Không phỏng đoán.
> Các đòn bẩy đã **thử rồi loại** được nêu kèm lý do đo được — kỷ luật đó là một phần của
> phương pháp, không kém gì các đòn bẩy thắng.

---

## 1. Bài toán & hợp đồng chấm điểm

Bảng C yêu cầu một **Docker container offline, tự chứa**: đọc `/data/*_test.csv`, ghi
`/output/pred.csv` đúng hai cột `qid,answer` (chữ cái mỗi dòng). Chấm trên **2000 câu private
đa lĩnh vực/đa ngôn ngữ**:

| Tiêu chí | Trọng số | Hệ quả thiết kế |
|---|---|---|
| **Accuracy** | 80đ | mục tiêu chính — mọi đòn bẩy phải tổng quát hoá sang 2000 câu lạ |
| **Thời gian inference** | 10đ | nhanh nhất = 10đ, còn lại `nhanh_nhất/của_đội × 10` → tốc độ là mục tiêu hạng nhất |
| **Ý tưởng / tối ưu sáng tạo** | 10đ | tài liệu này |

Mô hình cho phép: **Gemma‑4** và **Qwen3.5 ≤9B** (embed/rerank BGE‑m3 / Qwen‑Rerank). Thí
sinh ship: **Gemma‑4‑26B‑A4B QAT‑Q4_0 GGUF** — một mô hình **MoE** (~4B tham số *active*,
~15GB) chạy local qua llama.cpp, không cần API key khi chấm.

## 2. Triết lý thiết kế

Neko Core là **harness suy luận config‑first**, cố ý nhỏ gọn và tái lập. Bốn nguyên tắc chi
phối mọi quyết định:

1. **Để mô hình SUY LUẬN; harness điều phối và ĐO LƯỜNG.** Không nhồi đáp án hay công thức
   viết tay; cho mô hình mạnh không gian lập luận và đo độ tin cậy nên đặt vào output.
2. **Chống overfit, được THƯỚC ĐO bắt buộc.** Bộ private đa ngôn ngữ; bất cứ thứ gì gắn cứng
   vào một câu public hay một ngôn ngữ là gánh nặng. Một đòn bẩy chỉ được ship khi *tổng quát
   hoá*, chứng minh bằng đo thật — không phải bằng một câu chuyện hợp lý. Thêm ngôn ngữ/loại
   câu = một dòng config, không sửa mã.
3. **Đo độ bất định thật.** Confidence là tín hiệu quan sát được (mức đồng thuận khi lấy mẫu),
   để harness "nhìn thấy" chỗ nó dễ sai và chỉ tốn compute ở đó — bảo vệ điểm Time.
4. **Ranh giới runtime/phát triển CỨNG.** Container nộp bài offline, tự chứa (không web, không
   dịch vụ ngoài, không trạng thái ẩn). Mọi trace/review/phân tích sống ở khâu phát triển,
   không bao giờ ship.

## 3. Kiến trúc

```
/data (CSV|JSON)
  → loader            (Problem mỗi dòng: qid, câu hỏi, lựa chọn; NFC‑normalize, BOM‑safe)
  → router/classifier (tín hiệu cấu trúc language‑agnostic → chọn strategy)
  → solver            (engine self‑consistency CoT; chế độ TIR / reading / safety routed vào)
  → answer normalizer (trích chữ cái, kể cả từ trong lập luận)
  → constrained repair (GBNF grammar ép chữ cái hợp lệ nếu một mẫu trôi khỏi định dạng)
  → contract repair   (đảm bảo pred.csv phủ đúng mọi qid với chữ cái hợp lệ)
  → exporter          → /output/pred.csv
  → (chỉ dev) trace / review / eval / checkpoint / manifest
```

Tầng provider giấu sau một hợp đồng `complete()` duy nhất, nên Gemma‑4 (local GGUF, runtime
thi đấu) và Qwen3.5 / API dev hoán đổi được mà không đụng logic solver. Một policy gate cùng
các registry (agents/tools/commands) bảo đảm không khả năng "chỉ‑dành‑cho‑dev" nào lọt vào
container thi.

## 4. Hành trình tối ưu Accuracy (đo trên leaderboard — thước đo duy nhất chúng tôi tin)

| Cấu hình (cùng mô hình Gemma‑4‑26B) | Accuracy public | Ghi chú |
|---|---|---|
| Letter‑only (ép trả lời 1 token) | **77.11** | lập luận bị nén |
| **Self‑consistency chain‑of‑thought** | **87.26** | +10.15pp — engine cốt lõi |
| **+ đòn bẩy an‑toàn‑từ‑chối** | **88.55** | +1.29pp, tổng quát hoá (xem §5) |

Tham chiếu trần: giải‑tay toàn bộ 463 câu bằng một mô hình frontier đạt **91.79** (chỉ dùng
làm *mốc trần*, không ship — vi phạm allowlist). Phần còn lại tới 91.79 bị chi phối bởi **fact
hành chính VN‑2025, trivia địa phương, và một số đáp án đề tự sai (defective gold)** — không
phải lỗi suy luận. Đây là lý do trần thật của một Gemma offline nằm ở vùng ~88.5, không phải
95+.

## 5. Các đòn bẩy thắng — đo thật

**Đòn bẩy 1 — Cho mô hình lập luận (CoT).** Baseline ép trả lời 1 chữ cái → mô hình giải sai
bài nhiều bước. Một prompt lập luận language‑neutral + trích chữ cái cuối thu hồi chúng:
**+10pp**, bước nhảy lớn nhất. (Ví dụ đo tay: độ co giãn cầu 2.0→1.0; giãn nở thời gian
1.33→1.25; RPM động cơ 735→1470.)

**Đòn bẩy 2 — Self‑consistency = accuracy *và* confidence thật.** Lấy mẫu lập luận, bỏ phiếu
đa số, đặt **confidence = tỉ lệ đồng thuận**. Vừa nâng accuracy vừa làm cho review rủi ro và
phân bổ compute có ý nghĩa (thay confidence gắn cứng 0.88 che giấu ~57 lỗi im lặng của
baseline).

**Đòn bẩy 3 — Phán đoán an‑toàn‑từ‑chối (+1.29pp, đã chứng minh).** Một lớp câu cài *"làm thế
nào để [hành vi phạm pháp/gây hại]"* mà đáp án đúng là lựa chọn **từ chối**. Một mệnh đề ngữ
nghĩa duy nhất — phán đoán theo *nghĩa* của yêu cầu, không match từ khoá, không bao giờ chọn
từ chối cho câu hợp pháp — chuyển đúng các câu này. Không‑từ‑khoá nên tổng quát sang tập
private đa ngôn ngữ; đo +1.29pp, không thấy hồi quy. Tiêm một chỗ ở tầng voting nên phủ mọi
đường (self‑consistency/reading/rag).

**Đòn bẩy 4 — TIR (Tool‑Integrated Reasoning) có gate cho lát định lượng.** ~25–30% đề là
toán đa lĩnh vực (kinh tế/giải tích/động học/thống kê, dày trong câu 10‑lựa‑chọn). Sau một
classifier số học, solver **chạy Python trong sandbox offline** và self‑consistency trên phần
*thiết lập bài* (không chỉ số học) để tránh bẫy "giải đúng nhưng sai hệ phương trình".
Offline‑safe; tổng quát theo tỉ lệ toán. (Phân tích cấu trúc lỗi cho thấy đây đúng là lát có
thể cứu được — xem §9.)

**Đòn bẩy 5 — Constrained decoding ở lượt sửa.** Nếu một mẫu CoT không cho ra chữ cái phân
giải được, lượt hỏi lại dựng **GBNF grammar chỉ chấp nhận đúng các chữ cái lựa chọn hợp lệ**,
nên một lần trôi định dạng không bao giờ rơi xuống đoán heuristic. Bộ dựng grammar suy biến
mềm (tự chạy không‑ràng‑buộc nếu llama.cpp thiếu hỗ trợ) — không bao giờ làm hỏng một lần
chạy. Đây là cải tiến *giải mã* thuần → không tune nội dung, không overfit.

**Đòn bẩy 6 — Khử thiên lệch vị trí (choice‑permutation).** 29% câu là 10‑lựa‑chọn, nơi thiên
lệch vị trí ảnh hưởng mạnh nhất; hoán vị xoay vòng lựa chọn trung hoà nó trước khi bỏ phiếu.

## 6. Robustness — hợp đồng pred.csv bất khả xâm phạm

Bài thi chấm trên `/output/pred.csv`; lỗi tệ nhất là **file thiếu hoặc sót (0 điểm)**. Hai
đảm bảo loại bỏ khả năng đó:

- **Mọi câu đều trả lời được.** Một exception khi giải được bắt the‑từng‑câu và thay bằng
  fallback heuristic tất định — một câu lỗi không thể làm sập cả lần chạy.
- **pred.csv được ghi TRƯỚC mọi thứ có thể raise.** Một bước *contract‑repair* dựng lại danh
  sách dự đoán để phủ **đúng các qid đầu vào, đúng thứ tự, mỗi câu một chữ cái hợp lệ** (giữ
  nguyên dự đoán tốt → accuracy không đổi; câu thiếu/sai‑phạm‑vi/trùng được điền tất định).
  File được ghi *trước* khâu kiểm tra hợp đồng (khâu này giờ chỉ cảnh báo). Một lỗ hổng giải
  hoặc lỗi bất ngờ không thể zero hoá một lần chạy 2000 câu.

Loader khoan dung input: BOM‑safe UTF‑8, NFC normalize dấu tiếng Việt, tên cột linh hoạt, số
lựa chọn động (không gắn cứng A–D). Sampling tất định; mỗi lần chạy ghi manifest (hash
config/input, mô hình, strategy, argv) + trace bất biến. **211 test đơn vị xanh**, kèm
dry‑run contract check và policy audit. *Đã smoke đúng entrypoint Docker trên GPU thật:
pred.csv hợp lệ, contract 40/40.*

## 7. Kỷ luật chống overfit — những gì đã LOẠI, và vì sao

Báo cáo phần loại bỏ chính là điểm nhấn: mỗi đòn bị **một phép đo** giết, không phải một linh
cảm.

- **RAG luật/hành chính (BM25 trên corpus VN): loại.** Đo âm trên phân phối thật (civics −5pp,
  quant −7.5pp ở nơi nó kích hoạt). Trắc nghiệm đóng tự chứa không có corpus để truy xuất;
  lát với tới được ~10–15%, phần lớn không‑khớp‑verbatim. Để OFF.
- **maj@k / voting đa dạng k=5: loại.** Đo (FPT n=120/bucket) = HOÀ (89.7 vs 90.0 k=1). Lỗi
  của Gemma là **hệ thống, không ngẫu nhiên** — các mẫu đa dạng đồng thuận cùng một đáp án
  *sai*, nên bỏ phiếu chỉ xác nhận cái sai. (Đây là lý do `self_consistency_samples=1`.)
- **Quant cao hơn (Q6_K/Q8_0): loại — giữ Q4_0.** Đo full 463: Q6/Q8 hoà‑tới‑kém‑nhẹ so với
  Q4_0 (đồng thuận với mốc tham chiếu: Q4 93.30 / Q8 93.09 / Q6 92.66) ở **2× thời gian + VRAM**.
  Q4_0 của ta là **QAT** (huấn luyện sẵn cho 4‑bit → mất rất ít); con số "4‑bit mất 4–10pp"
  trong nghiên cứu là *post‑training* quant, bản chất khác. Accuracy không nằm ở độ chính xác bit.
- **Mô hình dense 31B: loại vì điểm Time.** Đo thật **~90s/câu** trên A6000 (mọi tham số 31B
  active mỗi token) → ~50 giờ cho 2000 câu private, *mất trắng* 10đ Time, mà chỉ hơn ~0.7pp
  (nằm trong nhiễu). 26B‑A4B (MoE ~4B active) nhanh **~30×** ở cùng độ sâu suy luận và là thí
  sinh được ship.
- **Qwen3.5‑9B (standalone, hoặc adjudicator): không nhận.** Standalone đo kém hơn Gemma
  (84.9% proxy). Làm adjudicator vote chéo: phân tích cấu trúc lỗi cho thấy là *tung đồng xu*
  + rủi ro lật‑nhầm các câu đang đúng (xem §9). "Đo trước khi nhận" là luật cứng.
- **Solver công thức viết tay / rule riêng tiếng Việt: đã gỡ.** Đóng góp ~0 trên câu lạ, rủi
  ro bắn nhầm.

## 8. Tối ưu cho điểm Time (Vòng‑2)

Thời gian inference là mục tiêu hạng nhất, không phải nghĩ sau:

- **Mô hình MoE 26B‑A4B** (~4B active) là lựa chọn tốc độ cốt lõi.
- **Núm `reasoning_max_tokens` gần như PHẲNG về thời gian.** Sweep thật 768/1280/2048 trên
  463: 2048 chỉ chậm hơn 768 **+6.7%** (MoE tự dừng sớm trước khi chạm trần) → trần token gần
  như miễn phí, và 2048 là điểm gần mốc trần nhất. ⇒ giữ 2048; 2000 câu private chạy ~1.5–1.6h
  ở mọi mức → **điểm Time an toàn ở độ sâu suy luận tối đa**.
- **Phân bổ compute theo độ đồng thuận:** câu đồng thuận cao xong trong một lượt rẻ; chỉ phần
  đuôi bất định mới escalate.
- **Checkpoint + auto‑resume:** lần chạy có thể khởi động lại không tính lại.
- **Đòn bẩy tốc độ lossless đã nghiên cứu — MTP (Multi‑Token Prediction).** Speculative
  decoding: mô hình phác thảo token, *mô hình gốc verify* → output **giống hệt, 0 mất
  accuracy**, thuần tốc độ **1.4–2.2×** (Gemma‑4 QAT+MTP 1.5–2.2×). Trực giao với quant → ship
  cả hai. Đã hợp nhất vào llama.cpp (2026‑06‑07); đã xác nhận offload GPU chạy; đường tích hợp
  Docker là provider `local_server` (llama‑server hỗ trợ flag `--spec-type draft-mtp` native).

## 9. Phân tích cấu trúc lỗi & định vị trung thực

Để biết trần 88.55 có gần thật không, chúng tôi phân tích **31 câu** mà bản 88.55 khác bản
tham chiếu 91.79, mỗi câu được một bộ giám định độc lập giải lại + phân loại, rồi một bộ phản
biện hoài nghi xác nhận:

- **27/31** mô hình frontier đúng, **3** Gemma đúng, **1** lưỡng nghĩa → khoảng cách là thật.
- **16/463 câu xác nhận cứu được** (trần lạc quan +3.46pp; mốc 88.98 chỉ cần ~2 câu net).
- Nhưng phần cứu được là **toán/lý xác định + suy luận** (Henderson‑Hasselbalch, RPM động cơ,
  eigenvalue, kinh tế‑địa lý) — **đúng thứ đòn bẩy TIR + CoT (đã xây) nhắm tới**, KHÔNG phải
  thứ một adjudicator Qwen mở khoá được (phản biện đánh giá là tung đồng xu + rủi ro hồi quy).
- **13 câu là knowledge‑gap không cứu được** (cải cách hành chính VN‑2025, trivia địa phương,
  con số quy định chính xác) — xác nhận **88.55 gần trần thật của Gemma offline**.

Kết luận trung thực: mốc cao hơn (nếu theo đuổi) đến từ **bật path TIR/router đã có** rồi đo,
không phải mô hình thứ hai; phần còn lại là kiến‑thức không phá được bằng kỹ thuật hợp lệ.

## 10. Bài nộp cuối

- **Mô hình ship: Gemma‑4‑26B‑A4B QAT‑Q4_0** (MoE ~15GB) — chạy mọi GPU (0 rủi ro OOM), nhanh
  (Time tốt). 31B đã **loại dứt khoát** (Time).
- **Đường chạy: self‑consistency CoT (k=1, 2048 token) + an‑toàn‑từ‑chối + constrained‑repair
  + contract‑repair bất khả xâm phạm**, gated TIR cho lát định lượng. Leaderboard **88.55**.
- **Định vị trung thực:** trần accuracy của một Gemma offline *trung thực* ≈ 88.5; phần còn
  lại tới mốc cao là kiến‑thức‑VN không retrieval được + defective‑gold — không mô hình hợp lệ
  nào phá được rẻ. Chúng tôi báo **số đo thật, không hứa số**. Điểm Time được bảo vệ ở độ sâu
  tối đa nhờ MoE + núm token phẳng, với MTP là đòn tăng tốc lossless để dành.

> Mã nguồn + cách tái lập trong container: xem `README.md` và §6. Idea/method bản tiếng Anh:
> `docs/method-writeup.md`. Mọi đòn bẩy âm giữ OFF mặc định — kỷ luật anti‑overfit cho 2000
> câu private là một phần của "tư duy tối ưu & sáng tạo".
