# 암종 분류 실험 기록

> 실제로 실행하거나 제출한 내용만 기록합니다.
> 작성 규칙은 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)를 따릅니다.
> 긴 개념 설명과 분석은 [reports 작성 안내](reports/README.md)에 따라 실험별
> `README.md`에 기록하고 이 파일에는 링크만 둡니다.

## 현재 상태

- 실제 실험 수: 5
- 실험 ID 규칙: GitHub Experiment Issue #N → EXP-NNN
- 다음 실험: Experiment Issue를 먼저 생성하고 발급된 번호를 사용
- 최고 Local OOF Macro F1: 0.4135846695002278 (`EXP-031` attempt 5, hotspot 확장)
- 최고 Public LB Macro F1: 0.2987843366 (`EXP-005`, EXP-031은 미제출)
- 최고 재현 검증 모델: `EXP-005` (`INFERENCE_VERIFIED`)
- 최종 갱신일: 2026-07-31

## 실험 요약

| ID | 상태 | 실행자 | Issue | 모델·메모(선택) | OOF Macro F1 | Public LB | 재현 상태 | 판단 | 상세 기록 |
|---|---|---|---|---|---:|---:|---|---|---|
| EXP-003 | COMPLETED | fabxoe | #3 | XGBoost mutation-presence baseline | 0.334930 | 0.228167518 | INFERENCE_VERIFIED | 비교 기준 | [보고서](reports/exp003_xgb_baseline/README.md) |
| EXP-005 | COMPLETED | 2heej | #5 | XGBoost + 유전자×변이유형 희소 피처 | 0.4043796587000222 | 0.2987843366 | INFERENCE_VERIFIED | 제출 재생성 검증 완료·Release 보관 필요 | [보고서](reports/exp005_xgb_mutation_features/README.md) |
| EXP-012 | COMPLETED | Kangho-Park | #12 | COSMIC 보호 유전자 기반 feature 보호 전략 분석 (모델 학습 없음) | N/A (분석 전용) | 미제출 | NOT_STARTED | 채택 | [상세](#exp-012-cosmic-보호-유전자-기반-feature-보호-전략-분석) |
| EXP-026 | COMPLETED | fabxoe | #26 | XGBoost mutation-presence + mutated-gene count | 0.3817476632 | 0.2575936484 | NOT_STARTED | EXP-003 대비 개선, EXP-005보다 낮음 | [보고서](reports/exp026_mutation_burden/README.md) |
| EXP-031 | COMPLETED | Kangho-Park | #31 | EXP-005 변이유형 피처 + 알려진 cancer hotspot 위치 피처 (attempt 5, hotspot 19→34개 확장이 팀 최고) | 0.4135846695 | 미제출 | NOT_STARTED | attempt 5 채택(팀 최고 Local), 리더보드 제출은 보류 | [상세](#exp-031-exp-005-변이유형-피처--cosmic-보호유전자-교차-피처) |

## 리더보드 제출 이력

| 제출 시각 | 실험 ID | Issue | 제출 파일 | SHA-256 | Public 점수 | 순위 | 재현 상태 |
|---|---|---|---|---|---:|---:|---|
| 2026-07-30T18:20:48+09:00 | EXP-003 | #3 | `submissions/exp003_xgb_baseline.csv` (제출 ID `1506230`) | `6e8b64726c86b5a6d52ee58f7f042b74b302852aa8a59c9bfe13332bfee424a5` | 0.228167518 | 3 (확인 당시) | INFERENCE_VERIFIED |
| 2026-07-30T18:26:30+09:00 | EXP-005 | #5 | `submissions/exp005_xgb_mutation_features.csv` | `7bc3e64e1904d9b4007bc141dde771a39e7527172f3cd24c25c408000103183c` | 0.2987843366 | 제출 시점 1위 → 2026-07-30 23:13 KST 기준 2위 | INFERENCE_VERIFIED |
| 2026-07-30T23:56:29+09:00 | EXP-026 | #26 | `submissions/exp026_mutation_burden.csv` (제출 ID `1506469`) | `53d835335d6d23945c80acef4b70d0112f14abdaf1b5d504a63fd1ea7b16ef00` | 0.2575936484 | 미선택·개별 순위 미확인 | NOT_STARTED |

