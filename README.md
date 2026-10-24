# 中文教材编写 Skills · 使用说明

管理科学与工程学科（本科高年级 / MBA）中文教材编写工具集，共 9 个 skill，串成一条流水线：

```
0 textbook-builder（总控，判断你在第几步）
        │
1 拆解样本 ──> 2 课标映射 ──> 3 大纲 ──> 4 正文 ──> 7 审校 ──> 8 排版
                    │            │          │
                    └────────────┴──────────┴──> 5 练习 / 6 素材
```

## 一、装在哪里

9 个 skill 已安装到 `~/.workbuddy/skills/`，所有项目可用。源码在工作区 `skills/` 下，改完需重新同步（见第六节）。

## 二、按场景找 skill

| 你想做的事 | 用哪个 | 示例请求 |
|---|---|---|
| 不知道下一步做什么 | `textbook-builder` | 「这个教材项目下一步做什么」 |
| 拆解获奖教材，摸清体例 | `textbook-analyzer` | 「拆解这本教材，做横向对比」 |
| 把课标变成学习目标 | `curriculum-mapper` | 「把课标拆成教学目标」 |
| 设计章节与课时 | `outline-designer` | 「设计 48 学时 MBA 教材大纲」 |
| 写一节课正文 | `unit-writer` | 「按大纲写第 2 单元第 3 课」 |
| 出分层习题 | `exercise-designer` | 「给这一课配三层练习题」 |
| 编案例与情境数据 | `material-creator` | 「写个案例，制造业系统上线冲突」 |
| 交稿前体检 | `textbook-reviewer` | 「审一下这一课，看能不能交」 |
| 导出 Word | `textbook-formatter` | 「按体例排版成 docx」 |

**不适用**：纯翻译、润色、查重、逐字校对错别字、生成插图、生成 PDF、考试命题。

## 三、三条硬约定

1. **学科与学段必给**。学段只能是「本科高年级」或「MBA」，它决定全部篇幅参数。
2. **大纲先行**。写正文前必须有 `<course-slug>-outline.md` 或至少给清「课程名 + 单元号 + 课号 + LO-x-y」。没挂 LO 的稿件过不了审校。
3. **走文件不走口头**。上一环的产物是文件，下一环直接吃这个文件；不要在对话里传结论。

## 四、产物与自检

| 产物 | 命名 | 自检 |
|---|---|---|
| LO 表 | `LO表.csv` | `check_lo.py` |
| 大纲 | `<course-slug>-outline.md` | `check_outline.py` |
| 正文 | `<course-slug>-u<单元>-l<课>.md` | `check_draft.py` |
| 习题 | `<course-slug>-ex-u<单元>-l<课>.md` | `check_exercise.py` |
| 审校报告 | `<course-slug>-review-u<单元>-l<课>.md` | — |
| Word | `<课程名>-<单元>-<课>.docx` | 排版核对单 |

报 ERROR 不能交付，这是 SOP 的红线。

## 五、当前状态

**v1.1.2 已发布（人工评审与专家审定经项目负责人决定豁免）。** 交付包：`dist/textbook-skills-v1.1.2.zip`（旧版归档在 `dist/archive/`）。

- 触发测试：9 个 skill × 20 条，漏判 0、误判 0 ✅
- 脚本回归：4 个脚本全绿；K7（结构缺失短路）已修 ✅
- 效果用例：6 条全部产出（实验组、对照组、跨学段、超长、两条审校）✅
- 人工盲评、学科专家签字：⏭️ 豁免（`docs/盲评包/` 保留备查，随时可补评）

**必须遵守的使用限制**（豁免带来的代价）：

| 限制 | 原因 |
|---|---|
| 产出只能作内部起草，不得对外称「已审定教材」 | 规范库未经专家签字 |
| 每份产出标注「初稿·未经学科审定」 | 同上 |
| 不得引用审校评分作为质量承诺 | 五维权重未经第三方验证 |
| 事实、数据段落逐条人工核实 | T-06 已证明脚本查不出编造事实 |

## 六、维护

| 改了什么 | 要做什么 |
|---|---|
| `规范库/` 任一文件 | 重新复制到各 skill 的 `references/`，否则脚本与规则会打架 |
| 任一 `SKILL.md` | 跑 `python tools/trigger_test.py`，确认 0 漏判 |
| 规则微调 | 升小版本号，同步 `CHANGELOG.md` |
| 任何文件改动 | 重新打包 `dist/textbook-skills-v<版本>.zip`（内容：`skills/` `docs/` `规范库/` `tools/` + `meta/` 三份文档） |
| 底层模型升级 | 重跑全部用例（SOP 阶段 6） |

同步命令：

```bash
cp 规范库/*.md skills/textbook-reviewer/references/
cp 规范库/体例规范.md 规范库/学段适配.md skills/outline-designer/references/ skills/textbook-builder/references/
cp 规范库/体例规范.md 规范库/语言风格.md 规范库/学段适配.md 规范库/练习设计.md skills/unit-writer/references/
cp 规范库/体例规范.md 规范库/学段适配.md skills/textbook-formatter/references/ 2>/dev/null
cp skills/unit-writer/scripts/check_draft.py skills/textbook-reviewer/scripts/
cp skills/outline-designer/scripts/check_outline.py skills/unit-writer/scripts/
```

> `check_draft.py` 与 `check_outline.py` 各有多份副本，必须同源，否则同一稿件在不同 skill 下判定会不一致。
