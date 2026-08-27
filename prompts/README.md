# 经营分析报告模块 prompts

这些 prompt 按 Dify 工作流中的模块独立使用，不在 prompt 层整合完整报告。

最终报告由程序根据模块结果硬编码组织，模块之间不互相生成或改写内容。

文件结构：

- `shared.md`：各模块可共同引用的最小安全规则
- `channel.md`：第一屏·渠道全景
- `product.md`：第二屏·品类营收结构
- `efficiency.md`：第三屏·获客成本信号
- `growth-quality.md`：第四屏·投放有效性
- `summary.md`：第五屏·总结模块；只接收前四屏结果

## 使用方式

- `type=channel` 只调用 `channel.md`
- `type=product` 只调用 `product.md`
- `type=efficiency` 只调用 `efficiency.md`
- `type=growth_quality` 只调用 `growth-quality.md`
- `type=summary` 调用 `summary.md`，输入前四屏结果
- `type=all` 仍然分别调用各模块，再由程序按固定顺序拼装