## 재현성 검증 이력

| 검증 시각 | 실험 ID | 검증자 | 소스 커밋·태그 | 데이터 일치 | 제출 재생성 | 재학습 검증 | 결과 | 증빙 |
|---|---|---|---|---|---|---|---|---|
| 2026-07-30T09:14:20Z | EXP-003 | fabxoe | `7306182669c3676e7b17024d3cf1f821131d909b` / [`exp-003-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-003-repro-v1) | SHA-256 일치 | byte-level SHA-256 일치 | 미수행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp003_xgb_baseline/comparison.json) |
| 2026-07-30T09:38:54.622845+00:00 | EXP-005 | 2heej | `816d0a5e070c29d2f549e4fb25b81ec5c0ad5f7b` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100% | 미실행 | INFERENCE_VERIFIED | `reproducibility/exp005_xgb_mutation_features/artifact_manifest.json` |

## 상세 실험 로그

<!-- 실제 실험 로그는 이 줄 아래에 시간순으로 추가합니다. -->

### [EXP-003] XGBoost mutation-presence baseline

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #3 / 3
- 소스 commit: `e58c5f0a02dff92030d4a2363fdf7622eccb5686`
- 시작/종료: 2026-07-30T08:15:12Z / 2026-07-30T08:18:02Z

#### 실행

- Config: `reproducibility/exp003_xgb_baseline/config.resolved.yaml`
- Metrics: `reports/exp003_xgb_baseline/metrics.json`
- Report: `reports/exp003_xgb_baseline/README.md`

#### 결과

- Fold Macro F1: 0.330432, 0.342344, 0.342316, 0.324125, 0.325573
- OOF Macro F1: 0.334930
- Public LB: 0.228167518, 제출 ID `1506230`, 제출 직후 3위
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction: `reports/exp003_xgb_baseline/`,
  `reproducibility/exp003_xgb_baseline/`
- Checkpoint Release:
  [`exp-003-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-003-repro-v1)
- 체크포인트 추론 검증: 원본·재생성 제출 SHA-256
  `6e8b64726c86b5a6d52ee58f7f042b74b302852aa8a59c9bfe13332bfee424a5`,
  test 라벨 일치율 100%, 확률 최대 절대 차이 0
- 결론: 순수 mutation-presence XGBoost의 이후 비교 기준으로 채택

### [EXP-005] XGBoost + 유전자×변이유형 희소 피처

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #5 / issue-5-hgvs-protein-normalization
- 소스 commit: 816d0a5e070c29d2f549e4fb25b81ec5c0ad5f7b
- 시작/종료: 2026-07-30T09:13:28.135923+00:00 / 2026-07-30T09:18:18.616817+00:00

#### 실행
- Config: `reproducibility/exp005_xgb_mutation_features/config.resolved.yaml`
- Metrics: `reports/exp005_xgb_mutation_features/metrics.json`
- Report: `reports/exp005_xgb_mutation_features/README.md`

#### 결과
- Fold Macro F1: [0.3957389475242374, 0.41264527023707276, 0.4011635978874454, 0.39173710435471243, 0.4130462426049025]
- OOF Macro F1: 0.4043796587000222
- Public LB: 0.2987843366 (제출 ID 1506233, 제출 시점 1위,
  2026-07-30 23:13 KST 기준 2위)
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론
- Metrics/Report/Reproduction: `reports/exp005_xgb_mutation_features/metrics.json` / `reports/exp005_xgb_mutation_features/README.md` / `reproducibility/exp005_xgb_mutation_features/artifact_manifest.json`
- 결론: Public 0.2987843366으로 제출 시점 1위였으며 2026-07-30 23:13 KST
  기준 2위. 저장 checkpoint 추론으로 제출 SHA-256과 라벨 100% 일치를
  확인해 `INFERENCE_VERIFIED`로 승격함. 비작성자 재학습과 GitHub Release
  보관은 아직 완료하지 않음.
### [EXP-012] COSMIC 보호 유전자 기반 Feature 보호 전략 분석

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #12 / issue-12-cosmic-protected-genes
- 소스 commit: c5460fab46b78f82e40ace9c48acbcd61a19766a
- 시작/종료: 2026-07-30 / 2026-07-30

#### 실행
- Config: N/A (스크립트 상단에 경로·임계값을 직접 명시, 별도 YAML 없음)
- Metrics: `reports/exp012_feature_analysis/*.csv` (로컬 전용, 아래 라이선스 메모 참고)
- Report: N/A

#### 결과
- Fold Macro F1: N/A (모델 학습을 수행하지 않는 feature 분석 실험)
- OOF Macro F1: N/A (사유 상동)
- Public LB: 미제출
- 재현 상태: NOT_STARTED (모델 산출물이 없어 재현성 계약 대상 아님)

실제 실행 수치 (`uv run python scripts/exp012_feature_analysis.py`, train.csv 4,384개 유전자 기준):

- COSMIC CGC v104 화이트리스트 교집합: 361개 / 4,384개 (train 컬럼 전부 매칭)
- 화이트리스트 vs 비화이트리스트 변이율<1% 비율: 54.57% vs 77.85%
- tier1 297개(평균 변이율 1.39%) / tier2 64개(평균 변이율 1.25%)
- 화이트리스트인데 train 변이율 0%: 3개 (NSD2, KNL1, TENT5C) → 팀 판단으로 `protect` 확정
- 비화이트리스트 고변이율(>3%) 유전자: 79개 (long gene bias 의심, 검증 보류)
- 패널에 없는 known driver 유전자: KRAS, NRAS, BAP1, PBRM1, SETD2
- test 결측 25개 컬럼 중 화이트리스트 포함: 1개 (PTCH1)
- 최종 보호 규칙: `protect` 361개 / `drop` 151개 / `keep`(중립) 3,872개

#### 산출물과 결론
- Metrics: `reports/exp012_feature_analysis/protected_dropped_draft.csv`,
  `protected_genes_final.csv`, `dropped_genes_final.csv` 등 (COSMIC CGC v104
  유전자 심볼을 그대로 포함하므로 라이선스 확인 전까지 `.gitignore` 처리,
  로컬에만 보관)
- 결론: 채택. `protect_review` 3건은 train 관측 0건이지만 COSMIC 임상적 중요도를
  우선해 `protect`로 확정. 최종 보호/제거 유전자 목록은 후속 baseline 모델
  Issue의 feature 선택 입력으로 사용.

#### 선택 메모
- COSMIC CGC v104 화이트리스트(`data/external/gene_whitelist_cosmic_v104.csv`,
  라이선스: COSMIC 학술 라이선스, 등록 필요·재배포 금지)는 원본과 파생 산출물
  모두 Public 레포에 커밋하지 않음. `protected_genes_final.csv` /
  `dropped_genes_final.csv` 자체의 COSMIC 재배포 해당 여부는 아직 팀/COSMIC
  약관 확인 전이라 로컬 보관으로 보류.
- 다음 행동: 이 산출물을 입력으로 하는 "COSMIC 보호 유전자 기반 피처 선택
  XGBoost baseline" 작업을 새 GitHub Issue로 분리해 진행.

### [EXP-026] XGBoost mutation-presence + mutated-gene count

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #26 / issue-26-exp-mutation-burden
- 학습 소스 commit: `cb9c19679811104ba83eb2e7ce766166c484589e`
- 시작/종료: 2026-07-30T14:48:49Z / 2026-07-30T14:51:45Z

#### 실행

- Config: `reproducibility/exp026_mutation_burden/config.resolved.yaml`
- Metrics: `reports/exp026_mutation_burden/metrics.json`
- Report: `reports/exp026_mutation_burden/README.md`

#### 결과

- Fold Macro F1: 0.3755728860, 0.3901946095, 0.3852622979,
  0.3863606499, 0.3624281412
- OOF Macro F1: 0.3817476632
- Public LB: 0.2575936484 (제출 ID `1506469`)
- 재현 상태: NOT_STARTED

#### 산출물과 결론

- 입력은 EXP-003의 4,384개 유전자별 mutation-presence 피처와 동일하며,
  환자별 변이 유전자 개수인 `mutated-gene count` 한 개를 추가함.
