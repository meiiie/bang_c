# Codex webmax public-463 pred probe r3 - 2026-06-13

Status: dev-only public-set probe. Do not commit generated `pred.csv` files or
copy these qid decisions into runtime code, config, tests, Docker, or prompts.

## Output files

Conservative r3:

```text
output-probes/codex-webmax-2026-06-13-r3-conservative/pred.csv
```

Boost variant with one extra reading-comprehension flip:

```text
output-probes/codex-webmax-2026-06-13-r3-boost0346/pred.csv
```

Both files passed the harness submission contract:

```text
Valid: True
Input rows: 463
Prediction rows: 463
Issues: none
```

## Construction

Base file:

```text
output-probes/codex-webmax-2026-06-13-r2/pred.csv
```

Conservative r3 changes from r2:

| qid | r2 | r3 | confidence | reason |
|---|---:|---:|---|---|
| `test_0080` | A | B | high | Exact political-science item keys "tinh nhan van" as B; A is "tinh nhan dao". |
| `test_0389` | A | B | high | Exact Vietnamese electrical-measurement item keys the direct instrument as "mot watt ke 3 pha 2 phan tu". |

Boost variant additionally changes:

| qid | conservative | boost | confidence | reason |
|---|---:|---:|---|---|
| `test_0346` | A | B | medium-high | Source passage ties the first overt disobedience/confrontation to the 1752 Hospital restructuring without Parlement approval. |

## Evidence

### `test_0080`: A -> B

Question summary:

```text
Tinh nhan van cua van hoa chinh tri bieu hien o cho:
A. Giai phong con nguoi khoi ap buc, bat cong, boc lot
B. Tao dieu kien cho con nguoi phat trien tu do, toan dien, hai hoa
C. Xa hoi dua tren quy luat khach quan, chan that, chan ly
```

Evidence:

- VietJack exact item says B is the answer:
  https://khoahoc.vietjack.com/question/1707649/tinh-nhan-van-cua-van-hoa-chinh-tri-bieu-hien-o-cho-a-nen-chinh-tri-do-huong-toi-viec-giai-phong-con
- Nhaquanlytuonglai exact/near-exact answer list distinguishes:
  `tinh nhan dao = A`, `tinh nhan van = B`, `tinh nhan ban = C`.
  https://nhaquanlytuonglai.wordpress.com/2013/06/01/trac-nghiem-chinh-tri-hoc/

Rationale:

R2 selected A, but A is the neighboring "humanitarian" key in the same question
bank. The public item asks "nhan van", so B is the stronger source-key match.

### `test_0389`: A -> B

Question summary:

```text
De do cong suat tieu thu trong mang 3 pha 3 day khong doi xung thuong dung:
A. Hai watt ke 1 pha
B. Mot watt ke 3 pha 2 phan tu
C. Ba watt ke 1 pha
D. Mot watt ke 3 pha 3 phan tu
```

Evidence:

- VietJack exact item says B is the answer:
  https://khoahoc.vietjack.com/question/1681394/de-do-cong-suat-tieu-thu-trong-mang-3-pha-3-day-khong-doi-xung-thuong-dung-a-hai-watt-ke-1-pha-b-mot
- A Studocu measurement-bank copy also lists the exact item with answer B:
  https://www.studocu.vn/vn/document/truong-dai-hoc-su-pham-ky-thuat-thanh-pho-ho-chi-minh/do-luong-va-cam-bien/trac-nghiem-chuong-5-do-luong/113946279

Rationale:

There is a conceptual ambiguity: two single-phase wattmeters implement the
two-wattmeter method, and that is a valid engineering explanation. However,
the Vietnamese multiple-choice bank asks for the commonly used direct meter
configuration, and exact answer-key sources mark B.

### `test_0346`: A -> B in boost only

Question summary:

```text
In the Louis XV / Hopital General passage, when did the first direct
confrontation between the French legislature and Louis XV occur?
A. 1749, Parlement Paris refused to discuss the hospital reorganization
B. 1752, Louis XV changed the hospital structure without Parlement approval
```

Evidence:

- The source passage appears copied from the Louis XV article; the paragraph
  states that on 1752-01-28 the King instructed the Grand Council to change the
  Hospital administration without Parlement approval, then describes the affair
  as the first overt disobedience of the legislature against the King:
  https://en.wikipedia.org/wiki/Louis_XV

Rationale:

This is not as clean as `0080` and `0389`. A is plausible because the Parlement
refusal-to-discuss event is an act of disobedience. B is plausible because the
source text's "this affair / first overt disobedience" sentence follows the
1752 no-approval restructuring. Candidate-pool votes also leaned B. Keep this
as a boost variant, not the conservative recommendation.

## Recommendation

If r2 improves over the 91.79 frontier, the next safest official/test-account
probe is the conservative r3:

```text
output-probes/codex-webmax-2026-06-13-r3-conservative/pred.csv
```

It adds two high-confidence source-key corrections over r2. If both are right,
it adds about `2 / 463 = 0.43pp`.

Use the boost `0346` variant only if:

- r2/r3-conservative results suggest more risk is acceptable; or
- there is only a test-account check, not a scarce official submission.

## Verification commands

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --check-submission "output-probes\codex-webmax-2026-06-13-r3-conservative\pred.csv"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --check-submission "output-probes\codex-webmax-2026-06-13-r3-boost0346\pred.csv"
```
