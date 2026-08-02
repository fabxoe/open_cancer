# EXP-135: EXP-094 + EXP-125 fixed probability blend

## 목적

G4 감사에서 품질·다양성 gate를 통과한 EXP-125와 기준 EXP-094의 예측 확률을
학습 없이 사전 고정한 `0.5/0.5`로 평균했습니다. OOF 또는 Public LB를 확인한
뒤 가중치를 조정하지 않았습니다.

## 결과

| 항목 | EXP-135 | EXP-094 | EXP-125 | EXP-131 최고 단일 |
|---|---:|---:|---:|---:|
| OOF Macro F1 | 0.4201772665 | 0.4168865739 | 0.4189078364 | 0.4222392962 |
| Fold 표준편차 | 0.0126953092 | 0.0078842521 | 0.0081051732 | 0.0140119367 |
| Log Loss | 1.8083444812 | 1.8399371814 | 1.8227982412 | 1.8665114104 |

EXP-094와 EXP-125의 평균은 Log Loss를 크게 낮췄지만, 현재 최고 단일 모델
EXP-131보다 Macro F1이 `0.0020620298` 낮고 G5의 fold 안정성 기준을 충족하지
못했습니다. 이후 사전 생성된 파일을 2026-08-02 리더보드에 제출했고 Public
Macro F1은 `0.3166527939`였습니다. 재현 가능한 최고 EXP-096보다
`0.0002528810`, 팀 최고 EXP-031보다 `0.0004275910` 낮아 팀 점수·순위는
갱신되지 않았습니다. Public 결과를 이용한 추가 가중치 탐색은 하지 않습니다.

## 리더보드 제출 결과

- 제출 ID / 시각: `1508856` / 2026-08-02 23:07:03 KST
- 제출 파일: `submissions/exp135_fixed_probability_blend.csv`
- SHA-256: `5eef332c50322a8f2be1fb64b15bef49d8f5c91ac6200a7dbc587cebaa75b70a`
- Public Macro F1: `0.3166527939`
- 순위 해석: EXP-031 최고 점수에 미달해 팀 순위는 갱신되지 않았으며,
  확인된 재현 가능한 제출 중 EXP-096 다음 2위입니다.
- 재현 번들: [`exp-135-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-135-repro-v1)
  (`44,786,385` bytes, SHA-256
  `d736b48262f51b0521c4db6fcb55a746e13f62fe60f3f984084d8031dc0cb4f7`)

## 재현성

- Issue: [#135](https://github.com/fabxoe/open_cancer/issues/135)
- Branch: `issue-135-exp-fixed-blend`
- Config: `configs/exp135_fixed_probability_blend.yaml`
- Resolved config: `reproducibility/exp135_fixed_probability_blend/config.resolved.yaml`
- OOF: `oof/exp135_fixed_probability_blend.csv`
- Test probability: `preds/exp135_fixed_probability_blend_test_proba.csv`
- Submission: `submissions/exp135_fixed_probability_blend.csv`
- Reproducibility: `INFERENCE_VERIFIED`

재실행에서 OOF·test 확률, 예측 라벨과 제출 CSV SHA-256이 일치했습니다. 이
실험은 부모 확률을 결합하는 inference-only 실험이므로 새 checkpoint는 만들지
않았습니다.
