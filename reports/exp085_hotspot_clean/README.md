# EXP-085: Clean fixed-hotspot reconstruction

## 한눈에 보기

EXP-085는 EXP-005의 유전자×변이유형 희소 피처에 문헌으로 고정한 cancer
hotspot 34개와 샘플별 hotspot 총개수를 추가해 canonical 5-fold에서 다시 실행한
로드맵 단계 D 실험입니다. 기존 EXP-031의 점수를 수정하거나 복구한 것이 아니라,
새 Issue·clean commit·공용 runner로 독립 실행했습니다.

| 항목 | EXP-005 | EXP-085 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4043796587 | 0.4125795545 | +0.0081998958 |
| Fold 표준편차 | 0.0086812077 | 0.0091265687 | +0.0004453610 |
| Log Loss | 1.8632071018 | 1.8315716982 | -0.0316354036 |

- Public LB: `0.3103760308` (제출 ID `1507333`, 2026-07-31 23:55:33 KST)
- 순위: 플랫폼 전체 개별 순위 미제공·확인 당시 팀 내부 8개 제출 중 2위
- 재현 상태: `INFERENCE_VERIFIED`
- 판단: **hotspot family 복구 성공·채택**, 현재 팀 선택 제출물은 EXP-031 유지

## 피처와 누출 방지

- hotspot은 `(gene, residue position, reference amino acid)`가 모두 일치할 때만 1입니다.
- 문헌으로 고정한 34개 목록은 validation/test를 보고 변경하지 않았습니다.
- 추가 15개 hotspot은 각 fold의 fold-train에서만 최소 5회 관측되는지 검사했습니다.
- fold별 최소 관측 수는 `5, 5, 6, 6, 6`이었습니다.
- test는 고정된 목록을 변환하는 데만 사용했습니다.

## 실제 결과

- Fold Macro F1: `0.4070290`, `0.4219064`, `0.4059511`, `0.4005702`, `0.4232571`
- OOF Macro F1: `0.4125795545`
- Accuracy: `0.4039671021`
- Log Loss: `1.8315716982`

EXP-005 대비 로드맵 채택 기준 `+0.005`를 넘었고 fold 표준편차 악화도
`+0.0004454`에 그쳤습니다. 기존 EXP-031 OOF `0.4135846695`보다는
`-0.0010051150` 낮지만, EXP-031과 달리 저장 checkpoint 추론을 검증할 수 있는
clean 결과입니다.

Public LB는 `0.3103760308`로 EXP-031의 `0.3170803849`보다
`0.0067043541` 낮았습니다. 따라서 hotspot family의 재현 가능한 후속 기반으로는
채택하되, 현재 팀 대표 제출은 EXP-031을 유지합니다.

## 리더보드 제출 결과와 순위 해석

| 항목 | 값 |
|---|---|
| 제출 ID | `1507333` |
| 제출 시각 | 2026-07-31 23:55:33 KST |
| Public Macro F1 | `0.3103760308` |
| 제출 선택 여부 | 미선택, EXP-031 유지 |
| 팀 순위 영향 | EXP-031 최고 점수 미달로 미갱신 |
| 팀 내부 제출 점수 순위 | 확인 당시 8개 제출 중 2위 |
| 공식 전체 개별 순위 | 플랫폼 미제공 |

확인 당시 팀 내부 상위 세 제출은 다음과 같았습니다.

| 팀 내부 순서 | 실험 | Public Macro F1 |
|---:|---|---:|
| 1 | EXP-031 | 0.3170803849 |
| 2 | EXP-085 | 0.3103760308 |
| 3 | EXP-058 | 0.3044672015 |

2026-08-01 확인 당시 DACON 리더보드에 표시된 8조의 공식 순위는 참가 4팀
중 4위였습니다. 이 순위는 선택된 EXP-031의 `0.3170803849`를 기준으로 한
**팀 순위**입니다. DACON 화면은 선택하지 않은 EXP-085의 공식 전체 개별
순위를 별도로 제공하지 않으므로, EXP-085를 “전체 4위”라고 기록하지 않습니다.

## 재현과 파일

- Config: `configs/exp085_hotspot_clean.yaml`
- Metrics: `reports/exp085_hotspot_clean/metrics.json`
- Resolved config: `reproducibility/exp085_hotspot_clean/config.resolved.yaml`
- 비교 증빙: `reproducibility/exp085_hotspot_clean/comparison.json`
- OOF: `oof/exp085_hotspot_clean.csv` (Git 제외)
- Test 확률: `preds/exp085_hotspot_clean_test_proba.csv` (Git 제외)
- 제출 파일: `submissions/exp085_hotspot_clean.csv` (제출 ID `1507333`)
- 제출 SHA-256: `d319c6967ea98b75c158265fe3b46a5ebb12db207a19cd87964476154eecfe5d`

저장 checkpoint 재추론 결과 제출 라벨은 100% 일치했고, test 확률 최대 절대
오차는 `2.97e-08`이며 제출 CSV의 byte-level SHA-256도 일치했습니다.

## 다음 단계

로드맵 단계 E의 위치 negative control을 진행합니다. Hotspot family는 단계 F의
Feature Spec v1 조합 후보로 유지합니다.
