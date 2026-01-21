# Manga Skill - AI 漫剧生成

将用户的创意描述转换为 AI 漫剧，采用分阶段生成 + 人工审核机制。

## 工作流程概览

```
阶段 0: 故事创作
    ↓ 生成完整剧情（起承转合、人物发展）
    ↓ 定义角色阶段（phases）和场景/地点（locations）
[人工审核] ← 审核故事逻辑
    ↓
阶段 0.5: 分镜规划
    ↓ 按场景分组镜头
    ↓ 每个场景 2-4 个镜头
[人工审核] ← 审核分镜内容
    ↓
阶段 1: 角色阶段参考图生成
    ↓ 为每个角色阶段生成参考图
[人工审核] ← 审核角色各阶段外观
    ↓
阶段 1.5: 场景背景生成
    ↓ 为每个场景生成纯背景图（无人物）
[人工审核] ← 审核背景图风格一致性
    ↓
阶段 2: 镜头生成
    ↓ 使用场景背景 + 角色阶段参考图生成镜头
[人工审核] ← 审核镜头图片效果
    ↓
阶段 3: 视频生成
    ↓
完成
```

## 文件组织

所有文件位于 `.claude/commands/manga/` 目录：

| 文件 | 内容 | 阶段 |
|------|------|------|
| `manga.md` | 主入口、路由、辅助操作 | - |
| `story.md` | 故事创作、分镜规划 | 0, 0.5 |
| `assets.md` | 角色参考图、场景背景 | 1, 1.5 |
| `production.md` | 镜头图片、视频生成 | 2, 3 |
| `reference.md` | 创作指南、脚本说明 | - |

---

## 指令入口

当用户调用 `/manga "创意描述"` 时：

1. **读取** `.claude/commands/manga/story.md` 获取阶段 0 的详细指令
2. **执行阶段 0**：根据用户描述生成故事大纲

---

## 指令路由

根据用户指令加载对应文件（相对于 `.claude/commands/manga/`）：

| 用户指令 | 操作 |
|---------|------|
| `/manga "描述"` | 读取 `story.md`，执行阶段 0 |
| "继续阶段0.5" | 读取 `story.md`，执行阶段 0.5 |
| "继续阶段1" | 读取 `assets.md`，执行阶段 1 |
| "继续阶段1.5" | 读取 `assets.md`，执行阶段 1.5 |
| "继续阶段2" | 读取 `production.md`，执行阶段 2 |
| "继续阶段3" | 读取 `production.md`，执行阶段 3 |

**重要**: 执行任何阶段前，必须先读取对应文件以获取详细指令。

---

## 辅助操作指令

### 重新生成角色阶段参考图

当用户说「重新生成阶段 X」时：

```bash
python .claude/scripts/manga_generate_phases.py --phase X --force
```

### 重新生成场景背景

当用户说「重新生成场景 X 背景」时：

```bash
python .claude/scripts/manga_generate_backgrounds.py --location X --force
```

### 重新生成镜头图片

当用户说「重新生成图片」时：

执行图片生成脚本（会自动跳过已存在的图片）：
```bash
python .claude/scripts/manga_generate_images.py
```

### 重新生成指定场景的镜头

当用户说「重新生成场景 X 的镜头」时：

```bash
python .claude/scripts/manga_generate_images.py --location X --force
```

### 一键生成

当用户说「帮我一键生成」时：

按顺序执行所有步骤：
1. 生成角色阶段参考图: `python .claude/scripts/manga_generate_phases.py`
2. 生成场景背景: `python .claude/scripts/manga_generate_backgrounds.py`
3. 生成镜头图片: `python .claude/scripts/manga_generate_images.py`
4. 生成视频: `python .claude/scripts/manga_generate_videos.py --duration 3`
5. 合并视频: `python .claude/scripts/manga_concat.py --transition crossfade`

每个步骤完成后报告进度。

### 验证剧本

当用户说「验证剧本」或「validate」时：

```bash
python .claude/scripts/manga_validate.py
```

验证脚本检查：
- 角色锚定特征一致性（anchor_features 是否定义、是否在 prompt 中使用）
- 叙事节奏变化（镜头时长、构图多样性）
- Prompt 格式规范（image_prompt 以 anime style 开头、video_prompt 包含 Camera Type）
- 旁白质量（避免过于描述性的旁白）

验证完成后显示错误和警告，帮助优化剧本质量。

---

## 前置条件

- 安装依赖: `pip install google-genai pillow`
- 设置 API Key: `export GEMINI_API_KEY="your-api-key"`
- 安装 ffmpeg (用于视频合并): `brew install ffmpeg`

获取 API Key: https://aistudio.google.com/apikey

---

## 快速参考

需要查看创作指南或脚本参数时，读取 `reference.md`。
