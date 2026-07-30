# 실험 보고서 사용법

`EXPERIMENT_HISTORY.md`는 전체 실험의 점수, 상태와 판단을 빠르게 찾는 단일
색인입니다. 피처 개념, 변환 예시, 상세 해석과 긴 분석은 이 폴더의 실험별
보고서에 작성합니다.

## 경로

Experiment Issue #12에서 파생된 `EXP-012` 보고서는 다음 형식을 사용합니다.

```text
reports/exp012_<slug>/
├── README.md
├── metrics.json
└── class_f1.csv
```

GitHub는 폴더의 `README.md`를 자동으로 화면에 표시합니다.

## 작성 순서

1. [`EXPERIMENT_REPORT_TEMPLATE.md`](EXPERIMENT_REPORT_TEMPLATE.md)를
   `reports/expNNN_<slug>/README.md`로 복사합니다.
2. 실제 실행값으로 자리표시자를 교체합니다.
3. 측정하지 않았거나 사용하지 않은 내용은 만들지 말고 `미측정`, `미사용` 또는
   `미제출`로 명확히 표시합니다.
4. `EXPERIMENT_HISTORY.md`의 요약표와 상세 로그에 보고서 상대경로를 연결합니다.
5. PR 본문에도 같은 보고서 링크를 추가합니다.

## 언제 작성하나?

다음 실험은 사람이 이해할 수 있는 README 작성을 권장합니다.

- 팀의 첫 베이스라인
- 새로운 데이터 처리 또는 피처를 처음 도입한 실험
- 리더보드에 제출한 실험
- 현재 최고 모델과 최종 수상 후보
- 팀원이 재사용하거나 설명을 자주 확인할 실험

seed나 단일 하이퍼파라미터만 바꾼 작은 비교 실험은 장문 보고서를 강제하지 않습니다.
그 경우 `EXPERIMENT_HISTORY.md`, resolved config와 metrics만으로 충분합니다.

## 역할 구분

| 파일 | 역할 |
|---|---|
| `EXPERIMENT_HISTORY.md` | 전체 실험 색인, 핵심 점수, 상태와 판단 |
| 실험별 `README.md` | 사람이 읽는 개념 설명, 해석, 한계와 다음 단계 |
| `metrics.json` | 프로그램이 읽는 실제 평가값 |
| `config.resolved.yaml` | 기본값까지 포함한 실제 실행 설정 |

`EXPERIMENT_HISTORY_1.md`, `EXPERIMENT_HISTORY_2.md`처럼 History를 번호로 나누지
않습니다. 실험별 README를 연결하면 History를 짧게 유지하면서도 상세 정보를
잃지 않을 수 있습니다.
