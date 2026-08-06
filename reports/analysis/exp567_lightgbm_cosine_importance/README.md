# EXP-567 LightGBM class-cosine 중요도 감사

## 결론

26개 class-cosine은 EXP-567 LightGBM에서 중복적으로 무시되는 피처가 아니다.
전체 5-fold checkpoint 합산 기준으로 다음 비중을 차지했다.

- gain share: **46.0671%**
- split share: **54.5483%**
- family joint permutation Macro F1 delta: **-0.2036123 ± 0.0134768**

여기서 delta는 원 validation Macro F1에서 permutation 후 Macro F1을 뺀 값이다.
따라서 양수일수록 해당 family와 환자 행의 연결을 끊었을 때 성능이 낮아졌음을
뜻한다. cosine permutation은 5개 fold × 3회, 총 15회 모두 `+0.1841` 이상이었다.

이 결과는 EXP-565/566/567의 통제 비교와 같은 방향이다.

| Arm | 입력 | OOF Macro F1 | 판단 |
|---|---|---:|---|
| EXP-565 | parser parent only | 0.4272525489 | 원시 표현만으로는 부족 |
| EXP-566 | 26 cosine only | 0.2674060456 | 손실 압축이라 단독 대체 불가 |
| EXP-567 | parser parent + cosine | 0.4477416384 | 상호 보완 |

따라서 cosine은 독립 representation도, 제거 가능한 중복 노이즈도 아니다.
parser-v4 의미 벡터를 26개 암종 방향으로 투영하여 LightGBM이 쉽게 분할하도록
만드는 **지도 압축 보조 피처**로 판정한다.

## Family 결과

| Family | 열 수 | Gain share | Split share | Permutation F1 delta |
|---|---:|---:|---:|---:|
| class cosine | 26 | 46.0671% | 54.5483% | 0.2036123 |
| sample aggregate | 12 | 12.3407% | 9.8587% | 0.0915455 |
| gene mutated | 4,384 | 10.3425% | 6.8090% | 0.0631478 |
| fixed hotspot | 35 | 5.0343% | 1.3807% | 0.0364818 |
| fixed pathway | 64 | 5.4749% | 3.5440% | 0.0351294 |
| max residue position | 4,384 | 13.7769% | 18.6039% | 0.0338961 |
| gene missense | 4,384 | 3.5476% | 3.6586% | 0.0136714 |
| gene synonymous | 4,384 | 2.2493% | 0.8357% | 0.0086304 |
| gene frameshift | 4,384 | 0.8413% | 0.5176% | 0.0033539 |
| gene nonsense | 4,384 | 0.3254% | 0.2435% | 0.0019962 |
| gene complex | 4,384 | 0% | 0% | 0 |
| gene missing | 4,384 | 0% | 0% | 0 |

상위 cosine은 SKCM, CESC, BLCA, LAML, TGCT 순이었다. cosine 26개가 모두
사용됐으며 SKCM cosine 하나만 전체 gain의 5.12%를 차지했다.

## 해석 제한

- gain·split은 모델의 사용량이지 생물학적 인과 중요도가 아니다.
- correlated family를 통째로 섞으면 실제 데이터에 없는 조합을 만들 수 있으므로
  permutation delta를 해당 family의 순수 기여량으로 해석하지 않는다.
- class-cosine은 outer-train label로 만든 supervised feature다. validation과 test는
  outer-train centroid로 transform-only 했지만, 일반적인 비지도 임베딩과는 다르다.
- test와 Public LB는 이번 분석 및 판단에 사용하지 않았다.
- LightGBM은 XGBoost식 `cover` 중요도를 직접 제공하지 않으므로 gain과 split만
  기록했다.

## 방법과 재현

- Issue: #576
- 분석 대상: EXP-567의 저장된 5-fold LightGBM checkpoint
- canonical stratified 5-fold, seed 42
- fold validation 전체 행에서 원 점수가 EXP-567 metrics와 일치하는지 먼저 확인
- 한 family의 모든 열에 동일한 행 순열을 적용하여 family 내부 관계는 유지
- fold별 3회 deterministic permutation
- 실행 명령:

```bash
PYTHONPATH=src:scripts uv run python \
  scripts/audit_exp567_lightgbm_feature_importance.py \
  --artifact-root <EXP-567-artifacts가-있는-저장소-root> \
  --permutation-repeats 3
```

산출물:

- `family_importance.csv`: family gain/split/permutation 요약
- `feature_importance.csv`: 전체 피처 gain/split
- `summary.json`: fold·checkpoint hash·반복별 raw delta

## 다음 결정

cosine 제거·축소 실험은 진행하지 않는다. 다음 공식 실험은 EXP-527 XGBoost와
EXP-567 LightGBM의 사전 고정 `0.5/0.5` 확률 블렌드다. 두 모델은 동일 피처를
쓰지만 OOF 라벨 불일치율이 25.59%, 정오답 상관이 0.753이고 서로만 맞힌 행도
각각 369·384개라 모델 다양성 검증 가치가 있다.
