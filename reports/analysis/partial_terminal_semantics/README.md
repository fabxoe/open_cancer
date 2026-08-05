# Signed frameshift·bilateral-stop 부분 표기 감사

> Task Issue: [#362](https://github.com/fabxoe/open_cancer/issues/362)
>
> Parent roadmap: [#360](https://github.com/fabxoe/open_cancer/issues/360)

## 결론

두 문법은 정보를 버리지 않고 구조화하되, 표준 protein consequence를 발명하지
않는다.

```text
-762fs  -> signed_nonstandard_frameshift
*261*   -> bilateral_stop_unresolved
```

`-762fs`의 `-762`는 signed source field로 보존하지만 정상 protein residue
coordinate가 아니다. 입력에 `c.` prefix·transcript·DNA consequence가 없으므로
이를 5′ UTR이나 N-terminal extension이라고 확정하지 않는다.

`*261*`은 stop 기호 두 개와 숫자 261을 보존하지만 ordinary nonsense(`Y261*`),
stop-loss/extension(`*261Qext*17`) 어느 문법에도 충분하지 않다. 따라서
`bilateral_stop_unresolved`이며 extension으로 승격하지 않는다.

## 전수 감사

| 문법 | train occurrences | train unique | test occurrences | test unique |
|---|---:|---:|---:|---:|
| signed nonstandard frameshift | 75 | 53 | 19 | 16 |
| bilateral-stop unresolved | 99 | 80 | 13 | 13 |

signed 형태는 train에서 NPM1 17건, test에서 NPM1 4건이 가장 많지만 gene
분포나 빈도를 의미 규칙 선택에 사용하지 않았다. bilateral-stop도 여러 유전자에
분산되어 있으며, 이 사실만으로 extension이라고 확정할 수 없다.

## 모델 계약

- 두 형식 모두 `position_eligible=false`
- 기존 adapter에서는 계속 `other_unmappable`
- raw token·signed/source position·marker 유무는 provenance로 보존
- 오류·passenger·암종 driver라고 단정하지 않음
- 이번 Task에서는 새 feature와 실험 점수를 만들지 않음

## 재실행

```bash
uv run python scripts/audit_partial_terminal_tokens.py
uv run pytest -q tests/test_protein_partial_terminal_semantics.py
```
