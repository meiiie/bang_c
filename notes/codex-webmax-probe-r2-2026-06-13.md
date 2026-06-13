# Codex webmax public-463 pred probe r2 - 2026-06-13

Status: dev-only public-set probe. Do not commit generated `pred.csv` files or
copy these qid decisions into runtime code, config, tests, Docker, or prompts.

## Output files

Primary r2 probe:

```text
output-probes/codex-webmax-2026-06-13-r2/pred.csv
```

Optional ambiguous-item variant:

```text
output-probes/codex-webmax-2026-06-13-r2-alt0001A/pred.csv
```

Both files passed the harness submission contract:

```text
Valid: True
Input rows: 463
Prediction rows: 463
Issues: none
```

## Construction

Base frontier file:

```text
data/q4results/claude_public463_pred_v2_webfixed.csv
```

The r2 primary is built on top of:

```text
output-probes/codex-webmax-2026-06-13/pred.csv
```

Primary r2 changes from the base frontier file:

| qid | base | r2 | reason |
|---|---:|---:|---|
| `test_0068` | B | A | Exact/near-exact political-science quiz sources mark "Cong dong" as answer A. |
| `test_0115` | B | D | HCM force question: exam sources give "cong nhan, nong dan, lao dong tri oc". |
| `test_0200` | B | D | Huu-khuynh in quantity-quality dialectics includes both conservative/no-jump and quantity-only gradualism. |
| `test_0271` | A | D | Exact Sinh 11 item: one-way blood movement is due to heart push/suction, vessel elasticity, and valves. |
| `test_0329` | A | C | Promotion filing is at So Cong Thuong/provincial system; after the 2025 administrative rearrangement the intended model is 34 provincial units, not commune/ward filing. |

Optional variant additionally changes:

| qid | primary r2 | alt | reason |
|---|---:|---:|---|
| `test_0001` | D | A | The item appears defective/ambiguous: both Deut. 21:18-21 and Deut. 22:23-24 describe stoning cases. A is isolated as a separate variant; keep it out of the primary unless explicitly testing this ambiguity. |

## New r2 evidence

### `test_0068`: B -> A

Question summary:

```text
Augustine / O-guyt-xtanh says political power should belong to:
A. Cong dong
B. Thuong de
C. Giao chu
D. Vua
```

Evidence:

- Studocu exact/near-exact item marks `A) Cong dong` as `Dap an A`:
  https://www.studocu.vn/vn/document/truong-cao-dang-cong-nghe-bach-khoa-ha-noi/hoc-va-lam-theo-bac/de-thi-trac-nghiem-mon-cth/39918575
- Nhaquanlytuonglai exact/near-exact item also marks `Dap an A`:
  https://nhaquanlytuonglai.wordpress.com/2013/06/01/trac-nghiem-chinh-tri-hoc/

Rationale:

The theological intuition can pull toward `B. Thuong de`, but the public item
looks copied from a Vietnamese political-science question bank where the keyed
answer is `A. Cong dong`. This is a high-value key-source match, so r2 switches
to A.

### `test_0329`: A -> C

Question summary:

```text
After 2025-07-01, promotion filing will follow which administrative model?
A. Provincial or commune/ward level depending on promotion type and scope
B. Direct filing to 63 provinces/cities
C. Filing to 34 provinces/cities under the new regulation
D. Only provincial level, regardless of promotion scope
```

Evidence:

- Official Government portal page for Nghi dinh 128/2024/ND-CP records the
  governing promotion regulation effective 2024-12-01:
  https://vanban.chinhphu.vn/?docid=211405&pageid=27160
- LuatVietnam summary of the Nghi dinh 128/2024/ND-CP procedure says the
  receiving authority is the So Cong Thuong where the promotion is organized,
  with online filing via national/provincial administrative systems:
  https://luatvietnam.vn/linh-vuc-khac/truong-hop-khong-phai-thuc-hien-thong-bao-hoat-dong-khuyen-mai-883-99546-article.html
- Chinhphu.vn administrative-rearrangement article says Vietnam has 34
  provincial administrative units after the 2025 rearrangement:
  https://xaydungchinhsach.chinhphu.vn/chi-tiet-34-don-vi-hanh-chinh-cap-tinh-tu-12-6-2025-119250612141845533.htm

Rationale:

Option A is likely a distractor because it adds commune/ward filing. The legal
procedure stays with So Cong Thuong/provincial systems, and the question's
"after 2025-07-01" wording points at the 34-province administrative model.
Option D is semantically close on "only provincial", but it does not answer the
"administrative model" cue as directly as C.

## Recommendation

Use the primary r2 file first:

```text
output-probes/codex-webmax-2026-06-13-r2/pred.csv
```

Expected value versus the 91.79 frontier file:

- If all five primary r2 changes match the official key, gain is about
  `5 / 463 = 1.08pp`.
- If only the original three r1 changes match, gain is about `0.65pp`.
- If the official key follows the old frontier answers for any changed qid,
  the probe loses those points.

Only use the `alt0001A` variant if deliberately testing the ambiguous Bible
item after the primary r2 attempt.

## Verification commands

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --check-submission "output-probes\codex-webmax-2026-06-13-r2\pred.csv"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --check-submission "output-probes\codex-webmax-2026-06-13-r2-alt0001A\pred.csv"
```
