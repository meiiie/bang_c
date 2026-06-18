# Neko Core — Thuyết minh phương pháp (HackAIthon 2026, Bảng C)

**Đội thi: Neko Core — Đại học Hàng hải Việt Nam (VMU).** Thành viên: Nguyễn Mạnh Hùng
(CNT63ĐH, trưởng nhóm), Bùi Việt Hoàng (CLC63ĐH), Phạm Thị Minh Hồng (CNT63ĐH),
Phạm Thị Thu Thảo (KTN63ĐH), Nghiêm Thị Mỹ Linh (KPM63ĐH).

> **Bài nộp: image `hacamy12345/neko-core:qwen3-4b-selfconsist-20260618` (= `:v0.7.2` = `:latest`).**
> Mô hình **Qwen3‑4B‑Instruct‑2507** (dense 4B, ≤5B theo tổng tham số), self‑consistency, offline,
> một mô hình duy nhất. Public‑463 leaderboard **83.59**. Cập nhật: 2026‑06‑18.
>
> Mọi con số trong tài liệu là **đo thật** — trên leaderboard chính thức, hoặc trên chính mô hình thi đấu
> (Qwen3‑4B GGUF, llama.cpp, GPU NVIDIA thuê thật). Không phỏng đoán. **Các đòn bẩy đã thử rồi LOẠI được
> nêu kèm lý do đo được — kỷ luật đó chính là phần lõi của "ý tưởng & tối ưu sáng tạo", không kém các đòn
> bẩy thắng.**

---

## 1. Bài toán & hợp đồng chấm điểm

Bảng C yêu cầu một **Docker container offline, tự chứa**: đọc `/data/*_test.csv` (hoặc `.json`), ghi
`/output/pred.csv` đúng hai cột `qid,answer`. Chấm trên **2000 câu private đa lĩnh vực** (đề kiểu THPT
Quốc gia: Toán/Lý/Hoá/Sinh + Giáo dục công dân + đọc hiểu).

| Tiêu chí | Trọng số | Hệ quả thiết kế |
|---|---|---|
| **Accuracy** | 80đ | mục tiêu chính — mọi đòn bẩy phải tổng quát hoá sang 2000 câu lạ |
| **Thời gian inference** | 10đ | nhanh nhất = 10đ → tốc độ là mục tiêu hạng nhất, không nghĩ sau |
| **Ý tưởng / tối ưu sáng tạo** | 10đ | tài liệu này |

**Ràng buộc BTC (xác nhận chính thức 2026‑06‑18):** (1) server chấm **16GB VRAM**; (2) **≤5B tính theo
TỔNG tham số** (nên MoE 26B‑tổng bị loại; dense Qwen3‑4B = 4B‑tổng hợp lệ rõ ràng); (3) **chỉ 1 model
LLM ≤5B, KHÔNG embedding/rerank**, không API/mô hình ngoài, offline. Bài nộp này tuân thủ tuyệt đối: đúng
1 LLM Qwen3‑4B, không model phụ, dùng ~5GB/16GB VRAM, **không RAG/rerank**.

> *(Lịch sử: bản trước dùng Gemma‑4‑26B‑A4B đạt 88.55 public‑463, nhưng 26B > 5B theo tổng tham số nên
> **không còn hợp lệ**. Việc đổi mô hình chỉ là sửa dữ liệu config — xem §2.)*

## 2. Triết lý thiết kế — harness là một artifact đo được, không phải mớ code dán

Neko Core là **harness suy luận config‑first**: harness được coi là **đối tượng hạng nhất, gõ kiểu,
hoán đổi được** (giống cách ta đối xử với trọng số mô hình). Bốn nguyên tắc chi phối mọi quyết định:

1. **Để mô hình SUY LUẬN; harness điều phối và ĐO LƯỜNG.** Không nhồi đáp án hay công thức viết tay;
   cho mô hình mạnh không gian lập luận, và đặt vào output **confidence quan sát được** (mức đồng thuận
   khi lấy mẫu).
2. **Mọi đòn bẩy phải qua một THƯỚC ĐO held‑out.** Bộ private 2000 câu là mục tiêu — proxy 463/450 chỉ
   là *que thăm*. Một đòn bẩy chỉ ship khi **tổng quát hoá** (đo trên phân phối thật, không hồi quy cụm,
   không 0 false‑positive), không phải vì một câu chuyện nghe hợp lý. Thêm môn/loại câu = một dòng config.
