# v1.2.0 — 修掉三处会直接出错的配置问题

规则内容没变（仍 68 条）。这一版改的是**九份 `SKILL.md` 之间的关系**——那些"该一致却没一致"的地方。

## 如果你装过上一版，建议升级

三项修复里有两项直接影响使用：

**① 脚本命令现在能跑通了。** 上一版七处命令写的是 `python scripts/check_draft.py`，依赖当前目录是 skill 目录。实际安装后你的工作目录是教材项目，那里没有 `scripts/`，命令直接报 `No such file or directory`。现在统一为：

```bash
python <SKILL_DIR>/scripts/check_draft.py 我的稿件.md
```

`<SKILL_DIR>` 指 skill 所在目录（如 `~/.claude/skills/unit-writer`），每份 `SKILL.md` 开头都写了这句约定。

**② 边界声明进了 description。** Agent Skills 是渐进加载，第一层只读 `name` 和 `description`。上一版九份里八份把「不适用：…」写在正文，**路由时根本看不到**——于是「帮我排成 Word」可能先触发 `unit-writer`。现在九份统一带一句：

> 不用于：设计大纲（→ outline-designer）、只出习题（→ exercise-designer）、审校（→ textbook-reviewer）。

**③ 审校标准的母本比副本旧。** `规范库/审校标准.md` 停在 v1.0，而 `textbook-reviewer/references/` 里是 v1.1——副本多出「只能人工判的项」整节。照 README 的同步命令执行一次，这节会被静默覆盖。现已以副本为准合回母本（v1.1），并修掉副本里两个「## 五」的编号撞车。

## 其余修改

| 类型 | 内容 |
|---|---|
| 规则同步 | `unit-writer` 步骤 3 还写着「用『然而』把好处翻成麻烦」，而 TY-06 在 v1.1.4 已改为「反转出问题」——同步，并指向三种合法形态 |
| 规则空转 | `语言风格.md` 有三份副本，但**没有任何 SKILL.md 提到它**；而脚本会按其中的禁用词表报 ERROR。已在 unit-writer / reviewer / material-creator 三处补引用 |
| 死引用 | `exercise-designer` 指向不存在的 `assets/习题模板.md`——新增该模板（空骨架 + 出题自检清单） |
| 术语 | 「单元/课」（写作）与「章/节」（排版）没有对照，formatter 全篇用「章」。体例规范加一句：**单元 = 章，课 = 节**（v1.4 → v1.5） |
| 命名 | 产物命名统一为 `<course-slug>-` 前缀，`exercise-designer` 补上原先缺失的文件名规则 |
| 兜底参数 | 删掉 `outline-designer` 复制的那份学段参数表（该节自己写着「只保留指向，不再复制数值」），改为「缺文件就停下来报告，别用估算值兜底」——兜底会把「缺文件」变成静默的数字漂移 |

## 新增两个工具

**`tools/consistency_check.py`** —— 零依赖，检查六件事，任一 ERROR 非零退出：

1. 各 `references/*.md` 与 `规范库/` 同名文件 md5 一致
2. `SKILL.md` 里 `references/` `assets/` `scripts/` 的引用路径全部存在
3. `check_draft.py` 的学段区间能在规范库里找到出处
4. 九份 `SKILL.md` 都含基础六节（跳过代码围栏内的示例标题）
5. 执行步骤编号连续
6. 每份 `description` 都带边界声明

写它的时候它立刻抓到一个假引用——路径说明里写了 `scripts/x.py`，被当成真实文件。这类检查值得存在的理由就在这。

**`tools/pack.py`** —— 打包从临时操作变成可复现脚本，排除清单（版权图书、盲评密封件）写进代码，打完自检。

## 校验

- `consistency_check.py`：0 ERROR / 0 WARN
- 触发测试 9 skill × 20 用例：漏判 0 / 误判 0
- 范文 0/0、T-03 0/0、T-06 问题稿 17 ERROR / 4 WARN、大纲 0/0 —— 与 v1.1.7 完全一致，**说明这轮只改关系、没动判定**

## 交付包

80 个文件（skills 47 / docs 22 / 规范库 5 / meta 3 / tools 3），332,916 bytes。

```bash
# 校验下载完整性
python -c "import hashlib;print(hashlib.sha256(open('textbook-skills-v1.2.0.zip','rb').read()).hexdigest())"
# 期望：62aed3ee4f9ca5ff7eb469bd8f15d2385c37da145da7c7e90e4ede80fdf76ba4
```

## 升级方式

覆盖 `skills/` 下 9 个目录即可，无需迁移数据。用链接安装的，`git pull` 后即生效——但**注意重跑一次** `python tools/consistency_check.py`，确认副本没有因为之前的同步回退。

## 同系列其他版本

v1.1.2 起七个版本都有 Release 和附件，完整索引见 [README 的「版本历史」](https://github.com/hcming2026/textbook-writing-skills#版本历史)。

**除本版外都是历史版本**——v1.1.3–v1.1.7 都早于本版的三项 P0 修复，装上后脚本命令可能直接报 `No such file or directory`。

> v1.1.3 的附件是重制包（70 文件 / 209,807 bytes）。原归档包 71 文件，其中一个 `docs/盲评包/_映射-密封勿发.md` 是盲评 A/B 组对应表，文件首行自述「不得发给评审教师」，打包时误入。重制只剔除该文件，其余 70 项逐字节未变。
