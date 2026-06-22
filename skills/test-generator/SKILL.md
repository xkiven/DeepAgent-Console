---
name: test-generator
description: 为变更逻辑、边界场景、行为契约和回归防护生成有针对性的测试。
allowed-tools: read_file glob grep
metadata:
  owner: demo
---
# Test Generator

当用户要求补测试、增强回归覆盖或生成示例测试用例时，使用这个技能。

工作流程：
1. 先阅读实现代码，推断它对外暴露的行为契约。
2. 至少覆盖成功路径、失败路径和一个有意义的边界场景。
3. 保持测试可重复、可预测且规模精简。
4. 如果仓库里已有测试风格，优先沿用现有风格。