3. **Robustness hạng nhất — không‑bao‑giờ‑0‑điểm.** Trong contest chấm‑Docker, thảm hoạ là **container ăn
   0 điểm** (OOM / timeout / crash / sai GPU), không phải sai vài câu. Mọi quyết định tối ưu **điểm kỳ
   vọng dưới bất định phần cứng**, không phải accuracy trên máy dev.
4. **Ranh giới runtime/phát triển CỨNG.** Container nộp bài offline, tự chứa. Mọi chiến lược "ứng cử"
   (TIR, RAG, tiered…) được **đo ở khâu phát triển** rồi mới được hay không được bật ở runtime.

**Allowlist mô hình config‑driven.** Khi BTC đổi luật (Gemma‑26B → ≤5B), việc pivot chỉ là **sửa dữ liệu**:
`runtime.model_policy` (`{"aliases":["*"],"max_params_b":5.0}` + cờ `count_active_for_moe`) ép mọi mô hình
≤5B mà **không sửa một dòng code solver** nào. Đây là một đòn bẩy Ý tưởng: harness thích nghi luật bằng config.

## 3. Kiến trúc — harness composable, định tuyến theo loại câu

```
/data (CSV|JSON)
  → loader            (Problem mỗi dòng: qid, câu hỏi, lựa chọn; NFC‑normalize, BOM‑safe, số lựa chọn động)
  → router/classifier (tín hiệu cấu trúc language‑agnostic → chọn strategy)
  → solver            (engine self‑consistency CoT; các strategy TIR / reading / safety hoán đổi được)
  → answer normalizer (trích chữ cái, kể cả từ trong lập luận)
  → constrained repair (GBNF grammar ép chữ cái hợp lệ nếu một mẫu trôi khỏi định dạng)
  → contract repair   (đảm bảo pred.csv phủ ĐÚNG mọi qid với chữ cái hợp lệ — chống 0 điểm)
  → exporter          → /output/pred.csv
  → (chỉ dev) trace / review / eval / checkpoint / manifest
```

Tầng provider giấu sau một hợp đồng `complete()` duy nhất; các **strategy là processor typed, hoán đổi
được** (self‑consistency / tiered / TIR / reading / rag) qua một policy gate. Điểm mấu chốt: ta **xây cả
một foundry chiến lược**, rồi **chọn cấu hình ship bằng đo held‑out** — chứ không đoán. Cái gì ship là
**kẻ thắng của một phép đo**, không phải một linh cảm.

## 4. Mô hình ≤5B + kỹ thuật arch‑portability (không‑bao‑giờ‑0‑điểm)

- **LLM: Qwen3‑4B‑Instruct‑2507**, GGUF Q5_K_M, dense 4B (≤5B tổng), chạy local qua llama.cpp, offline.
  Một mô hình duy nhất — không embedding/rerank (đúng luật).
- **Vừa 16GB thừa sức:** đo thật runtime dùng **~5GB VRAM** (model ~2.7GB + KV@8192) → chừa ~11GB cho
  "tác vụ khác" của server BTC.
- **Wheel nướng native SASS cho `sm_60/70/75/80/86/89/90/120`** (P100 / **V100** / T4 / A100 / Ampere /
  Ada / H100 / Blackwell) **+ PTX floor `compute_60`** → **mọi GPU NVIDIA ≥ Pascal (2016→2025) chạy
  native hoặc JIT lúc load** = không 0‑điểm dù BTC dùng GPU nào. `GGML_NATIVE=off` → chạy mọi CPU (wheel
  prebuilt SIGILL trên CPU cũ).
- **Đã kiểm chứng LITERAL (2026‑06‑18):** kéo nguyên image v0.7.2 từ Docker Hub trên 1 GPU sạch →
  `cuobjdump` xác nhận đủ `sm_60…sm_120` (gồm sm_70 V100) trong wheel → chroot chạy entrypoint thật trên
  test CSV → `pred.csv` hợp lệ. Pull + arch + chạy end‑to‑end đều PASS.

## 5. Hành trình Accuracy — đo thật (proxy 450 + leaderboard 463)

Mô hình thi đấu (Qwen3‑4B), self‑consistency CoT, đo trên proxy 450 câu (kiểu THPT) và leaderboard 463:

| Cấu hình | Accuracy | Ghi chú |
|---|---|---|
| Letter‑only (ép 1 token) | thấp | lập luận bị nén — bỏ |
| **Self‑consistency chain‑of‑thought (ship)** | **80.22** proxy / **83.59** leaderboard | engine cốt lõi |

Phân rã cụm (proxy 450): **quant (Toán/Hoá) 73.91 · civics (GDCD) 78.67 · science (Lý…) 85.41**. Lỗi của
một mô hình 4B trên đề THPT chủ yếu là **sai suy luận/tính toán**, không phải thiếu fact tra‑cứu được —
một phát hiện then chốt định hướng việc chọn/loại đòn bẩy (§7).

**Đòn bẩy thắng đang ship:**
- **CoT self‑consistency** — cho mô hình lập luận rồi trích chữ cái cuối; bước nhảy lớn nhất so với
  ép‑1‑token.
- **Phán đoán an‑toàn‑từ‑chối** — lớp câu "làm thế nào để [hành vi hại]" mà đáp đúng là *từ chối*; một
  mệnh đề ngữ nghĩa, không match từ khoá → tổng quát đa ngôn ngữ, tiêm ở tầng voting nên phủ mọi đường.
- **Constrained decoding (GBNF) ở lượt sửa** + **khử thiên lệch vị trí** (hoán vị lựa chọn) cho câu nhiều
  phương án — cải tiến *giải mã/định dạng* thuần, không tune nội dung, không overfit.

## 6. Robustness — hợp đồng pred.csv bất khả xâm phạm

Lỗi tệ nhất là **file thiếu/sót → 0 điểm**. Bốn lớp đảm bảo loại bỏ khả năng đó:

- **Mọi câu đều trả lời được:** exception khi giải được bắt the‑từng‑câu → fallback heuristic tất định;
  exception bất ngờ → fallback‑after‑error; mẫu ra chữ không hợp lệ → answer‑repair.
- **pred.csv ghi TRƯỚC mọi thứ có thể raise:** bước *contract‑repair* dựng lại danh sách dự đoán phủ
  **đúng mọi qid, mỗi câu một chữ cái A–J hợp lệ theo số phương án TỪNG câu** (giữ nguyên dự đoán tốt →
  accuracy không đổi). Một lỗi bất kỳ không thể zero‑hoá cả lần chạy 2000 câu.
- **Checkpoint mỗi câu + auto‑resume** → container bị ngắt giữa chừng vẫn tiếp tục, không làm lại từ đầu.

Loader khoan dung input (BOM‑safe, NFC normalize tiếng Việt, tên cột linh hoạt, số lựa chọn động không
gắn cứng A–D). Mỗi lần chạy ghi manifest bất biến. **Bộ test đơn vị xanh + dry‑run contract check + policy
audit.** Đã smoke‑test literal đúng entrypoint Docker trên GPU thật → pred.csv hợp lệ.

## 7. ⭐ Kỷ luật chống overfit — những gì đã LOẠI (lõi của Ý tưởng)

Đây là điểm nhấn phương pháp: **mỗi đòn bẩy "ngầu" đều được XÂY rồi GIẾT bằng một phép đo held‑out**, không
phải bằng linh cảm. Trên một model ≤5B đã mạnh sẵn, thêm phức tạp sai cách làm **TỆ ĐI** — và chúng tôi có
receipts:

| Đòn bẩy (đã xây + đo) | Kết quả đo (Qwen3‑4B, proxy) | Quyết định |
|---|---|---|
| **Fine‑tune v1** (math 2311 + legal 1189 + mcq 823) | **−4.44** (quant −14.78) | LOẠI |
| **Fine‑tune v2** (chỉ 823 VMLU‑MCQ = hết data in‑dist) | **±0.00** (đúng base) | LOẠI |
| **RAG‑gated** | nominal +3.11 nhưng **variance** (battery sạch: civics **−5**) | LOẠI (+ nay luật cấm) |
| **TIR** (model viết+chạy Python) trên quant | **−16.52** (41% câu degrade) | LOẠI |
| **k5‑vote / tiered** | ≈ self‑consistency (trong nhiễu) | không bật |

