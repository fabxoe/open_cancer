# EXP-327: isoform-relative residue-position 5-bin

## 결론

Ensembl release 116에서 sequence-supported simple substitution의 위치를 대표
protein 길이로 나눈 뒤 사전 고정 5개 구간으로 변환했다. EXP-229 대비 OOF
Macro F1은 개선됐지만, 먼저 완료된 EXP-313 semantic mask보다 성능·fold 안정성·
Log Loss가 모두 열세여서 `ARCHIVE`한다. relative-bin 경계나 대표 isoform
우선순위를 추가 튜닝하지 않는다.

## 실험 계약

- Issue/브랜치: #327 / `issue-327-isoform-relative-position-bin`
- 부모: EXP-229
- source commit: `f3b309170206163aa4adc138fec7513e4bfcd2d7`
- canonical stratified 5-fold, seed 42
- XGBoost·pathway families·balanced weight·Macro-F1 checkpoint 정책 고정
- 유일한 변경: raw max residue-position을 Ensembl 116 relative 5-bin으로 교체하고
  unmapped token을 구분하는 observed indicator 추가
- 우선순위: MANE Select → Ensembl canonical → other isoform
- 동순위 tie-break: transcript ID → protein ID 사전순
- SUBCLASS·test 분포·Public LB는 변환 정의에 사용하지 않았다.

입력에는 transcript ID가 없으므로 대표 sequence는 deterministic 계산 규칙일 뿐,
실제 종양에서 발현된 isoform이라고 해석하지 않는다.

## 결과

| 지표 | EXP-229 | EXP-327 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4229885745 | 0.4266361381 | +0.0036475635 |
| fold 표준편차 | 0.0098679649 | 0.0115013235 | +0.0016333586 |
| Log Loss | 1.8509613276 | 1.8585858345 | +0.0076245070 |
| Accuracy | 0.4125141106 | 0.4150943396 | +0.0025802290 |

Fold Macro F1은 `0.4155225548 / 0.4250140277 / 0.4213012888 /
0.4215258721 / 0.4485677567`이다. 클래스별 최악 변화는 UCEC `-0.0254936`,
최대 개선은 DLBC `+0.0592593`이었다. DLBC는 38건의 극소수 클래스이므로 단일
실행 개선을 강한 근거로 해석하지 않는다.

## EXP-313과의 직접 비교

| 지표 | EXP-313 mask | EXP-327 relative bin | EXP-327 - EXP-313 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4267909268 | 0.4266361381 | -0.0001547888 |
| fold 표준편차 | 0.0085032169 | 0.0115013235 | +0.0029981066 |
| Log Loss | 1.8440648317 | 1.8585858345 | +0.0145210028 |

두 실험 모두 외부 sequence 의미를 쓰는 독립 ablation이다. EXP-327은 부모 대비
방향성은 확인했지만 기존 EXP-313을 대체하지 못한다. Track B의 채택 후보는
EXP-313으로 유지한다.

## 재현성

- Config: `configs/exp327_isoform_relative_position_bin.yaml`
- Runner: `scripts/run_exp327_isoform_relative_position_bin.py`
- Metrics: `reports/exp327_isoform_relative_position_bin/metrics.json`
- Reproducibility: `reproducibility/exp327_isoform_relative_position_bin/`
- Submission: `submissions/exp327_isoform_relative_position_bin.csv` (미제출)
- 상태: `INFERENCE_VERIFIED`
- checkpoint 재추론의 test label 일치율 100%, 확률 최대 절대 차이
  `1.4829636e-07`, submission SHA-256 byte-level 일치