- `mutated-gene count`는 패널 내 유전자 변이 존재 개수이며 임상적 TMB가 아님.
- EXP-003 대비 OOF `+0.046817` 및 Public LB `+0.0294261304`로 개선됨.
- EXP-005보다 OOF와 Public LB가 모두 낮아 최종 제출 후보로 선택하지 않음.
- 제출 파일 형식과 SHA-256은 확인했지만 저장 체크포인트로 제출 파일을
  독립 재생성하는 검증은 아직 수행하지 않았으므로 `NOT_STARTED`로 기록함.

### [EXP-031] EXP-005 변이유형 피처 + COSMIC 보호유전자 교차 피처

- 상태: COMPLETED
- 실행자: Kangho Park
- Issue/브랜치: #31 / issue-31-cosmic-mutation-type-cross
- 소스 commit: `25c8434cfe19ecb8943aeec02e91c25f8ca38862`
- 시작/종료: 2026-07-31 (아래 attempt 1·2 모두 이 실험 세션에서 순서대로 실행)

#### 실행

EXP-005(#5)의 유전자×변이유형 희소 피처(30,697개)를 그대로 재현하고, 세
가지 구성을 순서대로 비교했다. attempt 1·2는 EXP-012(#12)의 COSMIC 보호
유전자 화이트리스트(361개)를 "보호 유전자 × 변이유형" 교차 파생변수로
추가하는 방식으로, 이미 유전자 단위에 존재하는 정보를 재집계하는 접근이었다.
두 attempt 모두 EXP-005보다 낮게 나오자, "유전자 단위 재집계는 구조적으로
새 정보가 아니다"라는 판단 아래 attempt 3에서는 개별 유전자 컬럼에 존재하지
않는 정보, 즉 **특정 코돈(hotspot) 단위 변이 여부**로 방향을 전환했다.
`scripts/explore_hotspot_numbering_consistency.py`(RUN_MODE=explore, 외부
transcript 데이터 없이 train/test 자체의 내부 일관성만 검사)로 BRAF 600,
IDH1 132, PIK3CA 545/1047 등 잘 알려진 driver hotspot 위치의 reference
amino acid가 이 패널 전체에서 문헌값과 정확히 일치·일관됨을 먼저 확인한 뒤,
검증된 9개 유전자·19개 위치만 hotspot 피처로 사용했다(KRAS/NRAS는 패널에
없어 제외). 세 attempt 모두 fold 분할과 무관하게 train/test 전체에서
계산되는 결정적 피처라 leakage 위험이 없다(PROJECT_CONTEXT.md 5절).

| 시도 | 피처 구성 | 피처 수 | Config | Metrics |
|---|---|---:|---|---|
| attempt 1 | EXP-005 전체 + 보호유전자 교차 8개(mutated/missense/synonymous/nonsense/frameshift/complex/missing count + LOF count) | 30,705 | `configs/exp031_cosmic_mutation_type_cross.yaml` | `reports/exp031_cosmic_mutation_type_cross/metrics.json` |
| attempt 2 | EXP-005 전체 + 보호유전자 LOF(nonsense+frameshift) count 1개만 | 30,698 | `configs/exp031_cosmic_lof_only_cross.yaml` | `reports/exp031_cosmic_lof_only_cross/metrics.json` |
| attempt 3 | EXP-005 전체 + 검증된 hotspot 19개 individual indicator + 총 hotspot count 1개 | 30,717 | `configs/exp031_hotspot_cross.yaml` | `reports/exp031_hotspot_cross/metrics.json` |
| attempt 4 | EXP-005 전체 + attempt 2의 LOF count 1개 + attempt 3의 hotspot 20개(결합) | 30,718 | `configs/exp031_lof_hotspot_combined.yaml` | `reports/exp031_lof_hotspot_combined/metrics.json` |
| **attempt 5(채택)** | EXP-005 전체 + hotspot 19개(attempt 3) + 신규 발굴 15개 individual indicator + 총 hotspot count 1개(34개 hotspot) | 30,732 | `configs/exp031_hotspot_extended.yaml` | `reports/exp031_hotspot_extended/metrics.json` |

attempt 5는 `scripts/explore_hotspot_candidate_mining.py`(RUN_MODE=explore)로
EXP-012 COSMIC 보호유전자 화이트리스트(361개) 전체를 대상으로 attempt 3의
검증 로직을 확장해 만들었다. 이 과정에서 중요한 **데이터 아티팩트**를
발견했다: 일부 유전자에서 특정 위치 조합이 서로 다른 환자 다수에서 정확히
동일하게(예: BRAF 600+512+548+563+566+578+603+640이 정확히 같은 39개 행에서,
TP53 16+43+136+175가 61개 행에서) 반복되는데, 이는 한 환자가 한 유전자
안에서 여러 코돈에 동시에 독립적인 점돌연변이를 얻는 실제 종양 생물학으로
설명할 수 없어 데이터 생성/전처리 과정의 인공물로 판단했다(상세는
`reports/exp012_feature_analysis/hotspot_artifact_clusters.csv`). "동일 유전자
내 위치 조합이 5회 이상 반복"을 아티팩트로 정의해 제외한 뒤(임계값은 결과를
보기 전에 고정) 482개 후보가 남았고, 이 중 개별적으로 문헌에 확실히
검증되는 10개 유전자·15개 위치만 사람이 선별해 채택했다(PIK3CA
E542K/Q546/N345, PTEN R130/R233, FBXW7 R505, AKT1 E17K, U2AF1 S34, APC
R1450/R876, POLE P286R/V411L, KIT D816, FGFR3 S249C, RAC1 P29S). HLA-A(생식계열
다형성), PABPC1/SIRPA/ATP1A1(확립된 driver 유전자 아님), TP53 확장 세트(약
50개, 생물학적 개연성은 높으나 개별 코돈 검증에 자신 없음), KMT2D/PLEC 등은
의도적으로 제외했다.

- Report: N/A
- 재현성 manifest: `reproducibility/exp031_cosmic_mutation_type_cross/config.resolved.yaml`,
  `reproducibility/exp031_cosmic_lof_only_cross/config.resolved.yaml`,
  `reproducibility/exp031_hotspot_cross/config.resolved.yaml`,
  `reproducibility/exp031_lof_hotspot_combined/config.resolved.yaml`,
  `reproducibility/exp031_hotspot_extended/config.resolved.yaml`

#### 결과

| 시도 | OOF Macro F1 | Accuracy | Log Loss |
|---|---:|---:|---:|
| EXP-005(부모, 비교 기준) | 0.4043796587 | 0.396549 | 1.863207 |
| attempt 1(교차 8개) | 0.3956074120 | 0.388486 | 1.875899 |
| attempt 2(LOF count만) | 0.4017847879 | 0.393969 | 1.864124 |
| attempt 3(hotspot 19개) | 0.4120236288 | 0.403322 | 1.835079 |
| attempt 4(LOF+hotspot 결합) | 0.4057616458 | 0.398645 | 1.835519 |
| **attempt 5(hotspot 34개, 팀 최고)** | **0.4135846695** | 0.406225 | 1.831068 |

- Fold Macro F1(attempt 1): 0.386807, 0.398357, 0.385085, 0.388885, 0.411211
- Fold Macro F1(attempt 2): 0.403056, 0.411966, 0.390054, 0.387770, 0.409737
- Fold Macro F1(attempt 3): 0.413077, 0.420928, 0.399671, 0.403889, 0.418962
- Fold Macro F1(attempt 4): 0.406582, 0.415506, 0.387467, 0.398288, 0.414055
- Fold Macro F1(attempt 5): 0.415084, 0.415961, 0.400686, 0.406536, 0.424850
- Public LB: 미제출 (attempt 5가 팀 최고 Local이지만 리더보드 제출은 보류,
  아래 선택 메모 참고)
- 재현 상태: NOT_STARTED

클래스별로는 attempt 2에서 ACC(+0.0205), LAML(+0.0182), SARC(+0.0168),
KIPAN(+0.0124), SKCM(+0.0081) 등 일부(주로 중간 규모) 클래스가 EXP-005보다
개선됐지만, PAAD(-0.0432), LUSC(-0.0378), LIHC(-0.0245), GBMLGG(-0.0145)의
하락폭이 더 커서 전체 OOF는 소폭 낮았다. attempt 1은 거의 모든 클래스에서
attempt 2보다 나빴다(전체 OOF 기준 -0.0062p 추가 하락).

attempt 3(hotspot)은 26개 클래스 중 19개가 EXP-005보다 개선됐다. 특히
**SKCM(흑색종) +0.0443**로 가장 크게 개선됐는데, SKCM은 BRAF V600E가 대표
드라이버 변이인 암종이라 이 피처가 실제 생물학적 신호를 포착했다는 정황
증거로 볼 수 있다. UCEC(+0.0342), PAAD(+0.0279), LUAD(+0.0249),
DLBC(+0.0223), SARC(+0.0217), STES(+0.0209), ACC(+0.0178), COAD(+0.0164)도
개선됐다. 하락한 쪽은 LIHC(-0.0329), LUSC(-0.0242), TGCT(-0.0153),
BLCA(-0.0110), PCPG(-0.0101), GBMLGG(-0.0083), THCA(-0.0033) 7개로,
전체적으로 개선폭이 하락폭을 크게 앞섰다.

attempt 4(LOF+hotspot 결합)는 EXP-005보다는 근소하게 높았지만(+0.0014p)
attempt 3(hotspot 단독)보다는 뚜렷하게 낮았다(-0.0063p). attempt 3 대비
클래스별 비교에서 18개 클래스가 하락하고 8개만 개선됐으며, LUAD(-0.0446),
PAAD(-0.0433), DLBC(-0.0223)의 하락폭이 LAML(+0.0162), LGG(+0.0123) 같은
개선폭보다 컸다. 즉 attempt 2의 LOF count는 attempt 3의 hotspot 신호와
"더해지는" 관계가 아니라 오히려 그 효과를 갉아먹었다 — attempt 2가
EXP-005 단독 대비로도 net negative였던 것과 일관된 결과다.

attempt 5(hotspot 34개)는 attempt 3 대비 14개 클래스가 개선되고 12개가
하락했다. PCPG(+0.0229), CESC(+0.0219), UCEC(+0.0209), THYM(+0.0201),
LIHC(+0.0168), PRAD(+0.0154), KIPAN(+0.0153)이 크게 개선된 반면
PAAD(-0.0370), BLCA(-0.0247), DLBC(-0.0156), COAD(-0.0139), OV(-0.0100)가
하락했다. 개선폭 합이 하락폭 합보다 커서 전체 OOF가 attempt 3보다
+0.0016p 더 높아졌다.

#### 산출물과 결론

- Metrics/Reproduction: 위 표의 시도별 경로
- 코드: `src/open_cancer/cosmic_mutation_features.py`
  (`build_cosmic_mutation_features`, `build_cosmic_cross_matrix`),
  `src/open_cancer/hotspot_features.py`
  (`build_hotspot_augmented_features`, `build_hotspot_matrix`, `KNOWN_HOTSPOTS`,
  `ADDITIONAL_HOTSPOTS`, `EXTENDED_HOTSPOTS`),
  `src/open_cancer/combined_mutation_features.py` (`build_lof_hotspot_features`),
  `scripts/run_exp031_cosmic_mutation_type_cross.py`,
  `scripts/run_exp031_cosmic_lof_only_cross.py`,
  `scripts/run_exp031_hotspot_cross.py`,
  `scripts/run_exp031_lof_hotspot_combined.py`,
  `scripts/run_exp031_hotspot_extended.py`,
  `scripts/explore_hotspot_numbering_consistency.py`(RUN_MODE=explore, 검증용),
  `scripts/explore_hotspot_candidate_mining.py`(RUN_MODE=explore, 후보 발굴·
  아티팩트 클러스터 탐지)
- 결론: **attempt 5(hotspot 34개) 최종 채택 — 팀 최고 Local 기록 갱신**
  (EXP-005 대비 +0.0092p, attempt 3 대비 +0.0016p). attempt 1·2("COSMIC
  보호 유전자 정보를 유전자 단위로 재집계")는 EXP-005를 넘지 못했고, attempt
  3·5("개별 유전자 컬럼에는 없는 코돈 단위 정보를 추가")는 넘었다. attempt
  4는 attempt 2와 3을 결합하면 더 나아질지 확인했지만 오히려 attempt
  3보다 낮아, 두 신호가 단순히 합산되지 않으며 LOF count 쪽이 순손실
  요인임을 재확인했다. attempt 5는 "새 정보 추가"라는 같은 원칙을
  화이트리스트 361개 전체로 확장해 재확인한 결과로, "정보가 이미
  유전자×변이유형 단위에 존재해 재집계는 net negative, 코돈 단위의 진짜
  새 정보만 net positive"라는 가설을 다시 한번 뒷받침한다. 팀 최고 기록
  갱신에도 불구하고 아직 리더보드에는 제출하지 않았다(선택 메모 참고).

#### 선택 메모

- COSMIC CGC v104 화이트리스트와 EXP-012 산출물(`protected_genes_final.csv`)은
  라이선스 확인 전까지 Git 미포함 — `reproducibility/exp031_cosmic_*/config.resolved.yaml`의
  `features.protect_gene_whitelist_sha256`으로 사용 파일을 고정했다.
- **hotspot 좌표 검증의 한계**: `KNOWN_HOTSPOTS`(9개 유전자, 19개 위치)와
  `ADDITIONAL_HOTSPOTS`(10개 유전자, 15개 위치)는 외부 정준(canonical)
  transcript 서열과 대조한 것이 아니라, (1) 이 데이터셋 자체의 train+test
  전체에서 reference amino acid가 내부적으로 일관되는지, (2) 그 값이
  문헌에 알려진 hotspot residue와 일치하는지만 확인한 것이다. 즉 "이
  데이터가 자기모순이 없고 통용되는 임상 넘버링과 결과가 같다"는 정황
  증거이지, 이 패널이 실제로 어떤 transcript를 썼는지 확인된 것은 아니다.
  UniProt/RefSeq 정준 서열(FASTA)과 검증된 hotspot 좌표표(cancerhotspots.org
  등, 라이선스 확인 필요)가 확보되면 검증 범위를 넓힐 수 있다.
- **데이터 아티팩트 발견**(attempt 5 과정에서): BRAF/RXRA/CD209/MUC1/TP53/
  FBXW7 등 일부 유전자에서 특정 위치 조합이 서로 다른 환자들에게서 정확히
  동일하게 반복 등장한다(`reports/exp012_feature_analysis/hotspot_artifact_clusters.csv`,
  131개 클러스터). 예: BRAF 600+512+548+563+566+578+603+640이 39개 행에서,
  TP53 16+43+136+175가 61개 행에서 항상 함께 나타남. 실제 종양이 한
  유전자 안에서 이렇게 많은 코돈에 동시에 독립적인 점돌연변이를 얻을
  가능성은 매우 낮아, 이 원본 CSV 데이터 자체(또는 그 생성 과정)에 아직
  원인이 특정되지 않은 인공적 패턴이 섞여 있을 가능성을 시사한다. 이번
  실험에서는 이런 반복 클러스터에 속한 관측치를 hotspot 근거에서 제외하는
  방식으로 대응했지만, 이 현상 자체가 다른 실험(예: mutation-presence
  기반 피처 전반)에도 영향을 줄 수 있는지는 별도로 확인되지 않았다.
- HLA-A(생식계열 다형성), PABPC1/SIRPA/ATP1A1(확립된 point-mutation driver
  유전자 아님)은 필터를 통과했지만 의도적으로 제외했다. TP53 확장 세트
  (약 50개 코돈)는 생물학적 개연성은 높지만 개별 검증에 자신이 없어 이번
  attempt 5에는 포함하지 않았다.
- KRAS/NRAS hotspot(G12/G13/Q61)은 두 유전자 모두 이 패널의 컬럼에 없어
  (EXP-012에서 이미 확인된 한계) 포함하지 못했다.
- 다음 행동 후보: (a) attempt 5를 리더보드에 제출하기 전 `INFERENCE_VERIFIED`
  체크포인트 검증(EXP-003/EXP-005 방식) 수행, (b) 위에서 발견한 데이터
  아티팩트의 원인을 조사(가능하면 대회 주최측 공지 확인), (c) 외부 정준
  서열과 검증된 hotspot 좌표표를 확보해 TP53 확장 세트와 나머지 protect
  유전자로 검증 범위를 넓히는 것 검토, (d) attempt 2(LOF count)는 단독·
  결합(attempt 4) 모두 net negative로 재확인됐으므로 이 방향은 더 탐색하지
  않는다.
