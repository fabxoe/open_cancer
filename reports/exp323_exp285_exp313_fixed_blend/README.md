# EXP-323 EXP-285·EXP-313 고정 확률 평균

## 결론

EXP-285와 EXP-313은 OOF 예측 불일치율 `16.76%`, 오류 상관 `0.8430`으로
서로 보완할 가능성이 있었지만, 사전 고정 `0.5/0.5` 확률 평균의 OOF Macro F1은
`0.4260586706`이었다. EXP-285보다 `-0.0054122838`, EXP-313보다
`-0.0007322562` 낮고 fold 표준편차도 악화됐다.

Log Loss는 `1.8292042544`로 두 부모보다 개선됐지만 공식 지표는 Macro F1이다.
따라서 EXP-323은 **ARCHIVE**하고 Public 제출과 추가 가중치·클래스별 가중치·
threshold 탐색을 수행하지 않는다.

## 사전 다양성 감사

- OOF 행 수: 6,201
- ID·정답·canonical fold·26개 클래스 순서: 모두 일치
- 예측 라벨 불일치율: `0.1675536204`
- 오류 indicator 상관: `0.8430142358`
- EXP-285만 정답: 266행
- EXP-313만 정답: 208행
- 두 모델 모두 오답: 3,375행
- 전체 확률 flatten Pearson 상관: `0.9733486001`

프로젝트의 다양성 조건인 오류 상관 `<0.92` 또는 예측 불일치율 `≥10%`를
충족했기 때문에 고정 blend를 공식 실험으로 실행했다. 이 감사에서 test 정답이나
Public LB는 사용하지 않았다.

## 고정 계약

- Issue: [#323](https://github.com/fabxoe/open_cancer/issues/323)
- 부모: EXP-285, EXP-313
- 가중치: EXP-285 `0.5`, EXP-313 `0.5`
- 각 클래스 확률을 평균한 뒤 argmax
- 가중치는 공식 결과 계산 전에 Issue에 고정
- 다른 가중치·클래스별 가중치·threshold를 탐색하지 않음
- 모델 재학습 없음

## 결과

| 지표 | EXP-323 | EXP-285 | EXP-313 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4260586706 | 0.4314709544 | 0.4267909268 |
| Fold 평균 | 0.4256463387 | 0.4318801637 | 0.4266436967 |
| Fold 표준편차 | 0.0120673474 | 0.0117209428 | 0.0085032169 |
| Accuracy | 0.4146105467 | 0.4221899694 | 0.4128366393 |
| Log Loss | 1.8292042544 | 1.8409389257 | 1.8440648317 |

Fold Macro F1은 `0.4265050 / 0.4198155 / 0.4157123 / 0.4175499 /
0.4486491`이다. EXP-285 대비 KIRC `-0.05654`, LGG `-0.03907`, OV
`-0.03418`이 크게 하락했고, ACC `+0.04196`, CESC `+0.02446`, STES
`+0.02100`은 개선됐다. 서로 다른 오류가 존재해도 단순 평균이 Macro F1을
자동으로 높이지는 않는다는 통제 결과다.

## 재현성과 산출물

- Config: `configs/exp323_exp285_exp313_fixed_blend.yaml`
- Runner: `scripts/run_exp323_exp285_exp313_fixed_blend.py`
- Metrics: `reports/exp323_exp285_exp313_fixed_blend/metrics.json`
- OOF: `oof/exp323_exp285_exp313_fixed_blend.csv`
- test 확률: `preds/exp323_exp285_exp313_fixed_blend_test_proba.csv`
- submission: `submissions/exp323_exp285_exp313_fixed_blend.csv`
- reproducibility: `reproducibility/exp323_exp285_exp313_fixed_blend/`
- source commit: `4f0776175fd935acc4edb435f9e21e426909b23e`
- 재현 상태: `INFERENCE_VERIFIED`
- submission SHA-256:
  `8b34cc167c5b114fad0ea4a592104492478ee7e6d75caf64790470efd3f224db`

부모 확률을 다시 읽어 생성한 OOF·test 라벨과 확률은 100% 일치했고 최대 확률
차이는 0, 제출 CSV SHA-256도 byte-level로 일치했다.

## 다음 판단

EXP-285는 단독 제출 후보로 유지한다. EXP-313과의 단순 평균은 종료하며, 같은
canonical OOF 결과를 본 뒤 가중치를 세밀하게 맞추는 작업은 간접 과적합 위험이
있어 진행하지 않는다. 다음 우선순위는 EXP-285의 Public 확인 또는 다른 팀원의
독립 재학습 검증이다.
