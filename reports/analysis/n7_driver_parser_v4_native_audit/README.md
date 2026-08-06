# N7 driver 독립 재검증 — parser v4 native 여부 감사

> Task Issue: [#584](https://github.com/fabxoe/open_cancer/issues/584)
>
> Parent roadmap: [#422](https://github.com/fabxoe/open_cancer/issues/422)
> `reports/plans/parser_v4_baseline_reset_roadmap.md` §12 "N6 이후 재검증
> 순서" 2번(driver)
>
> N6 선례: Issue #493 / PR #495 / Issue #497 / PR #499

## 배경

N6(isoform 독립 재검증)는 `isoform_relative_position.py`·`isoform_semantics.py`가
legacy `mutation_features._SUBSTITUTION` 정규식을 직접 import해서 substitution
position/reference eligibility를 판정하던 것을 parser v4
(`mutation_parser_contract.route_protein_mutation`)로 교체하는 작업이었다.
N7은 로드맵상 같은 패턴이 "driver" 소비자에도 있는지 확인하는 단계다.

## 감사 방법과 결과

target-independent 정적 감사(코드 grep, SUBCLASS·test 분포·Public LB 미사용).

```bash
grep -rln "driver" src/open_cancer/*.py
```

저장소에서 "driver" 관련 실질 로직을 갖는 모듈은
`src/open_cancer/driver_event_signature.py`(Task #390, parent roadmap #360)
하나뿐이었다. `hotspot_features.py`·`pole_ed_features.py`는 문헌 고정
hotspot/panel이며 이 로드맵이 말하는 "driver" 재검증 대상이 아니다(N8
pathway·hotspot 스코프에 속함).

```bash
grep -n "^from\|^import" src/open_cancer/driver_event_signature.py
grep -n "^from\|^import" src/open_cancer/protein_duplication_semantics.py
grep -n "mutation_features" src/open_cancer/driver_event_signature.py \
  src/open_cancer/protein_duplication_semantics.py
grep -n "importlib\|__import__\|getattr(.*mutation_features\|globals()\[" \
  src/open_cancer/driver_event_signature.py \
  src/open_cancer/protein_duplication_semantics.py
```

- `driver_event_signature.py`는 legacy `mutation_features`를 전혀 import하지
  않는다. `protein_duplication_semantics.classify_protein_duplication`만
  사용한다.
- `protein_duplication_semantics`는 `mutation_parser_contract.py`가 라우팅하는
  parser v4 공식 계약의 일부다(내부에서 `PROTEIN_DUPLICATION_SEMANTICS_VERSION`을
  parser contract에 등록). 즉 `driver_event_signature.py`는 처음부터 parser v4
  native였고, N6의 isoform과 달리 legacy 경로 자체가 없었다.
- 동적 import·문자열 기반 우회(`importlib`, `__import__`, `getattr`,
  `globals()[...]`)로 legacy를 호출하는 패턴도 없었다.

```bash
grep -rln "driver_event_signature\|DriverCellSummary\|summarize_driver_cell" \
  src/open_cancer/*.py scripts/*.py
```

`driver_event_signature.py`를 실제로 import하는 코드는
`scripts/audit_driver_event_signature.py`(자체 감사 스크립트) 뿐이다. 어떤
Feature Family Registry·`frozen_feature_specs.py`·모델 runner에도 연결되어
있지 않은 QC 전용 코드다.

## 결론

N7이 전제하는 "legacy parser에 의존하는 driver 소비자"가 현재 코드베이스에는
존재하지 않는다. `driver_event_signature.py`는 이미 parser v4 native이고,
모델 피처로 소비되지 않는 QC 전용 모듈이라 OOF 영향 자체가 성립하지 않는다.
N6와 같은 형태의 migration·재실행 실험이 필요 없다 — **정적 감사만으로
COMPLETED 처리**하고 N8(pathway·hotspot 재검증)로 진행한다.

## 남은 확인 사항(사용자 스모크 테스트)

정적 grep 감사는 이 세션에서 완료했으나, `scripts/audit_driver_event_signature.py`
실제 실행은 스크립트 실행 규칙에 따라 저장소 소유자가 직접 확인한다.

```bash
uv run python scripts/audit_driver_event_signature.py
```

현재 parser v4 하에서도 예외 없이 정상 종료하고
`reports/analysis/driver_event_signature/audit.json` 출력이 기존과 동일한
구조를 유지하는지 확인하면 된다(값 자체는 원래도 parser v4 기반이었으므로
변경을 기대하지 않는다).

## 이 Task는 EXP-ID 없음

`RUN_MODE=explore` — 모델 재실행이나 Feature Spec 변경 없음. 기존 EXP-374/392
등 결과와 `EXPERIMENT_HISTORY.md`는 수정하지 않는다.
