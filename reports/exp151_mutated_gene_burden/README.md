# EXP-151: EXP-094 + log1p(mutated_gene_count)

## 결론

EXP-094 Feature Spec v1에 `log1p(mutated_gene_count)` 하나만 추가해 canonical
5-fold를 실행했습니다. Macro F1과 Log Loss는 개선됐지만 fold 표준편차가 크게
악화되어 사전 채택 기준을 통과하지 못했습니다. 이후 사전 생성된 제출 파일을
2026-08-02 리더보드에 제출했고 Public Macro F1은 `0.3125095748`이었습니다.
Feature Spec에는 채택하지 않습니다.

## 결과

| 항목 | EXP-151 | EXP-094 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4188970451 | 0.4168865739 | +0.0020104712 |
| fold 표준편차 | 0.0130000285 | 0.0078842521 | +0.0051157765 |
| Log Loss | 1.8381872786 | 1.8399373293 | -0.0017500507 |

fold Macro F1은 `0.4162682, 0.4292479, 0.4017717, 0.4084666, 0.4370477`입니다.
점수 상승보다 fold 간 변동성 증가가 커서 채택하지 않습니다.

## 리더보드 제출 결과

- 제출 ID / 시각: `1508912` / 2026-08-02 23:52:30 KST
- 제출 파일: `submissions/exp151_mutated_gene_burden.csv`
- SHA-256: `dddaf57cf2c497b08264a2c883223afff0d347edcadb9585783f06e1294e4349`
- Public Macro F1: `0.3125095748`
- EXP-094 대비: `+0.0006564118`
- 순위 해석: 팀 최고 EXP-031에 미달해 팀 점수·순위는 갱신되지 않았습니다.
- 재현성 메모: 현재 `NOT_STARTED`이므로 정식 History 제출 행과 Release 연결은
  checkpoint inference 검증 후 진행합니다.

## 실행 조건

- Issue: #151
- 부모: EXP-094 frozen Feature Spec v1
- 추가 피처: `log1p(mutated_gene_count)` 1개
- split: `data/splits/stratified_5fold_seed42.csv`
- 클래스 순서: 고정 26개
- 모델: XGBoost, `device: cuda`, Secure Cloud RTX 4090
- test 라벨 미사용
- 실행 산출물: `oof/exp151_mutated_gene_burden.csv`,
  `preds/exp151_mutated_gene_burden_test_proba.csv`,
  `submissions/exp151_mutated_gene_burden.csv`

## 실행 소스 정합성

- 정식 runner: `scripts/run_exp151_burden_incremental.py`
- config: `configs/exp151_burden_incremental.yaml`
- 과거 config가 EXP-154용으로 rename되고 runner 경로가 재사용된 이력이 있어,
  Git 이력 `17d433f`에서 EXP-151 source를 복원했다. 결과·점수는 변경하지 않았다.
- 재현 상태는 source 복구만으로 승격하지 않으며 현재 `NOT_STARTED`를 유지한다.

## 판단

사전 기준 중 Macro F1·Log Loss는 통과했지만 fold 표준편차 기준을 실패했습니다.
따라서 burden 피처는 보조 신호 가능성만 기록하고, Feature Spec v2나 제출 모델에는
반영하지 않습니다. 다음 total_variant_count 및 missense_count 실험은 별도 Issue로
분리해 동일 기준으로 평가합니다.
