# 中文教材编写 Skills

![version](https://img.shields.io/badge/version-1.1.3-blue)

![skills](https://img.shields.io/badge/skills-9-green)

![rules](https://img.shields.io/badge/规范库-62%20条-orange)

![scope](https://img.shields.io/badge/学科-管理科学与工程-lightgrey)

![format](https://img.shields.io/badge/format-Agent%20Skills-blueviolet)

![deps](https://img.shields.io/badge/校验脚本-零依赖-success)

面向**管理科学与工程**学科（本科高年级 / MBA）的中文教材编写流水线。9 个 skill 把「拆样本 → 课标映射 → 大纲 → 正文 → 练习/素材 → 审校 → 排版」固化成一条可执行、可检查的流程，每一步都有确定的输入、确定的产物，以及一个能跑出结论的自检脚本。

写教材真正的麻烦不是「写不出来」，而是**写出来的东西不像一本教材**：篇幅凭感觉、练习和正文对不上、审校靠通读一遍说「感觉还行」。这套 skill 的做法是把这些判断变成可核对的事实——字数按区间卡、每题必须挂学习目标、审校先跑脚本再过人眼。

**不绑定某一个客户端。** 内容就是 Markdown 规则 + 纯 Python 脚本：遵循 [Agent Skills](https://skill.md) 开放标准的客户端（Claude Code、Cursor、Codex、WorkBuddy 等）可直接加载；不支持的客户端也能用——把仓库放进项目、在 `AGENTS.md` 里指个路即可；**完全不用 AI 也能跑**，四个校验脚本是零依赖的命令行工具。

> ⚠️ **使用前请读第七节。** 本项目的规范库未经学科专家签字，人工盲评经项目负责人决定豁免。产出只能作内部起草，不得对外称「已审定教材」。



---

## 一、快速开始

### 1.1 装上

Agent Skills 的约定是「一个 skill 一个目录，目录里必须有 `SKILL.md`」。不同客户端只是扫描的目录不同，**内容完全一样**，所以装一次可以喂给多个工具。

| 客户端         | 个人级（所有项目可用）            | 项目级（仅当前项目）                                                   |
| ----------- | ---------------------- | ------------------------------------------------------------ |
| Claude Code | `~/.claude/skills/`    | `.claude/skills/`                                            |
| Cursor      | 建议用项目级                 | `.cursor/skills/` 或 `.agents/skills/`（也会读 `.claude/skills/`） |
| Codex       | 建议用项目级                 | `.agents/skills/`                                            |
| WorkBuddy   | `~/.workbuddy/skills/` | `.workbuddy/skills/`                                         |

**推荐做法：只留一份真身，其余用链接。** 这套东西最大的维护坑是「规则副本不同步」——9 个 skill 各自带着 `references/` 副本，多装几份就等于多几个漂移点。

```bash
# 取一份真身
git clone https://github.com/hcming2026/textbook-writing-skills.git ~/src/textbook-skills

# 建个人级目录，把 9 个 skill 逐个链过去（macOS / Linux）
mkdir -p ~/.claude/skills
for d in ~/src/textbook-skills/skills/*/; do ln -sfn "$d" ~/.claude/skills/; done
```

Windows 用**目录联接**（实测：联接不需要管理员权限，符号链接需要，所以不要用 `ln -s` 代替）：

```powershell
$src = "C:\src\textbook-skills\skills"
Get-ChildItem $src -Directory | ForEach-Object {
  New-Item -ItemType Junction -Path "$env:USERPROFILE\.workbuddy\skills\$($_.Name)" -Target $_.FullName
}
```

> 不要用 `cmd` 的 `for /d %d in ("路径\*")`——给通配符集合加引号会关掉通配符展开，循环一个目录都拿不到；不加引号又扛不住路径里的空格。PowerShell 这版两种毛病都没有。

不想折腾链接就整目录拷贝，代价是以后改规则要重新拷、容易漏：

```bash
cp -r skills/* <目标目录>/
```

**客户端不认 `SKILL.md` 怎么办。** 内容照样能用，只是要手动指路。在项目根的 `AGENTS.md`（Cursor、Codex 都读；Claude Code 在没有 `CLAUDE.md` 时也读）里加三行：

```markdown
教材编写按 skills/textbook-builder/SKILL.md 的流程走。
各环节规则见 规范库/（62 条，TY/YY/XD/LX/SJ 编号）。
正文写完必须跑 skills/unit-writer/scripts/check_draft.py，有 ERROR 不得交付。
```

模型读到路径会自己去读文件，不需要把规则贴进上下文——这也是这套东西能跨客户端的原因：它依赖的是「文件可读」，不是「某个产品的功能」。

### 1.2 不用 AI 也能用

四个校验脚本只依赖 Python 标准库（3.8+，无第三方包），可以当普通命令行工具用：

```bash
python skills/unit-writer/scripts/check_draft.py 我的稿件.md
python skills/outline-designer/scripts/check_outline.py 我的大纲.md
python skills/curriculum-mapper/scripts/check_lo.py LO表.csv
python skills/exercise-designer/scripts/check_exercise.py 习题.md --level=MBA
```

唯一有外部依赖的是 `textbook-analyzer/scripts/render_pages.py`（扫版 PDF 需要 `pip install pymupdf` 才能渲染）。

规则本身也是可读的：`规范库/` 里 62 条规则就是给人看的，不装任何工具、不看任何代码，照着写也行。

### 1.3 验证装对了

```bash
# 把 $SKILLS 换成一个真实存在的 skill 目录
SKILLS=~/.claude/skills          # 或 ~/.workbuddy/skills
python $SKILLS/unit-writer/scripts/check_draft.py \
       $SKILLS/unit-writer/assets/范文-u2-l3.md
# 期望输出：结果：0 个 ERROR，0 个 WARN
```

跑出 `0 个 ERROR，0 个 WARN` 说明脚本与规则副本都齐了。若报「未识别到三层小标题」之类的结构错误，多半是文件没拷全；若报 `No such file`，检查链接是否指到了目录本身而不是目录内容。

### 1.4 用起来

不需要记 skill 名字，**照平常说话就行**，触发词命中后会自己路由：

| 你说                  | 谁接手                         |
| ------------------- | --------------------------- |
| 「我要写一本教材，从哪开始」      | `textbook-builder` 判断你处在哪一环 |
| 「拆解这本教材，做横向对比」      | `textbook-analyzer`         |
| 「把课标拆成学习目标」         | `curriculum-mapper`         |
| 「设计 48 学时 MBA 教材大纲」 | `outline-designer`          |
| 「按大纲写第 2 单元第 3 课」   | `unit-writer`               |
| 「给这一课配三层练习题」        | `exercise-designer`         |
| 「写个案例，制造业系统上线冲突」    | `material-creator`          |
| 「审一下这一课，看能不能交」      | `textbook-reviewer`         |
| 「按体例排版成 docx」       | `textbook-formatter`        |

---

## 二、流水线

```
0  textbook-builder ── 总控：读项目状态，判断你在第几步，路由到下面某一个
        │
        ├─ 1 拆解样本 ──── textbook-analyzer    样本 PDF → 九维分析表
        ├─ 2 课标映射 ──── curriculum-mapper    课标/培养方案 → LO 表 (.csv)
        ├─ 3 大纲 ──────── outline-designer     LO 表 → 三级大纲 (.md)
        ├─ 4 正文 ──────── unit-writer          大纲 + 节标识 → 六栏稿件 (.md)
        ├─ 5 练习 ──────── exercise-designer    稿件 + LO → 分层习题 (.md)
        ├─ 6 素材 ──────── material-creator     案例方向 → 情境数据 (.md)
        ├─ 7 审校 ──────── textbook-reviewer    稿件 → 审校报告 (.md)
        └─ 8 排版 ──────── textbook-formatter   通过稿 → .docx
```

上游产物是文件，下游直接吃这个文件——**不要在对话里传结论**。整条链能中断、能重跑、能交给别人接着做，靠的就是这个约定。

---

## 三、9 个 Skill

| Skill                | 做什么                              | 典型触发语                          | 产物                        |
| -------------------- | -------------------------------- | ------------------------------ | ------------------------- |
| `textbook-builder`   | 项目状态判断与路由，不做具体写作                 | 「我要写一本教材」「现在该做什么」「还缺哪些产物」      | 环节判定 + 调度                 |
| `textbook-analyzer`  | 按九维拆解样本教材，出单套分析表与横向对比表           | 「拆解这本教材」「看看别人怎么编的」「提炼编写规律」     | `分析表.md`                  |
| `curriculum-mapper`  | 课标 / 培养方案 → 可追溯的学习目标表            | 「把课标拆成教学目标」「对齐课程标准」「目标怎么编号」    | `LO表.csv`                 |
| `outline-designer`   | 全书—单元—课时三级大纲，含学时配平               | 「排目录」「划分单元」「分配课时」「定每节课的篇幅配额」   | `<slug>-outline.md`       |
| `unit-writer`        | 按六栏体例写一节课完整正文                    | 「写一课」「撰写第 2 章第 3 节」「改写成另一学段版本」 | `<slug>-u<单元>-l<课>.md`    |
| `exercise-designer`  | 基础 / 提高 / 拓展三层习题，每题挂 LO          | 「出练习题」「配一套案例分析题」「设计拓展题」        | `<slug>-ex-u<单元>-l<课>.md` |
| `material-creator`   | 原创案例与情境数据，数据须自洽可核算               | 「写个案例」「造一组可核算的数据」「编一个情境」       | 素材 `.md`                  |
| `textbook-reviewer`  | 五维评分 + 否决项核查 + 带位置的问题清单          | 「审一下这一课」「能不能定稿」「出个审校报告」        | `<slug>-review-u_-l_.md`  |
| `textbook-formatter` | 稿件 → 结构化 Word（标题层级、栏目样式、题注、参考文献） | 「排版成 Word」「导出 docx」「统一标题样式」    | `.docx`                   |

**不适用**：纯翻译、润色、查重、逐字校对错别字、生成插图、生成 PDF、考试命题。`textbook-reviewer` 只出报告不改稿，改稿回 `unit-writer`。

---

## 四、三条硬约定

1. **学科与学段必给。** 学段只能是「本科高年级」或「MBA」，它决定全部篇幅参数——同一个知识点，本科导语 150–250 字、MBA 200–350 字；正文 3000–4500 对 2500–3500。学段说错，后面全错。
2. **大纲先行。** 写正文前必须有 `<slug>-outline.md`，或至少给清「课程名 + 单元号 + 课号 + `LO-x-y`」。没挂 LO 的稿件过不了审校。
3. **走文件不走口头。** 上一环的产物是磁盘上的文件，下游读文件，不读对话。

---

## 五、产物与自检脚本

| 环节   | 产物命名                      | 自检                                                |
| ---- | ------------------------- | ------------------------------------------------- |
| LO 表 | `LO表.csv`                 | `check_lo.py <LO表.csv>`                           |
| 大纲   | `<slug>-outline.md`       | `check_outline.py <大纲.md>`                        |
| 正文   | `<slug>-u<单元>-l<课>.md`    | `check_draft.py <稿件.md> [--json]`                 |
| 习题   | `<slug>-ex-u<单元>-l<课>.md` | `check_exercise.py <习题.md> [--level=MBA 或 本科高年级]` |
| 样本拆解 | `分析表.md`                  | `render_pages.py <教材.pdf> --probe`（先探文本层再渲染识读）    |
| 审校报告 | `<slug>-review-u_-l_.md`  | 复用 `check_draft.py`                               |
| Word | `<课程名>-<单元>-<课>.docx`     | 排版核对单                                             |

脚本只出**事实性违规清单**（第几行、违反哪条规则），不给分。分数由 `textbook-reviewer` 按 `审校标准.md` 的权重给——这个分工是刻意的，见第七节。

报 ERROR 不能交付，这是红线。WARN 可交付但要在报告里写明。

---

## 六、规范库

`规范库/` 是规则母本，共 **62 条**，用编号前缀区分来源：

| 文件        | 编号                | 条数 | 管什么                                       |
| --------- | ----------------- | -- | ----------------------------------------- |
| `体例规范.md` | `TY-01` … `TY-19` | 19 | 层级、编号、六栏体例、术语引注、章末收口、字数口径、章末参考文献     |
| `语言风格.md` | `YY-01` … `YY-25` | 25 | 句式、人称、时态；段级推进动作（学术史四要素／分域扫描／收口三件套）；附 5 类禁用词表 |
| `学段适配.md` | `XD-01` … `XD-05` | 5  | 本科高年级 / MBA 的篇幅参数与难度曲线                    |
| `练习设计.md` | `LX-01` … `LX-08` | 8  | 三层结构、题型配比、可评分性                            |
| `审校标准.md` | `SJ-X1` … `SJ-X5` | 5  | 五维权重、否决项、脚本可判项清单                          |

**六栏体例**（顺序不可变）：导语 → 正文 → 案例 → 思考 → 练习 → 拓展。

**五个否决项**（触发即「不通过」，不进入评分）：思想性问题 / 科学性错误 / 版权问题 / 编造事实 / 违反 GB/T。设成否决项而不是扣分项，是为了避免用平均分把严重问题稀释掉。

规则以**母本为准**，各 skill 的 `references/` 是副本。改规则必须双向同步，否则同一稿件在写作端和审校端判定会不一致。

---

## 七、质量状态与使用限制

### 已验证（机器可判）

| 项目   | 结果                                                                                                                              |
| ---- | ------------------------------------------------------------------------------------------------------------------------------- |
| 触发测试 | 9 skill × 20 用例 = 180 条，漏判 0 / 误判 0（`tools/trigger_test.py`）                                                                    |
| 脚本回归 | 4 个校验脚本全绿（`check_lo` / `check_outline` / `check_draft` / `check_exercise`）                                                      |
| 审校用例 | 范文 0 ERROR / 0 WARN；故意写坏的稿件 17 ERROR / 4 WARN。另有 2 条否决项由人工判出（`SJ-X2` 科学性错误、`SJ-X4` 编造事实）——**脚本一条都没报出来**，这正是"脚本查格式、人工查对错"必须分工的证据 |
| 跨学段  | 同一课写成本科版与 MBA 版，篇幅差异可被脚本检出（`XD-05`）                                                                                             |
| 对照组  | 有 skill / 无 skill 各一份，差异可逐条核对                                                                                                   |

### 未经第三方验证（豁免）

| 项目           | 状态    | 这意味着什么                      |
| ------------ | ----- | --------------------------- |
| 人工盲评（A/B 评分） | ⏭️ 豁免 | 「用了 skill 是否更好」**没有对照评分证据** |
| 规范库 5 份专家签字  | ⏭️ 豁免 | 「62 条规则是否正确」**只有编写者自证**     |

**豁免不等于通过。** 这两项是 SOP 要求的人工闸门，经项目负责人决定跳过。后果必须由使用者承担：

1. 产出只能作**内部起草**，不得对外称「已审定教材」。
2. 每份产出标注「初稿 · 未经学科审定」。
3. 不得引用五维评分作为质量承诺——权重本身未经第三方验证。
4. **事实与数据段落必须逐条人工核实。** 测试用例已经证明：脚本查不出编造事实，它只查格式与结构。

`docs/盲评包/` 完整保留（A/B 去标识文件、评分表、密封映射表），随时可以补做盲评。

---

## 八、目录结构

```
.
├── skills/                  9 个 skill（44 文件）
│   └── <skill>/
│       ├── SKILL.md         触发描述 + 执行步骤（渐进加载的第一层）
│       ├── references/      该 skill 用到的规则副本
│       ├── scripts/         自检脚本
│       └── assets/          模板与范文
├── 规范库/                   5 份规则母本（62 条）
├── docs/
│   ├── 阶段2-样本拆解报告.md
│   ├── 阶段5-测试与评估报告.md
│   ├── 阶段6-发布检查清单.md
│   ├── 测试用例/             T-03 ~ T-06 与两份对照组
│   └── 盲评包/               A/B 文件 + 评分表 + 密封映射表
├── tools/trigger_test.py     触发回归工具
├── dist/                     交付包 zip（当前 v1.1.4，旧版在 archive/）
├── 需求说明书.md             阶段 1 产出：范围、边界、验收标准
├── CHANGELOG.md              版本记录与已知问题
└── README.md
```

`参考教材/` 不随仓库分发（第三方版权图书）。

---

## 九、维护

| 改了什么                        | 要做什么                                                |
| --------------------------- | --------------------------------------------------- |
| `规范库/` 任一文件                 | 重新复制到各 skill 的 `references/`，否则脚本与规则会打架             |
| 任一 `SKILL.md` 的 description | 跑 `python tools/trigger_test.py`，确认仍是 0 漏判；触发词表要同步改 |
| 规则微调                        | 升小版本号，同步 `CHANGELOG.md`                             |
| 任何文件改动                      | 重新打包 `dist/textbook-skills-v<版本>.zip`               |
| 底层模型升级                      | 重跑全部用例（SOP 阶段 6）                                    |

同步命令：

```bash
cp 规范库/*.md skills/textbook-reviewer/references/
cp 规范库/体例规范.md 规范库/学段适配.md skills/outline-designer/references/ skills/textbook-builder/references/
cp 规范库/体例规范.md 规范库/语言风格.md 规范库/学段适配.md 规范库/练习设计.md skills/unit-writer/references/
cp 规范库/体例规范.md 规范库/学段适配.md skills/textbook-formatter/references/
cp skills/unit-writer/scripts/check_draft.py skills/textbook-reviewer/scripts/
cp skills/outline-designer/scripts/check_outline.py skills/unit-writer/scripts/
```

> `check_draft.py` 与 `check_outline.py` 各有多份副本，**必须同源**。副本不同步的典型症状：同一稿件在 `unit-writer` 下 0 ERROR，在 `textbook-reviewer` 下报一堆错。

---

## 十、常见问题

**Q：能不能直接写 MBA 的课，不给大纲？**  
不能。至少要给「课程名 + 单元号 + 课号 + `LO-x-y`」。没挂 LO 的稿件，审校第一步就会卡住——因为没有 LO 就无法判断这一课该讲什么、练习该考什么。

**Q：审校给了 4.5 分，是不是可以交了？**  
分数只反映**规范符合度**，不反映内容对错。五维评分里没有「观点是否正确」这一项，那是人工的事。另外见第七节第 3 条。

**Q：为什么脚本报了一堆 ERROR，我觉得没问题？**  
脚本判的是格式事实（字数、编号、栏目、挂载关系），不做语义判断。如果确实认为规则不合理，改 `规范库/` 母本并同步副本，而不是绕过脚本。

**Q：字数为什么和我 Word 里看到的不一样？**  
口径不同。本系列按**汉字数**计（只数中日韩统一表意文字，不含标点、数字、英文、空格），与 Word「字符数（不计空格）」相差 5%–8%，见 `TY-18`。

**Q：能改成别的学科吗？**  
`TY` 与 `YY` 两类规则通用；`XD`（学段参数）、`LX`（练习配比）和方法论部分是针对管理科学与工程的，换学科需要重做阶段 2 的样本拆解，不能只改几个数字。

---

## 许可

本仓库尚未指定开源许可证，默认保留所有权利。如需在教学中复用或二次分发，请先开 issue 联系。

代码部分建议将来采用 MIT，文档与规则部分建议 CC BY-NC 4.0（禁止商业出版用途）——两者诉求不同，不宜用同一个许可证覆盖。目前保持未指定状态，是为了避免默认授予超出意图的权利。

---

## 参考

- `需求说明书.md` — 项目范围、边界、验收标准（阶段 1）


- `docs/阶段5-测试与评估报告.md` — 触发测试、效果测试、通过标准
- `docs/阶段6-发布检查清单.md` — 发布前 14 项核对结果
- `CHANGELOG.md` — 版本记录与已知问题（K1–K7）