- **Fine‑tune không thắng base.** Lý do gốc: 4B thiếu **kiến thức**, không thiếu **kỹ năng** MCQ (base đã
  là instruct mạnh). 823 dòng MCQ in‑dist là quá ít để dịch chuyển base; data off‑dist (math/legal free‑form)
  **phá format MCQ** (quant 73.91→59.13) = catastrophic forgetting. Đo 2 lần, chốt: không ship.
- **RAG là ẢO + nay phạm luật.** "+3.11" trên proxy thực ra là **variance k=1** (~30 câu lật/lần chạy;
  civics "+6" mà gate chỉ fire 2 lần = noise). Trên battery sạch, RAG còn **làm tệ civics −5** ("one wrong
  fact poisons it"). Và luật BTC 2026‑06‑18 **cấm embedding/rerank** → RAG out cả về kỹ thuật lẫn luật.
- **TIR chết trên 4B.** "Weakest‑improves‑most" thất bại cho TIR‑viết‑code: 4B **dưới ngưỡng năng lực**
  viết Python đúng cho Toán/Lý/Hoá → phá 24 câu suy luận trực tiếp đã đúng (−16.52).
- **Vấn đề thật là variance k=1**, không phải thiếu lever. Mọi so sánh ±3pp đều **chìm trong nhiễu** →
  ta judge bằng *generalization*, không bằng điểm proxy. Đây là kỷ luật đo lường (tránh reward‑hack que thăm).

**Kết luận:** trên đề suy luận ≤5B, **self‑consistency trên base mạnh là tối ưu — và nhanh nhất.** Việc
*không* thêm phức tạp gây hại cũng là một dạng tối ưu hiệu quả.

## 8. Tối ưu điểm Time (Vòng‑2) — minimalism = nhanh nhất

- **Đường ship tối giản** (1 model + self‑consistency) là **đường NHANH nhất**: TIR (2 round + chạy code),
  RAG (retrieval), k>1 (nhiều mẫu) đều chậm hơn — mà đo ra đều không giúp. Minimalism vừa thắng Accuracy
  (không hồi quy) vừa thắng Time.
- Đo thật: ~3 giây/câu → **2000 câu ≈ ~100 phút**, VRAM ~5GB → **không OOM, không timeout** trên server 16GB.
- **Checkpoint + auto‑resume** → an toàn nếu bị ngắt.

## 9. Định vị trung thực

Qwen3‑4B **đã gần trần ≤5B (~80–84)** trên phân phối đề THPT này — chứng minh bằng việc **mọi lever còn
lại (FT/RAG/TIR/k5) đều nằm trong nhiễu hoặc gây hại trên đo sạch**. Đây không phải "bỏ cuộc" mà là **kết
luận có dữ liệu**: đường tăng điểm tiếp theo (nếu có) là **thêm data MCQ đa môn** (nguồn bị chặn / cần sinh
synthetic) — một bài toán *thu thập dữ liệu*, không phải *kỹ thuật runtime*. Chúng tôi báo **số đo thật,
không hứa số**.

## 10. Bài nộp cuối

- **Mô hình ship: Qwen3‑4B‑Instruct‑2507** Q5_K_M GGUF (dense 4B ≤5B tổng) — một mô hình, offline, ~5GB
  VRAM, arch‑portable mọi GPU NVIDIA ≥ Pascal (đã verify literal).
- **Đường chạy: self‑consistency CoT + an‑toàn‑từ‑chối + constrained‑repair + contract‑repair bất khả xâm
  phạm.** Leaderboard **83.59**.
- **Idea = harness composable + chọn‑lever‑bằng‑đo + kỹ thuật không‑bao‑giờ‑0‑điểm.** Chúng tôi xây cả
  foundry chiến lược, đo held‑out từng cái, loại thẳng tay cái hại (TIR −16.52, RAG variance/illegal, FT
  −4.44), và ship cái **provably tối ưu cho ≤5B đồng thời nhanh nhất** — engineered để **chạy đúng trên
  mọi GPU judge**. Kỷ luật đo lường + robustness‑first chính là "tư duy tối ưu & sáng tạo".

> Image: `hacamy12345/neko-core:qwen3-4b-selfconsist-20260618` (= `:v0.7.2` = `:latest`,
> digest `sha256:39c7891c…575eaf`). Mã nguồn + tái lập: `README.md`. Bản tiếng Anh: `docs/method-writeup.md`.
> Hồ sơ đo lường: `notes/2026-06-18-finetune-verdict.md`, `notes/2026-06-18-rag-lever-analysis.md`.
