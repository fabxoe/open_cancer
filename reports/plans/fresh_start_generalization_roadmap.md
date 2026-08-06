# 처음부터 다시 설계하는 일반화 우선 로드맵

> Task Issue: [#658](https://github.com/fabxoe/open_cancer/issues/658)

136개 과거 실험은 결과를 복사할 기준선이 아니라 실패 양상을 확인하는 참고
증거로만 사용한다. 새 공식 결과는 별도 Experiment Issue와 canonical 5-fold에서
다시 측정한다.

## 실행 순서

1. **Raw contract와 parser correctness**
   - 원본 해시·schema·결측·토큰 multiplicity를 먼저 고정한다.
   - `X`, `*`, `Ter` equivalence, 공백·대소문자, signed/partial 표기의
     metamorphic test를 필수로 둔다.
   - isoform annotation은 고정 release·hash·reference 일치 상태를 보존하고,
     불확실 위치를 정상 residue로 강제 해석하지 않는다.

2. **Adversarial validation을 모델 실험 전에 실행**
   - raw 요약 domain AUC와 parser-native family domain AUC를 QC로 기록한다.
   - test prevalence와 domain propensity는 피처 선택·threshold·sample weight에
     사용하지 않는다.
   - 첫 raw-first 결과는 OOF AUC 0.7277526507로, 초기 경고 gate를 명확히 통과했다.

3. **Local 채택 gate**
   - primary: 전체 OOF Macro F1 개선.
   - 동시 안전 gate: Log Loss 비악화, fold std 악화 0.002 미만, 클래스 F1
     0.05 이상 붕괴 없음.
   - Macro F1만 개선하고 Log Loss가 악화한 후보는 주력 승격·조기 제출에서 제외하고
     독립 앙상블 후보로만 보존한다.

4. **사후 보정 조기 중단**
   - probability offset, threshold, sample-weight redistribution은 각 공간에서
     사전 고정한 대표 1회만 허용한다.
   - 비대상 클래스 이동 또는 Log Loss 악화가 재현되면 같은 메커니즘의 scale/grid
     변형을 중단한다.

5. **처음부터 독립적인 모델 트랙 두 개**
   - Track A: notation-invariant·isoform-aware canonical event + tree model.
   - Track B: canonical event document/TF-IDF 또는 raw mutation presence 기반의
     선형/RandomForest 계열. Track A의 parser-derived burden 열을 그대로 복제하지 않는다.
   - 같은 `(6201, 26)` OOF·class order를 저장하고 correctness correlation과 label
     disagreement를 사전에 감사한 뒤에만 blend한다.

6. **계층 라벨은 상한으로 측정**
   - KIPAN/KIRC와 GBMLGG/LGG confusion을 pair 합산 정확도와 pair 내부 정확도로
     분해한다.
   - specialist가 pair 내부 Macro F1과 전체 Log Loss를 동시에 개선하지 못하면
     반복 교정하지 않고 구조적 ambiguity로 기록한다.

7. **조기·소량 Public probe**
   - parser/피처 철학이 다른, Local gate와 `INFERENCE_VERIFIED`를 통과한 후보만
     소량 제출한다.
   - 같은 계보의 미세 변형을 연속 제출하지 않는다. Local Macro F1·Log Loss와
     Public 전이의 관계를 제출 전 사전 등록한 표로 누적한다.

## 바로 다음 공식 실험

첫 Experiment Issue는 Track A의 최소 기준선으로 한다. raw mutation presence를
보존하면서 stop-notation-invariant canonical event와 isoform eligibility를 적용하고,
sample token multiplicity 계열은 넣지 않는다. 피처·parser schema·모델·seed·fold를
사전 고정하고 Macro F1과 Log Loss 공동 gate로 판정한다. 그 결과를 본 뒤가 아니라
동시에 Track B의 독립 기준선 Issue도 생성한다.

