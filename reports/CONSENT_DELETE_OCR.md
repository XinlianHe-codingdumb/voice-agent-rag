# 文档确认、删除与 OCR 修复报告

## 问题原因及修复

原确认函数只接受少数完整短句，截图中的两种长句都未匹配。随后待确认状态被清除，确认语被送给普通模型，模型口头表示“已选中”却没有真实写入。

现在自然确认先进入应用控制逻辑：在 SQLite 中实际关联文档，再恢复原问题。用户明确表示稍后发问时只选文档并等待，不抢答。带否定的确认不授权；模糊条件要求再次确认。文字、Mic、Live Call 共用这个入口。前端重新读取服务器选择状态，不凭模型文本勾选。

删除对话会删除消息及文档关联，不删除资料库文件和长期记忆。移除文件会清除所有对话的关联及该文件待确认状态，并持久化隐藏标记，重启不会自动恢复。磁盘源文件和索引保留，重新上传可恢复；这不是永久擦除。

以前纯扫描 PDF 会被拒绝。现在文字少于 80 字符的页面采用本地 RapidOCR + PDFium，保留页码。新索引另存 extraction.json 留下每页提取来源和字符数。现有缓存不自动重建，文件入口仍只接受 PDF。

## 已验证

真实后端结果：`runs/20260905T025905Z_consent-delete-ocr/result.json`。

- 初始仅勾选 Treasury，提出 AI Agent Book 问题后批准，自然确认实际保留 Treasury 并新增 AI Agent Book。
- “Yes, please do that.” 自动继续原问题，回答强化学习位于第 8 章，引用该书 PDF 第 16、290 页。
- “Yes, please select it. I'll send you my question based on that.” 先完成选择；后续问题仍检索该书并返回来源。
- 合成纯图片 PDF 没有文字层，OCR 后建立索引；真实 RAG 回答金额 4729 美元，引用 PDF 第 1 页。
- 合成文件从资料库及对话选择中移除；两个临时对话已删除。用户资料未删除。

## 失败也留痕

- 第一轮单元测试 63 通过、1 失败：PDFium 4.30 不支持文档 context manager。改为显式 finally 关闭。
- 第二轮 63 通过、1 失败：OCR 将 ORION 识别成 ORlON。未伪造纠正结果；测试保留金额严格验证，另以小于 5% 字符替换误差验收该样本。该例 1/37 字符错误。
- `runs/20260905T025806Z_consent-delete-ocr/` 保留临时目录权限冲突失败。修复回归脚本使用每次运行独立 pytest 临时目录后成功。

## 边界

Live Call 这次验证的是共享后端接口和浏览器事件回放，不是物理麦克风/WebRTC 音频端到端测试。OCR 已验证清晰英文印刷扫描件，不能据此声称复杂表格、手写、所有中文扫描质量均合格。文字丰富但夹有图片文字的页面目前不会全面 OCR。当前同意识别仍是可审计规则，不是任意表达都能理解的语义模型。

实现参考：[RapidOCR 1.4.4 API](https://rapidai.github.io/RapidOCRDocs/v1.4.4/install_usage/api/RapidOCR/)、[PDFium Python API](https://pypdfium2.readthedocs.io/en/v4/python_api.html)。
