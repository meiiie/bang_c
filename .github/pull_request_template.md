## Summary

- 

## Verification

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python -m compileall -q src`
- [ ] `.\scripts\verify.ps1 -InputPath <public_test.csv> -Docker`
- [ ] Manual/real-model run, if model behavior changed

## Contest Contract

- [ ] Reads `/data/public_test.csv` or `/data/private_test.csv`
- [ ] Writes `/output/pred.csv`
- [ ] Output columns remain exactly `qid,answer`
- [ ] Runtime model remains within Bang C rules: Gemma-4 or Qwen3.5 <= 9B
- [ ] Development-only tools do not affect final Docker scoring path

## Risk And Rollback

- Risk:
- Rollback:

