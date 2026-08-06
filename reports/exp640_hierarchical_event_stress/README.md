# EXP-640 — 계층형 mutation event family와 notation-shift 감사

## 결론

EXP-567의 parser-v4 class-cosine LightGBM을 정확히 재현한 뒤 상위 event
family 요약과 parser QC 요약을 분리해 추가했습니다. 네 arm 중 `parser_qc`가
가장 높은 OOF Macro F1을 기록했지만, 복잡 표기 구간과 Log Loss가 악화되어 새
주력 모델로 채택하지 않습니다.

| arm | 추가 피처 | OOF Macro F1 | EXP-567 대비 | fold std | Log Loss | 판단 |
|---|---:|---:|---:|---:|---:|---|
| Base | 0 | 0.4477416384 | 기준 | 0.0045984625 | 1.8136045028 | EXP-567 완전 재현 |
| Event family | 37 | 0.4469083486 | -0.0008332898 | 0.0046775175 | 1.9053587929 | 기각 |
| Parser QC | 10 | 0.4520752637 | +0.0043336253 | 0.0047918500 | 1.9370387304 | 보류·분해 실험 후보 |
| Combined | 47 | 0.4492108773 | +0.0014692388 | 0.0097035693 | 1.8640317124 | 주력 기각 |

모든 arm은 저장 checkpoint 재추론에서 제출 SHA-256과 확률이 일치해
`INFERENCE_VERIFIED`를 통과했습니다. Public LB에는 제출하지 않았습니다.

## 통제 설계

- 부모: EXP-567
- 모델·하이퍼파라미터·canonical split·seed·클래스 순서 고정
- Base 재현 오차 허용치: `1e-8`
- event/QC 요약만 additive하게 변경
- label·test 분포·Public LB를 피처 정의에 사용하지 않음

Base의 OOF Macro F1은 EXP-567의 `0.4477416384457121`과 정확히 같아 통제
게이트를 통과했습니다.

## 추가 피처

Event family arm은 parser-v4 사건을 missense, no-change, stop-gain,
frameshift, deletion, insertion, duplication, delins/complex replacement,
other non-synonymous, complex/unresolved의 상호 배타 family로 라우팅했습니다.
각 family의 event count·gene count·event ratio와 non-synonymous, indel,
truncating 요약, 관측 family 수를 합쳐 37개를 추가했습니다.

Parser QC arm은 complete·partial·unresolved·other status 비율, parser success
rate, unresolved/complex gene 수, multi-token cell 수·비율 등 10개를
추가했습니다.

## 클래스별 변화

Parser QC는 전체 Macro F1을 올렸지만 개선이 균등하지 않았습니다.

- 큰 개선: LGG `+0.138286`, KIRC `+0.054999`, HNSC `+0.030127`,
  LUSC `+0.027387`
- 큰 하락: DLBC `-0.037341`, BLCA `-0.033422`, BRCA `-0.027719`,
  THYM `-0.026416`

Combined는 BLCA가 `-0.061591` 하락해 사전 클래스 붕괴 기준 `-0.05`를
위반했고, fold std가 Base의 두 배 이상으로 증가했습니다.

## Train-only notation-shift subgroup 감사

각 canonical fold에서 subgroup 경계와 희귀 family를 outer-train에서만 정하고,
그 fold의 validation OOF에 적용했습니다. test와 Public LB는 사용하지 않았습니다.

| subgroup | support | Parser QC Macro F1 변화 | Combined 변화 | Parser QC Log Loss 변화 |
|---|---:|---:|---:|---:|
| unresolved high | 152 | +0.005545 | -0.011822 | +0.186662 |
| complex high | 249 | -0.022119 | -0.025868 | +0.188513 |
| multi-token high | 1,534 | -0.000962 | +0.008189 | +0.150515 |
| nonstandard present | 3,340 | +0.011999 | +0.010360 | +0.143259 |
| burden low | 1,680 | +0.000627 | +0.005462 | +0.091290 |
| burden high | 1,598 | -0.003108 | -0.002083 | +0.170403 |

희귀 event family subgroup은 support가 3개뿐이므로 결론에 사용하지 않았습니다.
Parser QC는 nonstandard/unresolved 구간에서 F1 신호가 있었지만 complex 구간에서는
악화됐고 모든 주요 구간의 Log Loss가 나빠졌습니다. 따라서 “새 표기에 전반적으로
강건하다”는 가설은 지지되지 않습니다.

## 판정과 다음 행동

- Event family 전체 묶음: `REJECT`
- Combined: `ARCHIVE_AS_PRIMARY`
- Parser QC: `KEEP_FOR_NARROW_ABLATION`

Parser QC의 OOF 개선은 무시하지 않되 10개를 한꺼번에 채택하지 않습니다. 다음
실험은 `parser success/status ratio`와 `multi-token/unresolved gene count`를 분리한
작은 ablation이어야 합니다. canonical 성능과 notation-shift 구간을 모두 통과한
경우에만 별도 split 감사를 실행합니다. 이번에는 주력 채택 gate를 통과한 arm이
없어 config의 secondary split audit를 실행하지 않았습니다.

## 재현

```bash
uv run python scripts/run_exp640_hierarchical_event_stress.py
uv run python scripts/audit_exp640_notation_shift.py
```

- Config: `configs/exp640_hierarchical_event_stress.yaml`
- Arm metrics: `reports/exp640_hierarchical_event_stress_<arm>/metrics.json`
- Arm summary: `reports/exp640_hierarchical_event_stress/arm_summary.json`
- Stress audit: `reports/exp640_hierarchical_event_stress/notation_shift_audit.json`
- Reproducibility: `reproducibility/exp640_hierarchical_event_stress_<arm>/`
