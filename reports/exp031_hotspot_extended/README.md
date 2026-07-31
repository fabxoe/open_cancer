# EXP-031 EXP-005 변이유형 피처 + 알려진 cancer hotspot 위치 피처 (attempt 5)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-031 / #31 |
| 목적 | EXP-005(변이 유형 세분화)와 EXP-021(COSMIC 지식 요약)을 비교해 얻은 "이미 있는 정보를 재집계하면 손해, 개별 컬럼에 없는 새 정보를 추가하면 이득"이라는 가설을 검증하고, 실제로 팀 최고 기록을 갱신하는 것 |
| 핵심 입력 | EXP-005의 유전자×변이유형 희소 피처(30,697개) + 검증된 cancer hotspot 위치 34개 individual indicator + 총 hotspot count 1개 = 30,732개 |
| 모델 | XGBoost `XGBClassifier` (EXP-005와 동일 하이퍼파라미터) |
| Local OOF Macro F1 | **0.4135846695002278** (attempt 5, 팀 최고) |
| Public LB | **0.3170803849** (제출 ID `1506950`, 팀 최고) |
| 판단 | 채택 — 팀 최고 Local·Public LB 기록. 단, 원 제출 checkpoint 미보관으로 재현 상태는 `FAILED` |

## 원본 데이터와 입력

train 6,201명, test 2,546명이며 각 환자는 4,384개 유전자 열로 표현된다(각 셀은
`WT` 또는 `S27N`, `R1538*`, `L1854fs` 같은 변이 문자열). EXP-005는 이 정보를
"유전자마다 변이 여부 + 변이 유형(missense/synonymous/nonsense/frameshift/complex)"
으로 세분화했다. EXP-031은 여기에 "**특정 코돈(hotspot) 단위**로 변이가
발생했는가"라는, 개별 유전자 컬럼만으로는 절대 표현할 수 없는 정보를 추가로
결합했다. 예를 들어 BRAF 유전자가 변이됐다는 사실만으로는 알 수 없지만,
그 변이가 정확히 600번째 코돈(V600E, 흑색종의 대표 드라이버 변이)에서
일어났는지는 이 새 피처로만 알 수 있다.

## 핵심 개념과 피처: 5번의 시행착오

이 Issue에서는 서로 다른 5가지 시도를 거쳐 지금의 결과에 도달했다. attempt
1~4는 공식 EXP-ID를 별도로 부여하지 않은 탐색적 ablation이고, attempt 5만
`EXP-031`의 공식 채택 config다. 실패한 탐색도 다음 실험에 참고하도록 남겼다.

| 시도 | 아이디어 | 결과 |
|---|---|---|
| attempt 1 | COSMIC 보호 유전자(361개) × 변이유형을 교차한 파생변수 8개 추가 | EXP-005보다 낮음(미채택) |
| attempt 2 | attempt 1을 LOF(기능소실) count 1개로 축소 | 여전히 EXP-005보다 낮음(미채택) |
| attempt 3 | 잘 알려진 driver 유전자의 특정 hotspot 코돈 19개를 개별 indicator로 추가 | EXP-005보다 개선(팀 최고 갱신) |
| attempt 4 | attempt 2(LOF)와 attempt 3(hotspot)을 결합 | attempt 3보다 낮음(결합 시 상쇄) |
| **attempt 5** | attempt 3의 hotspot을 COSMIC 화이트리스트 361개 전체에서 자동 채굴 + 사람이 문헌 대조로 검증한 15개 위치로 확장(19→34개) | **attempt 3보다 추가 개선, 팀 최고** |

**attempt 1·2 vs attempt 3·5의 차이**: attempt 1·2는 이미 개별 유전자 컬럼에
존재하는 정보(어떤 유전자가, 어떤 유형으로 변이됐는가)를 COSMIC 지식으로
"재집계"한 것이라 새로운 정보가 아니었다. attempt 3·5는 "그 유전자의 어느
정확한 위치가 변이됐는가"라는, 개별 컬럼 방식으로는 원천적으로 표현 불가능한
정보를 추가했다. 이 차이가 성패를 갈랐다.

