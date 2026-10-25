# 离线评估报告

- 预测器：rule-based（离线 baseline）
- 用例数：40
- 通过数：38
- 决策准确率：95.0%
- 澄清率：20.0%
- 错误接受（应澄清却放行）：0

## 分类准确率

| 类别 | 用例 | 通过 | 准确率 |
| --- | ---: | ---: | ---: |
| task | 14 | 13 | 93% |
| knowledge | 14 | 13 | 93% |
| chitchat | 6 | 6 | 100% |
| clarify | 6 | 6 | 100% |

## 失败用例

| id | 输入 | 期望 | 实际 |
| --- | --- | --- | --- |
| t-logistics-02 | 我上次买的那件衣服什么时候能到 | task / flow=logistics_tracking | clarify / reason=missing_track |
| k-refund-02 | 钱什么时候能退回来 | knowledge / intents=refund_policy | clarify / reason=missing_track |
