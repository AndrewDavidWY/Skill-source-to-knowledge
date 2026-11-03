# 历史资料转化为可追溯知识产品

把旧规划、白皮书和项目记录整理成来源明确、版本可核对、证据边界清楚的文章、课程或书稿。

**状态：试点版。** 本仓库提供中文 Skill、证据账本约定、校验脚本、单元测试及一组完全合成的演练。它没有使用真实客户材料，也不声称已经验证知识产品的业务效果。脚本通过不等于事实或版权已经获审。

## 使用

将本仓库复制到支持本地 Skill 的工具，将文件夹命名为 `source-to-knowledge`。在 Codex 中可放入 `~/.codex/skills/source-to-knowledge/`，开始新会话后用 `$source-to-knowledge` 调用。Skill 源文件为中文，不代表已提供其他语言译稿。

示例请求：

> 用 $source-to-knowledge 整理这批旧项目资料。先列来源和版本，区分当年的计划、记录的实践和有证据的成果，再选一个主题写短样稿。不要公开原始资料。

> 用 $source-to-knowledge 把已审阅的专题改成一节课程，保留事实出处、适用条件和待检验假设。只交付草稿。

## 内容

- [SKILL.md](SKILL.md)：适用范围与工作流程。
- [数据契约](references/evidence-contract.md)：来源、论断、引文和版本关系。
- [审阅与公开检查](references/review-and-publication.md)：语义、权限、版权和公开前检查。
- [合成试点](examples/synthetic-pilot/README.md)：四份虚构历史材料、完整账本、专题样稿和审阅记录。

## 本地验证

校验与渲染脚本只使用 Python 3 标准库，无网络请求或账号凭据。支持 Python 3.10 及以上。

```bash
python3 scripts/validate_evidence.py examples/synthetic-pilot/evidence.json --public
python3 scripts/render_brief.py examples/synthetic-pilot/evidence.json --public > /tmp/knowledge-brief.md
python3 -m unittest discover -s tests -v
```

`--public` 会拒绝声明为受限的来源、缺少再利用依据的来源和不适合公开的论断。它不是敏感信息检测器，也不能核验权限声明真伪；发布前仍须人工审核完整待发布文件。不要把真实私有材料复制进公开仓库运行试点。

## 与智库研究 Skill 的关系

本 Skill 侧重历史材料的来源、版本、时间和论断追溯；“智库专题研究与内容发布”侧重重新研究理论、形成论证和发布内容。可以串联使用，但不把历史资料整理等同于理论验证，也不要求绑定某个网站。
