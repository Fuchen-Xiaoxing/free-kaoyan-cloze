# CHANGELOG

## [1.0.0] - 2026-10-28

### 初始发布：FREE考研英语完形填空一对一私教 Skill

- **SSOT 单一事实来源架构**：
  - `SKILL.md` 作为轻量高刚性状态机控制器，严格定义四阶段推进流程（阶段 0 篇章宏观锚定 → 阶段 1 逐空攻坚循环 → 阶段 2 全篇宏观复盘 → 阶段 3 收尾统一联动）与停顿铁律。
  - `references/methodology.md` 承载完形填空专属核心方法论（三维宇宙拓扑、三大对应法则、遮选预填、分词性题型策略、红花绿叶双保险、十大排除矩阵、5A-5B-5C-5D 宏观平衡约束与极限保底机制）。
  - `references/style-guide.md` 规范完形课堂授课口吻、遮选预填示范感、三大辨识度特征与零音标铁律。
  - `references/sentence-core.md` 规范完形长难句标准化七板块拆解，设空处补全并加粗，遵循模块化积木模型与增量组装。
  - `references/error-log-format.md` 定义 12 类完形填空错误封闭枚举、能力短板集合与持久化 Schema。
  - `references/script-contracts.md` 规范移动端友好型传参契约与无残留自愈清理机制。
- **自动化工具链 (`scripts/`)**：
  - `scripts/record_error.py`：完形错题归档工具，适配 `YYYY-[E1-|E2-]Cloze-Q[01-20]` 标准 ID 规范化，内置跨平台安全持久化存储路径探测（Android Documents / Open Minis / PC Documents `考研英语/错题本.md`）、旧数据自动迁移、12 类完形错误校验与临时文件自动清理。
  - `scripts/memo_import.py`：墨墨背单词一键导入工具，集成词汇规则化原型还原（`-s/-es`, `-ed`, `-ing`）、词组核心词提取与虚词停用词过滤、≤30 词截断保护与临时文件自动清理。
  - `scripts/vocab_export.py`：向后兼容包装层。
