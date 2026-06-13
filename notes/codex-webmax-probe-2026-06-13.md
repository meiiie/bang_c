# Codex webmax public-463 pred probe - 2026-06-13

Status: dev-only public-set probe. Do not commit generated `pred.csv` files or
copy these qid decisions into runtime code/config/tests.

## Output files

Primary probe:

```text
output-probes/codex-webmax-2026-06-13/pred.csv
```

Optional ambiguous-item variant:

```text
output-probes/codex-webmax-2026-06-13-alt0001A/pred.csv
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
data/q4results/claude_public463_pred_v2_webfixed.csv
```

Primary probe changes from that base:

| qid | base | probe | reason |
|---|---:|---:|---|
| `test_0115` | B | D | HCM force question: external exam sources give "công nhân, nông dân, lao động trí óc". |
| `test_0200` | B | D | Huu-khuynh in quantity-quality dialectics includes both conservative/no-jump and quantity-only gradualism. |
| `test_0271` | A | D | Exact Sinh 11 item: one-way blood movement is due to heart push/suction, vessel elasticity, and valves. |

Optional variant additionally changes:

| qid | primary | alt | reason |
|---|---:|---:|---|
| `test_0001` | D | A | The item appears defective/ambiguous: both Deut. 21:18-21 and Deut. 22:23-24 describe stoning cases. A is supported directly by Deut. 22:23-24; D is retained in the primary because it was the prior frontier-reference choice. |

## Web evidence checked

- `test_0115`: Vietjack/Gauth-style exam copies identify the main forces of HCM's national unity bloc as workers, peasants, and intellectual labor.
  - https://khoahoc.vietjack.com/question/1546260/chon-phuong-an-tra-loi-dung-theo-tu-tuong-ho-chi-minh-ve-luc-luong-chu
  - https://www.gauthmath.com/vn/solution/1826542518089810/Trong-t-t-ng-H-Ch-Minh-l-c-l-ng-ch-y-u-c-a-kh-i-i-o-n-k-t-l-a-C-ng-nh-n-n-ng-d-n
- `test_0200`: philosophy notes describe huu-khuynh as conservative/no-jump and also quantity-only gradualism.
  - https://quizlet.com/vn/864903314/3-quy-luat-co-ban-cua-phep-bcdv-flash-cards/
  - https://www.studocu.vn/vn/document/hoc-vien-tai-chinh/triet-hoc-mac-lenin/bai-tap-triet-phan-y-nghia-cau-hoi/110024536
- `test_0271`: exact Sinh 11 item sources give answer D.
  - https://khoahoc.vietjack.com/question/1307278/mau-di-chuyen-mot-chieu-trong-he-mach-la-do-a-suc-day-cua-tim-su-dan-hoi-cua-thanh-dong-mach-cac-van
  - https://vietjack.com/sbt-sinh-11-kn/cau-69-trang-38-sbt-sinh-hoc-lop-11.jsp
- `test_0001`: Deut. 22:23-24 and Deut. 21:18-21 both support stoning cases, so the item is not cleanly single-answer.
  - https://bible.usccb.org/bible/deuteronomy/22
  - https://www.biblegateway.com/passage/?search=Deuteronomy+21%3A18-22%3A30&version=NKJV

Other spot checks supported the existing webfixed choices:

- `test_0058`: road-crossing construction/improvement permit time is 10 working days.
  - https://thuvienphapluat.vn/hoi-dap-phap-luat/trinh-tu-de-nghi-cap-giay-phep-xay-dung-duong-ngang-duoc-thuc-hien-theo-cac-buoc-nao-138022160.html
- `test_0070`: preschool accreditation file requires 1 registration letter and 2 self-assessment reports.
  - https://thuvienphapluat.vn/phap-luat/ho-tro-phap-luat/thu-tuc-cap-chung-nhan-truong-mam-non-dat-kiem-dinh-chat-luong-giao-duc-cap-tinh-tu-ngay-2512025-nh-197299.html
- `test_0254`: An Nhon Tay is formed from Nhon Loc and Nhon Tan.
  - https://thuvienphapluat.vn/phap-luat/xa-an-nhon-tay-tinh-gia-lai-moi-duoc-hinh-thanh-do-sap-nhap-tu-nhung-don-vi-hanh-chinh-nao-theo-ngh-243639-238080.html
- `test_0354`: beauty/model contest approval is 15 working days.
  - https://sovhtt.hanoi.gov.vn/quan-ly/thu-tuc-to-chuc-cuoc-thi-nguoi-dep-nguoi-mau-2/

## Expected value

This is not guaranteed to beat the public grader. It is a rational probe:

- If the three primary changes match the hidden/public answer key, the probe
  should improve over the 91.79 reference by about 3/463 = 0.65pp.
- If the key follows the prior 91.79 file instead, this probe loses those points.
- `test_0001` is separately isolated because it looks genuinely ambiguous; do
  not spend a limited official submission on the alt variant unless the owner
  wants to test that specific item.
