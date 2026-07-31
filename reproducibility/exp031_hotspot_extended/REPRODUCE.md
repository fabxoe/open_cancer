# EXP-031 재현 복구 결과

원 실행의 checkpoint와 test 확률 파일이 보관되지 않아 checkpoint 추론 재생성은
수행할 수 없었다. 동일한 원본 데이터 해시, 공용 split, 코드와 설정으로 macOS에서
독립 재학습했지만 원 결과와 일치하지 않았다.

```text
원 OOF Macro F1:       0.41358466950022776
재학습 OOF Macro F1:  0.4125795545221178
원 제출 라벨 일치율:  0.9336213668499608
불일치 test 라벨:      169 / 2546
```

따라서 이 실험의 재현 상태는 `FAILED`이며 `INFERENCE_VERIFIED`로 승격하지 않는다.
원 제출 CSV는 리더보드 사실 증빙으로 그대로 보존한다. 이 구성을 최종 후보로 다시
사용하려면 새 Experiment Issue에서 clean 실행하고, 제출 전에 checkpoint, OOF,
test 확률과 재현 번들을 보관해야 한다.
