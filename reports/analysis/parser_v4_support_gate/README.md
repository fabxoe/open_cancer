# Parser v4 family train-support·Experiment eligibility gate

> Task Issue: [#407](https://github.com/fabxoe/open_cancer/issues/407)
>
> Parent roadmap: [#360](https://github.com/fabxoe/open_cancer/issues/360)

이 감사의 `EXPERIMENT_ELIGIBLE`은 성능 채택이 아니라 **canonical 5-fold를
실행할 최소 train 지원이 있다**는 뜻뿐이다. 기준은 train sample 50개 이상,
각 canonical fold sample 5개 이상이다. unresolved route는 건수와 무관하게 QC
전용이다. SUBCLASS·Public LB·test prevalence는 판정에 사용하지 않는다.

## 결과

| route:event | train samples | fold samples | test samples | 판정 |
|---|---:|---|---:|---|
| substitution:missense | 6,017 | 1210/1208/1200/1201/1198 | 2,485 | EXPERIMENT_ELIGIBLE |
| substitution:no_change | 5,251 | 1049/1044/1034/1057/1067 | 2,304 | EXPERIMENT_ELIGIBLE |
| substitution:nonsense | 3,266 | 684/662/632/634/654 | 1,559 | EXPERIMENT_ELIGIBLE |
| frameshift:frameshift | 3,274 | 644/651/666/647/666 | 1,642 | EXPERIMENT_ELIGIBLE |
| range_replacement:range_replacement | 129 | 18/29/29/25/28 | 24 | EXPERIMENT_ELIGIBLE |
| range_replacement:synonymous | 47 | 5/9/15/6/12 | 9 | ANALYSIS_ONLY |
| range_replacement:stop_gain | 23 | 3/6/7/3/4 | 2 | ANALYSIS_ONLY |
| deletion | 3 | 1/0/0/1/1 | 520 | ANALYSIS_ONLY |
| insertion | 0 | 0/0/0/0/0 | 345 | ANALYSIS_ONLY |
| delins 전체 | 0 | 0/0/0/0/0 | 226 | ANALYSIS_ONLY |
| start_codon_affected | 0 | 0/0/0/0/0 | 371 | ANALYSIS_ONLY |
| unknown-reference substitution | 0 | 0/0/0/0/0 | 138 | ANALYSIS_ONLY |
| unresolved route | 152 | 31/33/25/36/27 | 32 | UNRESOLVED_ONLY |

test 수치는 분포 설명일 뿐 판정에 사용하지 않았다. deletion·insertion·delins·
start-codon은 OOF에서 의미 피처 효과를 검증할 train 모집단이 없거나 지나치게
작다.

## 후속 결정

- missense·no-change·nonsense·frameshift는 충분한 train support가 있지만 기존
  Feature Spec이 이미 gene×mutation-type 신호를 사용한다. 이번 결과만으로 반복
  실험하지 않는다.
- **새 의미 adapter 후보는 ordinary `range_replacement` 하나다.** 기존 generic
  complex 표현은 유지하고, fold-safe gene-level `range_replacement_any`를 추가하는
  단일 변경 Experiment로 검증한다.
- synonymous/stop-containing range는 ordinary family에 합치지 않고 각각 QC로
  유지한다.
- train-zero/test-only family는 parser completeness 자산으로만 보존한다.

```bash
uv run python scripts/audit_parser_v4_support.py
uv run pytest -q tests/test_parser_support_gate.py
```
