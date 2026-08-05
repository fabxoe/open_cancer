# Parser v4-native feature adapter 검증

> Issue: [#427](https://github.com/fabxoe/open_cancer/issues/427)
>
> 모델 학습이나 점수 생성 없이 N2 고정 feature schema와 실제 데이터 연결을
> 검증한 결과입니다.

## 결과

- 고정 유전자 순서: `4,384`개
- 출력 차원: `26,316`
- train matrix: `(6201, 26316)`, nonzero `261,914`
- test matrix: `(2546, 26316)`, nonzero `215,705`
- feature-name SHA-256:
  `25602ca32efaeae474a5b280819cfbafad0270453f6e05496db878ae273bd025`
- schema SHA-256:
  `be230576e5364322d3670872eece5a7249c09bc05796e4373148c39333e8622a`
- raw mutation presence 재구성: train·test 모두 불일치 `0`행

## 표현 원칙

한 유전자 셀에 같은 의미의 token이 여러 개 있어도 해당 의미의 gene indicator는
한 번만 켭니다. 샘플 요약도 raw token count가 아니라 affected-gene count입니다.
이는 isoform annotation multiplicity와 test의 긴 token 나열이 모델 입력을 과도하게
증폭하는 것을 막습니다.

모델 입력으로 활성화한 의미는 다음과 같습니다.

```text
missense
no_change
nonsense
frameshift
range_replacement
non_simple_or_unresolved
```

deletion·insertion·delins와 reference-dependent duplication 판정의 세부 payload는
parser와 QC provenance에 남아 있지만
train 지원이 각각 3·0·0 token이므로 첫 native matrix에 세부 고차원 열로 노출하지
않습니다. 이들은 coarse fallback에 포함되어 mutation presence가 사라지지 않습니다.

## 재실행

```bash
uv run python scripts/audit_parser_v4_native_adapter.py
```

상세 기계 판독 결과는 [`validation.json`](validation.json)에 기록합니다.
