# EXP-374 EXP-369 stop 정규화 + Ensembl isoform mask 단일 조합

## 결론

EXP-369(stop 표기 `*`/`X`/`Ter` 정규화)를 부모로 고정하고, EXP-313/EXP-334와
동일한 Ensembl release 116 semantic residue-position mask 하나만 추가했다.
OOF Macro F1은 `0.4267909268`로 EXP-369 대비 `+0.0038023523` 개선됐고,
fold 표준편차(`0.0085032169`, `-0.0013647481`)와 Log Loss(`1.8440648317`,
`-0.0068964959`)도 함께 좋아졌다. 세 지표 모두 EXP-313이 EXP-229 위에서
얻은 개선폭과 소수점까지 동일하다 — train에는 X-표기 stop-gain이 0건이라
stop 정규화가 train 쪽에는 아무 영향을 주지 않기 때문에 당연한 결과다.

**parent 대비 채택 게이트(Macro F1 +0.001 이상, fold std 악화 `<0.002`,
클래스 붕괴 `-0.05` 없음)를 모두 통과한다.** 다만 이 실험이 만들어진 진짜
목적은 Local 개선 자체가 아니라, EXP-334가 Public에서 부모 EXP-285보다
낮았던 이유가 "mask 아이디어 자체의 결함"이 아니라 "그때는 아직 남아있던
stop 표기 버그" 때문이었는지 확인하는 것이다. 그 답은 Local이 아니라
Public 제출로만 확인할 수 있다.

## 실험 설계 — 단일 변수만 변경

- Issue: [#374](https://github.com/fabxoe/open_cancer/issues/374)
- **부모: EXP-369**(EXP-334가 아님). EXP-285의 nested-Optuna 튜닝 파라미터는
  의도적으로 가져오지 않았다 — EXP-285는 Local만 올리고 Public은 EXP-229와
  사실상 동일했고(`0.3201744850` vs `0.3203598833`), EXP-334는 그 튜닝과
  mask를 동시에 바꿔서 원인을 분리할 수 없었다. 이번 실험은 모델
  하이퍼파라미터를 EXP-229/EXP-369 기본값 그대로 두고 mask 하나만 추가해
  그 결함을 반복하지 않는다.
- 유지: EXP-369의 stop 표기 정규화(base/hotspot/pathway LoF/pathway
  mutation-type 전 경로), EXP-229의 canonical 5-fold seed 42, Macro-F1
  checkpoint 정책, pathway·hotspot 피처
- 유일한 변경: residue-position 집계에 EXP-313/EXP-334와 동일한 Ensembl
  116 semantic mask 적용(trusted: CANONICAL_MATCH/MANE_MATCH/
  OTHER_ISOFORM_MATCH, masked: COMPLEX_OR_UNMAPPABLE/
  OUTSIDE_ALL_KNOWN_ISOFORMS/POSITION_VALID_REF_MISMATCH)
- SUBCLASS·test 분포·Public LB는 mask나 파라미터 선택에 사용하지 않았다

## 결과

| 지표 | EXP-374 | EXP-369(부모) | 변화 | 참고: EXP-313 vs EXP-229 |
|---|---:|---:|---:|---:|
| OOF Macro F1 | 0.4267909268 | 0.4229885745 | +0.0038023523 | +0.0038023523 |
| Fold 평균 | 0.4266436967 | 0.4232332489 | +0.0034104478 | (동일 패턴) |
| Fold 표준편차 | 0.0085032169 | 0.0098679649 | -0.0013647481 | -0.0013647481 |
| Accuracy | 0.4128366393 | 0.4125141106 | +0.0003225286 | (동일 패턴) |
| Log Loss | 1.8440648317 | 1.8509613276 | -0.0068964959 | -0.0068964959 |

Fold Macro F1: 0.4243902236 / 0.4214466890 / 0.4201172029 / 0.4239068711 /
0.4433574970. 클래스별 F1은 EXP-313과 완전히 동일하다(train 쪽 영향이
없다는 점을 다시 확인).

## Test 영향 감사

EXP-374와 EXP-229(로컬에 test 확률이 있는 가장 이른 조상)의 test 확률을
ID·26개 클래스 고정 순서로 비교했다. **EXP-369 자체와의 직접 비교는
EXP-369의 test 확률 파일이 이 머신에 없어 수행하지 못했다** — stop
정규화와 mask 두 변경의 누적 효과만 아래에 있다.

- 확률이 `1e-6`보다 크게 바뀐 행: 2,546 / 2,546 (100%)
- 최종 예측 라벨이 바뀐 행: 533 / 2,546 (**20.93%**)
- 전체 확률 원소 평균 절대 차이: `0.0100970962`
- 최대 절대 확률 차이: `0.8080704160`

EXP-369 단독 감사(EXP-229 대비 라벨 변경 13.63%)보다 라벨 변경 비율이 더
크다 — stop 정규화와 mask가 서로 다른 test 행에 영향을 주며 누적된다는
뜻으로 해석한다. 어느 방향이 맞는지는 Public 없이는 알 수 없다.

## 재현성

- 소스 commit: `fb44df80c4ff054767c5366fcd85d89bfb3f8a3f`
- Config: `configs/exp374_stop_notation_isoform_mask.yaml`
- Runner: `scripts/run_exp374_stop_notation_isoform_mask.py`
- Metrics: `reports/exp374_stop_notation_isoform_mask/metrics.json`
- OOF: `oof/exp374_stop_notation_isoform_mask.csv`
- test 확률: `preds/exp374_stop_notation_isoform_mask_test_proba.csv`
- submission: `submissions/exp374_stop_notation_isoform_mask.csv`
- submission SHA-256: `6ebae265d36ce5b87748cdb40c412fc9563e64a69c0194d92b43cc1af4e6d006`
- 재현 상태: `INFERENCE_VERIFIED` — checkpoint 재추론에서 submission
  SHA-256 byte-level 일치, test 라벨 100%, 확률 최대 차이 `1.83e-7`
  (`reproducibility/exp374_stop_notation_isoform_mask/comparison.json`)
- 실행시간: 565.58초

## 판단과 다음 행동

Local 게이트는 통과했지만, 이 실험의 핵심 질문(EXP-334 Public 부진이
mask 결함이 아니라 stop 표기 버그 때문이었는가)은 Local로 답할 수 없다.
Public 제출로 확인이 필요하며, 제출 횟수 제한이 있으므로 팀 합의 후
진행한다. 제출 전 참고: parent EXP-369 단독으로 이미 Public 0.3407944343로
팀 최고를 기록했으므로, 이 실험은 "그 위에 mask를 더하면 더 좋아지는가,
아니면 EXP-334처럼 오히려 나빠지는가"를 가리는 실험이다.
