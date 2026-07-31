# EXP-012 COSMIC 보호 유전자 기반 feature 보호 전략 분석

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-012 / #12 |
| 유형 | 모델 학습 없는 feature 정책 분석 |
| 데이터 | train의 4,384개 유전자 컬럼과 COSMIC CGC v104 |
| 결과 | protect 361개, drop 151개, keep 3,872개 |
| Local OOF / Public LB | 해당 없음 / 미제출 |
| 재현 상태 | `NOT_STARTED` — 모델 checkpoint가 없는 분석 전용 기록 |

## 목적

희소하다는 이유만으로 임상적으로 중요한 암 유전자를 제거하지 않도록 COSMIC
Cancer Gene Census 정보를 feature 선택의 보호 규칙으로 사용했다. 이 분석은
모델 점수를 만들기 위한 실험이 아니라 후속 모델에서 사용할 `protect`, `drop`,
`keep` 정책을 결정하기 위한 작업이다.

## 방법과 결과

- train의 4,384개 유전자와 COSMIC CGC v104를 대조했다.
- COSMIC 화이트리스트와 겹치는 유전자는 361개였다.
- 화이트리스트 유전자 중 train 변이율이 0%인 3개도 임상적 중요도를 우선해
  `protect`로 유지했다.
- 최종 분류는 protect 361개, drop 151개, keep 3,872개다.
- 알려진 driver 중 KRAS, NRAS, BAP1, PBRM1, SETD2는 이 패널 컬럼에 없었다.

## 라이선스와 공유 범위

COSMIC CGC v104는 등록이 필요한 학술 라이선스 데이터다. 원본 화이트리스트와
유전자 심볼을 그대로 포함한 파생 CSV는 GitHub에 올리지 않는다. 이 보고서는
재배포가 가능한 집계 수치와 의사결정만 기록한다.

로컬 산출물 복구와 팀원 전달 절차는
[`docs/EXP-012_handoff.md`](../../docs/EXP-012_handoff.md)를 따른다.

## 결론

유전자 변이율만 보고 feature를 제거하지 않고, COSMIC 보호 목록을 먼저
적용하는 정책을 채택했다. 이 결과는 EXP-021의 피처 선택과 burden 파생변수
실험에 사용됐다.