**attempt 5의 hotspot 34개는 어떻게 골랐나**: 최초 후보 탐색에서는
`scripts/explore_hotspot_candidate_mining.py`로
COSMIC 보호 유전자 화이트리스트(361개, EXP-012) 전체에서 "관측 횟수가 충분하고
reference amino acid가 내부적으로 일관된" 위치를 자동으로 찾았다. 이 과정에서
일부 유전자(BRAF, TP53 등)에서 여러 코돈이 서로 다른 환자들에게 정확히 동일한
조합으로 반복 등장하는 **데이터 아티팩트**를 발견해 제외했고(아래 한계 절 참고),
남은 후보 482개 중 사람이 문헌 대조로 개별 검증한 15개 위치(PIK3CA E542K/Q546/
N345, PTEN R130/R233, FBXW7 R505, AKT1 E17K, U2AF1 S34, APC R1450/R876, POLE
P286R/V411L, KIT D816, FGFR3 S249C, RAC1 P29S)만 attempt 3의 19개에 추가했다.
최초 후보 채굴은 train과 test의 변이 분포를 함께 확인한 transductive
탐색이었다. 이 사실을 한계로 기록한다. 공식 runner는 최종 추가 15개 목록을
고정한 뒤 train에서 각 위치의 관측이 5회 이상인지와 reference amino acid가
일관되는지를 다시 검증한다. test는 고정 목록의 피처를 계산할 때만 사용한다.

## 모델이 학습하는 정보

모델 입력은 유전자별 변이 여부·유형과 34개 hotspot 위치의 정확한 일치 여부다.
타깃은 고정 순서 26개 `SUBCLASS`다. 피처 생성에는 `SUBCLASS`를 사용하지 않았고
EXP-005와 동일하게 클래스 불균형을 고려한 balanced sample weight를 각 fold의
학습 데이터에서 계산했다. XGBoost 파라미터 전체는
`reproducibility/exp031_hotspot_extended/config.resolved.yaml`에 기록했다.

## 검증 방법

팀 공용 `data/splits/stratified_5fold_seed42.csv`를 사용했다. 각 fold에서
나머지 4개 fold로 학습하고 한 fold를 검증해, 모든 환자의 OOF 예측을 채운 뒤
전체 OOF Macro F1을 계산했다(fold 수 5, seed 42, fold seed 42~46).

## 실제 결과

### Local OOF (5개 시도 비교)

| 시도 | OOF Macro F1 | Accuracy | Log Loss |
|---|---:|---:|---:|
| EXP-005(부모, 비교 기준) | 0.4043796587 | 0.396549 | 1.863207 |
| attempt 1 | 0.3956074120 | 0.388486 | 1.875899 |
| attempt 2 | 0.4017847879 | 0.393969 | 1.864124 |
| attempt 3 | 0.4120236288 | 0.403322 | 1.835079 |
| attempt 4 | 0.4057616458 | 0.398645 | 1.835519 |
| **attempt 5(채택)** | **0.4135846695** | 0.406225 | 1.831068 |

attempt 5의 fold별 Macro F1: 0.415084, 0.415961, 0.400686, 0.406536, 0.424850
(fold 평균 0.412624, 표준편차 0.008321).

attempt 5는 attempt 3 대비 26개 클래스 중 14개가 개선됐다(PCPG +0.0229, CESC
+0.0219, UCEC +0.0209, THYM +0.0201, LIHC +0.0168, PRAD +0.0154, KIPAN
+0.0153). 12개는 하락했지만(PAAD -0.0370, BLCA -0.0247, DLBC -0.0156, COAD
-0.0139, OV -0.0100) 개선폭 합이 더 커서 전체가 순개선됐다.

attempt 3에서 EXP-005 대비 가장 크게 개선된 클래스는 **SKCM(흑색종)
+0.0443**이었는데, SKCM은 BRAF V600E가 대표 드라이버 변이인 암종이라 이
피처가 실제 생물학적 신호를 포착했다는 정황 증거로 볼 수 있다.

### Public leaderboard

- 제출 파일: `submissions/exp031_hotspot_extended.csv`
- 제출 ID: `1506950`
- 제출 시각: 2026-07-31 15:50:02 KST
- Public score: **0.3170803849**
- 순위: 확인 당시 전체 2위(1위 6조 0.37149)

EXP-005(0.2987843366) 대비 **+0.0182960483** 개선했다. Local OOF 개선폭
(+0.0092, EXP-005 대비)보다 Public LB 개선폭이 더 커서, hotspot 방향이
로컬 검증뿐 아니라 실제 제출 성능에서도 유효함을 확인했다.

## 해석과 한계

- **원 제출 재현 실패**: 원 Windows 실행의 checkpoint와 test 확률을 보관하지
  않아 macOS에서 같은 코드·설정으로 재학습했다. OOF Macro F1은
  `0.4125795545`로 원 기록 `0.4135846695`와 달랐고, test 라벨 일치율도
  `93.3621%`에 그쳤다. 따라서 원 제출을 `INFERENCE_VERIFIED`로 승격하지 않고
  `FAILED`로 유지한다. 상세 비교는
  `reproducibility/exp031_hotspot_extended/comparison.json`에 있다.
- **hotspot 좌표 검증의 한계**: 34개 위치는 외부 정준(canonical) transcript
  서열과 직접 대조한 것이 아니라, (1) 이 데이터셋 자체의 train+test에서
  reference amino acid가 내부적으로 일관되는지, (2) 그 값이 문헌에 알려진
  hotspot residue와 일치하는지만 확인한 것이다. UniProt/RefSeq 정준 서열과
  검증된 hotspot 좌표표가 확보되면 검증 범위를 넓힐 수 있다.
- **데이터 아티팩트 발견 및 CV 영향 조사**: 후보 채굴 중 BRAF/TP53/RXRA/
  CD209/MUC1에서 여러 코돈이 서로 다른 환자들에서 정확히 동일한 조합으로
  반복되는 현상을 발견했다(`reports/exp012_feature_analysis/hotspot_artifact_clusters.csv`).
  `scripts/explore_duplicate_row_investigation.py`로 후속 조사한 결과, 이
  클러스터는 전부 **test에만** 존재하고(train 0건) train 5-fold CV를 직접
  왜곡할 수 없으며, 클러스터에 속한 행들도 서로 완전히 다른 환자였다. 별도로
  발견한 "전체 행 완전 중복"(train의 16.4%)도 대부분(447/451 그룹) 서로 다른
  SUBCLASS를 가진 희소(대부분 WT) 프로필의 우연한 충돌이었고, 진짜 우려할
  케이스(중복+같은 클래스+여러 fold 분산)는 11개 행뿐이라 지금까지의 OOF
  비교를 실질적으로 훼손하지 않는다고 판단했다. 다만 이 test-only 아티팩트의
  근본 원인은 밝혀지지 않았다.
- KRAS/NRAS hotspot(G12/G13/Q61)은 두 유전자 모두 이 패널의 컬럼에 없어
  (EXP-012에서 이미 확인된 한계) 포함하지 못했다.
- 순위는 제출 화면 확인 시점의 값이며 이후 바뀔 수 있다.

## 다음 실험 후보

1. 다음 제출부터 공식 runner가 clean worktree를 강제하고 실행 직후 checkpoint,
   OOF, test probability와 manifest를 함께 보관하도록 한다. 원 EXP-031 제출은
   당시 checkpoint가 없어 사후에 동일성을 증명할 수 없다.
2. 외부 정준 서열(UniProt/RefSeq)과 검증된 hotspot 좌표표(cancerhotspots.org
   등, 라이선스 확인 필요)를 확보해 TP53 확장 세트(~50개 코돈)와 나머지
   protect 유전자로 검증 범위 확대(낮은 우선순위, 개선폭 체감 곡선이 이미
   뚜렷함: attempt 3→5에서 위치 수를 거의 두 배로 늘렸지만 개선폭은 1/5
   이하로 줄었다).
3. 유전자 쌍 co-occurrence 피처(개별 유전자 컬럼에 없는 또 다른 정보 유형).
4. attempt 1·2(COSMIC 재집계, LOF count)는 단독·결합 모두 net negative로
   재확인됐으므로 더 탐색하지 않는다.

## 재현과 관련 파일

- Config: `reproducibility/exp031_hotspot_extended/config.resolved.yaml`
- Metrics: `reports/exp031_hotspot_extended/metrics.json`
- Submission: `submissions/exp031_hotspot_extended.csv`
- Source commit: 이 PR의 최신 커밋(`git log`로 확인)
- Reproduction status: `FAILED`
- 관련 코드: `src/open_cancer/hotspot_features.py`(`KNOWN_HOTSPOTS`,
  `ADDITIONAL_HOTSPOTS`, `EXTENDED_HOTSPOTS`), `scripts/run_exp031_hotspot_extended.py`,
  `scripts/explore_hotspot_numbering_consistency.py`,
  `scripts/explore_hotspot_candidate_mining.py`,
  `scripts/explore_duplicate_row_investigation.py`
- 전체 5개 시도의 상세 로그: [`EXPERIMENT_HISTORY.md`의 EXP-031 항목](../../EXPERIMENT_HISTORY.md#exp-031-exp-005-변이유형-피처--cosmic-보호유전자-교차-피처)
