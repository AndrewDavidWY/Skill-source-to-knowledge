# 证据账本约定

脚本接受 UTF-8 JSON。参考 `examples/synthetic-pilot/evidence.json` 创建底稿。相对路径以账本所在文件夹为根，文件必须位于根内；校验器不访问网络，不允许绝对路径、目录逃逸或指向根外的符号链接。

## 顶层

- `schema_version`：整数 `1`。
- `title`：成果标题。
- `material_mode`：`synthetic-demo`（完全合成）或 `research-draft`（真实研究材料）。混合材料使用后者，逐份注明类型。
- `as_of`：本次审阅截止日期，ISO `YYYY-MM-DD`。
- `scope_note`：读过什么、没有读过什么、结论范围。
- `sources`：来源数组，稳定 `id` 不重复。
- `claims`：论断数组，稳定 `id` 不重复。

## 来源

每个来源包括 `id`、`title`、`creator`、`source_type`、`path`、`sha256`、`document_date`、`event_date`、`version`、`access`、`reuse_basis`、`rights_note`、`coverage`。日期可用 `unknown`，不要猜测。时间区间或多次事件写进 `coverage`。

- `creator`：原作者或负责主体；未知时写 `unknown`，不要把整理者误填为原作者。
- `source_type`：材料性质，例如规划、会议纪要、项目登记、宣传简报或修订说明。
- `access`：`synthetic`、`public` 或 `restricted`。
- `reuse_basis`：`synthetic`、`public-domain`、`licensed`、`permission` 或 `unknown`。`public` 只是可访问性，不是再利用许可。
- `rights_note`：公开或复制依据的可核验说明。真实授权记录可能本身保密，公开稿不应包含其敏感原文。
- `coverage`：读取页码、正文／表格／图像范围、OCR 不确定性等。
- `supersedes`：可选的旧版本 ID 数组，只表达文档版本关系，不表示新版本必定真实。关系必须无循环。

脚本按原始字节计算 SHA-256，按 UTF-8 `splitlines()` 计行。先固定转录版本再记录引文；原始 PDF、扫描件或影音文件另外保留哈希及“页码／时间戳 → 转录行”的映射。样例是原生文本，因此不展示 OCR；不要误称脚本直接验证 PDF 页码。

## 论断

每项含 `id`、`text`、`kind`、`publication`、`limits`、`citations`。

- `kind`：`historical-plan`、`documented-observation`、`interpretation`、`hypothesis`、`unverified`。
- `publication`：`ready` 或 `hold`。这是审阅者的声明，不是脚本授予公开许可。
- `limits`：适用范围、缺失依据、冲突、解释限制或待检验设计，不可留空。
- `citations`：至少一条，每条含 `source_id`、`start_line`、`end_line`、`quote`、`relation`。行号为从 1 开始的闭区间，`quote` 必须与所指行全文一致（不含末尾换行）。`relation` 为 `supports`、`contradicts`、`context`。历史计划和记录观察至少有一条 `supports`；这只是结构约束，语义仍需审阅。

`unverified` 可在公开解释“尚未证实”时使用 `ready`，但必须保留限制；不应把未核实主张当作已成立事实。`hypothesis` 是基于现有材料提出的检验方向，需要写出待测试条件，不是结果。

## 公开校验与限制

`--public` 检查账本中的每份来源，而不只检查被引用的来源。受限来源或 `reuse_basis=unknown` 失败；合成来源与合成再利用标签应一致，合成演练不能混入真实来源。每项论断必须为 `ready`。

真实工作中应另建不含私有原件的公开包，再在公开包内运行检查。脚本不能发现未登记文件、秘密、姓名、语义夸大或伪造的许可，必须审查完整输出和实际发布清单。

退出码：`0` 结构检查通过；`1` 数据或文件检查失败；`2` 命令行用法错误。渲染器会先校验，只输出 Markdown 到标准输出，不写入来源文件、不提交或发布任何内容。
