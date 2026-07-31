# Residue-position과 co-mutation 피처 이해하기

이 문서는 변이 문자열에서 만드는 `residue-position` 피처와 문헌에 근거해
미리 정한 `co-mutation` 유전자 쌍 피처를 처음 접하는 팀원을 위한 안내서다.
두 피처는 모두 원본 유전체 변이 정보에서 계산하지만, 바라보는 정보와 계산
방법이 다르다.

## 먼저 한 문장으로 구분하기

- **Residue-position**: 한 유전자 안에서 변이가 단백질의 몇 번째 위치에
  적혀 있는지 사용한다.
- **Co-mutation pair**: 미리 정한 두 유전자가 한 환자에게 모두 변이됐는지
  사용한다.

## 1. Residue-position은 무엇인가

환자의 한 유전자 셀에 다음과 같은 변이 문자열이 있다고 가정한다.

```text
R132H 312_313QY>HH
```

파서는 문자열에 명시된 단백질 잔기 위치 `132`, `312`, `313`을 읽는다.
그 위치들로 다음 값을 만들 수 있다.

| 피처 | 계산 | 값 |
|---|---|---:|
| `min` | 가장 작은 위치 | 132 |
| `max` | 가장 큰 위치 | 313 |
| `span` | `max - min` | 181 |

이 위치는 입력 문자열에 적힌 단백질 잔기 번호다. genomic coordinate, DNA
염기 위치 또는 특정 transcript에 맞춰 정규화한 좌표로 추정하지 않는다.

## 2. 문헌 기반 고정 co-mutation pair는 무엇인가

EXP-052는 다음 유전자 쌍을 사용했다.

- `IDH1–IDH2`
- `APC–CTNNB1`
- `PIK3CA–PTEN`

한 환자에게 쌍을 구성하는 두 유전자가 모두 변이돼 있으면 `1`, 아니면 `0`을
기록한다.

| 환자 | IDH1 | IDH2 | `sample__comut_IDH1_IDH2` |
|---|---|---|---:|
| A | 변이 | 변이 | 1 |
| B | 변이 | WT | 0 |
| C | WT | WT | 0 |

여기서 **문헌 기반 고정**은 train 데이터에서 점수가 잘 나오는 쌍을 검색해
선택했다는 뜻이 아니다. 암 연구에서 관계가 알려진 유전자 쌍을 모델 실행 전에
고정했다는 뜻이다. 따라서 이 세 쌍 자체를 현재 데이터로 학습하거나 fold마다
다시 선택하지 않는다.

### 고정 pair와 데이터에서 찾은 pair의 차이

| 구분 | 문헌 기반 고정 pair | 데이터 기반 pair mining |
|---|---|---|
| 선택 근거 | 실행 전에 정한 외부 지식 | train의 동시발생 빈도·타깃·점수 |
| fold별 선택 | 필요 없음 | fold-train 안에서만 수행 |
| validation 정보 사용 | 없음 | 전체 train에서 고르면 누수 위험 |
| 현재 구현 예 | EXP-052의 고정 3쌍 | 아직 공통 Factory에 구현하지 않음 |

향후 데이터에서 co-mutation 후보를 발굴한다면 각 validation fold를 제외한
fold-train에서만 pair를 선정하고 validation에는 변환만 적용해야 한다.

## 3. 두 피처는 어떻게 다른가

| 구분 | Residue-position | 문헌 기반 co-mutation pair |
|---|---|---|
| 보는 단위 | 한 유전자 내부 위치 | 두 유전자의 관계 |
| 예시 | BRAF의 600번 위치 | PIK3CA와 PTEN이 모두 변이 |
| 주요 값 | min, max, span | pair별 0 또는 1, 활성 pair 총개수 |
| 입력 근거 | 제공된 변이 문자열의 숫자 | 고정 유전자 쌍과 각 유전자의 변이 여부 |

둘은 서로 대체하는 피처가 아니다. 하나는 유전자 내부의 위치 정보를 추가하고,
다른 하나는 유전자 사이의 관계 정보를 추가한다.

## 4. Residue-position 비교 옵션의 화살표

아래 화살표 `→`는 왼쪽 설정을 없애고 오른쪽으로 영구 변경한다는 뜻이 아니다.
**기존 기준 설정과 변경 설정을 비교한다**는 뜻이다.

### `zero → indicator`

`zero`는 위치를 읽을 수 없는 유전자의 위치값을 희소행렬의 `0`으로 남긴다.
`indicator`는 같은 0 처리에 위치 관측 여부 피처를 추가한다.

| 상황 | 위치값 | `residue_position_observed` |
|---|---:|---:|
| 위치 132를 읽음 | 132 | 1 |
| WT·빈값·위치 없는 토큰 | 0 | 0 |

비교 질문은 다음과 같다.

> 모델에 “0은 실제 위치가 아니라 위치 정보를 읽지 못했다는 뜻”을 별도로
> 알려주면 성능이 좋아지는가?

### `complex include → exclude`

`312_313QY>HH`처럼 `_`, `>` 등이 포함된 복잡한 토큰에서 읽은 위치를
aggregate에 사용할지 비교한다.

| 설정 | `R132H 312_313QY>HH`의 위치 후보 | min | max |
|---|---|---:|---:|
| `include` | 132, 312, 313 | 132 | 313 |
| `exclude` | 132 | 132 | 132 |

비교 질문은 다음과 같다.

> complex 토큰에서 읽은 위치가 유용한가, 아니면 불안정한 잡음인가?

`exclude`는 complex 토큰만 제외한다. frameshift는 별도 mutation type이므로
현재 정의에서는 자동으로 제외되지 않는다.

### `raw → coarse_bin`

`raw`는 위치 숫자를 그대로 사용한다. `coarse_bin`은 위치를 고정 폭 구간
번호로 바꾼다. `bin_width=100`이라면 다음과 같다.

| 원래 위치 | coarse bin |
|---:|---:|
| 1–100 | 1 |
| 101–200 | 2 |
| 201–300 | 3 |
| 301–400 | 4 |

위치 132는 `raw`에서 `132`, `coarse_bin`에서 `2`다. 비교 질문은 다음과 같다.

> 정확한 위치값이 중요한가, 아니면 넓은 위치 구간이 과적합을 줄여 더
> 안정적인가?

## 5. 왜 한 번에 하나만 바꾸는가

EXP-047의 기준 설정은 다음과 같다.

```text
min + zero + complex include + raw
```

각 옵션의 효과를 확인할 때는 나머지 설정을 고정하고 하나만 바꾼다.

```text
비교 1: min + indicator + include + raw
비교 2: min + zero      + exclude + raw
비교 3: min + zero      + include + coarse_bin
```

여러 옵션을 동시에 바꾸면 점수가 달라져도 어느 변경이 원인인지 알 수 없다.
단독 비교로 유망한 옵션을 확인한 뒤, 채택 후보끼리의 조합은 별도 Experiment
Issue에서 검증한다.

공식 실험은 설정이 달라 예측이 바뀔 때마다 별도 Experiment Issue를 사용한다.
간단한 screening은 `RUN_MODE="explore"`로 실행할 수 있지만 그 점수를 공식
History 결과로 기록하지 않는다.

## 관련 문서와 실험

- [Feature Factory 운영 안내](FEATURE_FACTORY.md)
- [프로젝트 운영 규칙](../PROJECT_CONTEXT.md)
- [EXP-047 residue-position 보고서](../reports/exp047_xgb_min_residue_position/README.md)
- [EXP-052 co-mutation 보고서](../reports/exp052_hotspot_cooccurrence/README.md)
