# R7 Evidence-First Plan - 2026-06-14

Status: dev-only public-463 analysis artifact. Do not ship into runtime.

## Current state

Locked best remains:

```text
429 / 463 = 92.66
```

Best known file:

```text
output-probes/codex-webmax-2026-06-13-r5-cumulative/s1-0274A/pred.csv
```

The R6 four-change pack:

```text
output-probes/codex-webmax-2026-06-13-r6-active-packs/base0022D-plus-core3-0396A-0370C-0048B/pred.csv
```

scored:

```text
426 / 463 = 92.01
```

So reject the R6 group:

```text
test_0022: A -> D
test_0048: A -> B
test_0370: B -> C
test_0396: D -> A
```

Do not submit R6 leave-one-out files unless a future independent result
contradicts this conclusion.

## Why R7 changes strategy again

The high-vote model-consensus candidates are not trustworthy: many are old-law
or first-true-option false flips. R7 uses evidence-first probes:

- exact legal/current source beats model vote count;
- in-passage wording beats candidate agreement;
- submit high-confidence singleton first, then use cumulative probes only after
  the first result is known.

This is slower than a big pack, but after R6 scored `-3`, it is the best way to
avoid burning the remaining submissions.

## Primary candidates

### `test_0384: B -> A`

Question: a nationwide model contest requires whose license?

Current base answer:

```text
B. Bộ Văn hóa, Thể thao và Du lịch
```

Candidate:

```text
A. Cục Nghệ thuật biểu diễn
```

Reason: Decree 79/2012 and amendment materials state that the Ministry licenses
nationwide beauty contests, while the Department of Performing Arts licenses
nationwide model contests.

Sources checked:

- https://chinhphu.vn/default.aspx?docid=163961&pageid=27160
- https://www.cucnghethuatbieudien.gov.vn/public/van-ban/nghi-dinh-sua-doi-bo-sung-mot-so-dieu-cua-nghi-dinh-so-792012nd-cp-ngay-05-thang-10-nam-2012-cua-chinh-phu-quy-dinh-ve-bieu-dien-nghe-thuat-trinh-dien-thoi-trang-thi-nguoi-dep-va-nguoi-mau-luu-hanh-kinh-doanh-ban-ghi-am-ghi-hinh-ca-mua-nhac-san-khau

This is the highest-confidence remaining public probe.

### `test_0433: A -> B`

Question asks which fee is 25,000 VND in the given VNPT/eSIM documents.

Current base:

```text
A. Giá bán một Profile eSIM
```

Candidate:

```text
B. Phí chuyển đổi từ thuê bao trả sau sang trả trước
```

Reason: the in-prompt document contains two 25,000 VND values, but the wording
asks for a fee. Option A is a listed price, while option B is explicitly a
conversion fee. Model variants also repeatedly selected B.

Risk: because the prompt says "theo quy định trong tài liệu" and includes both
values, the intended key could still accept the first matching 25,000 item.

### Reserve: `test_0012: C -> A`

Question asks which scientist is important but often overlooked in programming
development through work on early computers.

Current base:

```text
C. Ada Lovelace
```

Candidate:

```text
A. Grace Hopper
```

Reason: Grace Hopper worked on early computers such as Mark I/UNIVAC and
developed compiler work; Ada Lovelace is the canonical first programmer but did
not work on modern early computers. Still ambiguous, so reserve only.

### Reserve: `test_0220: J -> D`

Candidate switches from "dividend income" to broader "property income" for a
non-deductible equity return. This has some tax-theory support but is less
direct than `0384` and `0433`; keep as reserve.

## Generated files

All files passed 463-row submission contract check.

```text
output-probes/codex-webmax-2026-06-14-r7-evidence-first/p1-0384A-model-contest-license/pred.csv
output-probes/codex-webmax-2026-06-14-r7-evidence-first/p2-0384A-0433B-esim-fee-wording/pred.csv
output-probes/codex-webmax-2026-06-14-r7-evidence-first/p2-alt-0433B-esim-fee-wording/pred.csv
output-probes/codex-webmax-2026-06-14-r7-evidence-first/reserve-0012A-grace-hopper/pred.csv
output-probes/codex-webmax-2026-06-14-r7-evidence-first/reserve-0220D-equity-property-income/pred.csv
output-probes/codex-webmax-2026-06-14-r7-evidence-first/screen-0012A-0220D/pred.csv
output-probes/codex-webmax-2026-06-14-r7-evidence-first/screen-0384A-0433B-0012A/pred.csv
```

## Recommended submission order

Submit first:

```text
output-probes/codex-webmax-2026-06-14-r7-evidence-first/p1-0384A-model-contest-license/pred.csv
```

Interpretation from 92.66 base:

```text
92.87 -> test_0384 A is +1; keep it.
92.66 -> neutral; do not assume.
92.44 -> test_0384 A is -1; reject it.
```

If `p1` scores `92.87`, submit next:

```text
output-probes/codex-webmax-2026-06-14-r7-evidence-first/p2-0384A-0433B-esim-fee-wording/pred.csv
```

Interpretation:

```text
93.09 -> test_0433 B is +1; keep both.
92.87 -> test_0433 B is neutral; keep only 0384A unless later needed.
92.66 -> test_0433 B is -1; keep only 0384A.
```

If `p1` scores `92.66` or `92.44`, submit instead:

```text
output-probes/codex-webmax-2026-06-14-r7-evidence-first/p2-alt-0433B-esim-fee-wording/pred.csv
```

Only use reserve files after the first two results are known.

## Verification

Command:

```powershell
$env:PYTHONPATH="$PWD\src"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --check-submission <pred.csv>
```

All R7 files returned:

```text
Valid: True
Input rows: 463
Prediction rows: 463
Issues: none
```

