# Manga Reference - 参考指南

本文件包含 AI 漫剧生成的创作指南和脚本说明。

---

## 剧本创作指南

### 角色阶段设计
- 根据剧情发展定义 2-4 个角色阶段
- 每个阶段使用 `beat_range` 关联到对应的故事节拍
- 外观变化要符合剧情逻辑（如求生故事中衣物逐渐破损）

### 场景/地点设计
- 根据故事需要定义 3-6 个主要场景
- 每个场景包含 2-4 个镜头
- 使用 `time_of_day` 控制光线氛围

### 镜头语言
- Wide shot: 展示环境和角色位置关系
- Medium shot: 日常对话和互动
- Close-up: 表达情绪和细节
- POV shot: 第一人称视角

### 动作描述
- 避免复杂的动作序列
- 每个镜头聚焦一个主要动作
- 使用具体的运动描述（zoom in, pan left, dolly forward）

### 情绪曲线
- 开场：建立世界观和角色
- 发展：引入冲突或转折
- 高潮：情感最强烈的时刻
- 结尾：情感收束或开放式结局

---

## 角色一致性最佳实践

角色一致性依赖**双重机制**：

```
┌─────────────────────────────────────────────────────────────┐
│                    角色一致性保障                            │
├─────────────────────────────────────────────────────────────┤
│  1. 视觉参考（主要）                                         │
│     ├─ 角色三视图 (character_turnaround.png)                │
│     └─ 阶段参考图 (char_角色名_phase_XX.png)                 │
│        → 作为 image-to-image 的参考输入                     │
│                                                             │
│  2. 锚定特征（辅助）                                         │
│     └─ anchor_features 字段                                 │
│        → 增强 Prompt 的文字描述                              │
│        → 帮助 AI 理解角色关键特征                            │
└─────────────────────────────────────────────────────────────┘
```

**重要**：锚定特征是对参考图的补充，不能替代参考图。生成镜头时，必须同时使用：
- 阶段参考图作为视觉输入
- 锚定特征增强的 Prompt 作为文字描述

### Anchor Features 模板

每个主要角色必须定义以下锚定特征（使用英文）：

| 特征类型 | 字段名 | 示例 |
|---------|--------|------|
| 面部特征 | `face` | "oval face, large almond-shaped eyes, small nose, soft lips" |
| 发型描述 | `hair` | "black shoulder-length straight hair" |
| 体型描述 | `body` | "slender build, 165cm height" |
| 独特标识 | `distinguishing` | "small mole below left eye, silver earring" |

### 参考图生成流程

```
阶段 1: manga_generate_phases.py
    ↓ 使用角色 appearance + anchor_features 生成阶段参考图
    ↓ 保存为 char_角色名_phase_XX.png
    ↓ 更新 screenplay.json 中的 reference_image 字段

阶段 2: manga_generate_images.py
    ↓ 加载对应阶段的参考图
    ↓ 使用 anchor_features 增强的 image_prompt
    ↓ 同时传入参考图和 Prompt 生成镜头
```

### Image Prompt 注入规则

1. **首次出场镜头**：完整锚定特征
   ```
   anime style, [composition], young woman (oval face, large almond eyes,
   black shoulder-length hair, small mole below left eye), [action], [environment]
   ```

2. **后续镜头**：引用格式
   ```
   anime style, [composition], the same 林晓 (oval face, black hair, mole),
   [action], [environment]
   ```

3. **同一阶段内**：外观描述保持一致，不随意变换服装或发型

### 锚定特征检查清单

- [ ] 每个主角是否定义了 `anchor_features`？
- [ ] 面部特征是否足够具体（避免泛泛的"漂亮"）？
- [ ] 是否有独特标识便于识别（如痣、疤痕、饰品）？
- [ ] 所有包含角色的 image_prompt 是否包含锚定特征？

---

## 镜头时长建议表

| 场景类型 | 建议时长 | intensity | 构图建议 | 用途 |
|---------|---------|-----------|---------|------|
| 开场/建立 | 3-4秒 | 0.3-0.4 | wide shot, establishing | 交代环境、氛围 |
| 日常/对话 | 2-3秒 | 0.4-0.5 | medium shot, two-shot | 角色互动 |
| 动作/追逐 | 1-2秒 | 0.7-0.9 | tracking, handheld | 紧迫感、动态 |
| 情感高潮 | 2-3秒 | 0.9-1.0 | close-up, extreme close-up | 情绪传达 |
| 转折点 | 1-2秒 | 0.6-0.8 | dutch angle, low angle | 强调关键 |
| 结尾/收束 | 3-4秒 | 0.3-0.5 | wide shot, crane | 情感升华 |

### 时长与强度的关系

```
高强度 (0.8-1.0) → 短时长 (1-2秒) → 快节奏、紧张感
中强度 (0.4-0.7) → 中时长 (2-3秒) → 正常叙事
低强度 (0.1-0.4) → 长时长 (3-4秒) → 慢节奏、沉浸感
```

---

## Prompt 结构化模板

### Image Prompt 结构

```
[style] [composition] [character+anchor] [action] [environment] [lighting] [mood]
```

**完整示例**:
```
anime style, medium shot of young woman (oval face, black shoulder-length hair,
small mole below left eye) standing on beach at sunset, looking at horizon,
golden sunlight backlighting, melancholic atmosphere, film grain texture
```

**各部分说明**:
| 部分 | 必需 | 示例 |
|------|------|------|
| style | ✅ | "anime style" |
| composition | ✅ | "medium shot", "close-up", "wide shot" |
| character+anchor | 角色出现时 | "young woman (oval face, black hair, mole)" |
| action | ✅ | "standing", "running", "looking at camera" |
| environment | ✅ | "on beach", "in forest", "inside room" |
| lighting | 推荐 | "golden sunset", "blue moonlight", "soft daylight" |
| mood | 推荐 | "melancholic", "hopeful", "tense" |

### Video Prompt 结构

```
[Camera Type] [Camera Movement] [Character Action] [Environment Motion]
```

**完整示例**:
```
[Medium shot] [Slow dolly in] Woman turns to look at camera, wind blowing through hair, waves gently lapping shore
```

**Camera Movement 参考**:
| 运动类型 | 适用场景 | 示例 |
|---------|---------|------|
| Static | 对话、特写 | "[Static]" |
| Slow pan left/right | 展示环境 | "[Slow pan right]" |
| Dolly in/out | 情感聚焦 | "[Slow dolly in]" |
| Tracking | 跟随动作 | "[Tracking left]" |
| Crane up/down | 场景过渡 | "[Crane up]" |
| Handheld | 紧张、动作 | "[Handheld shake]" |

---

## 脚本说明

### .claude/scripts/manga_create_story.py (阶段 0)
- 从标准输入读取故事大纲 JSON 数据
- 验证故事结构完整性
- 验证角色定义和阶段
- 验证场景/地点定义
- 自动规范化中文标点符号
- 写入 story_outline.json

### .claude/scripts/manga_create_shots.py (阶段 0.5)
- 从标准输入读取分镜 JSON 数据
- 自动加载对应的 story_outline.json
- 验证分镜结构（locations → shots）
- 验证每个镜头的必需字段
- 合并故事信息和分镜信息
- 自动关联角色阶段
- 写入 screenplay.json

### .claude/scripts/manga_generate_phases.py (阶段 1)
- 读取 screenplay.json 中的 character_phases
- 为每个角色阶段生成三视图风格的参考图
- 保存到 output/故事标题/char_角色名_phase_XX.png
- 更新 screenplay.json 中的 reference_image 字段
- 支持参数:
  - `--force`: 强制重新生成所有参考图
  - `--phase N`: 只生成指定阶段的参考图

### .claude/scripts/manga_generate_backgrounds.py (阶段 1.5)
- 读取 screenplay.json 中的 locations
- 为每个场景生成纯背景图（无人物）
- 保存到 output/故事标题/loc_XX_bg.png
- 更新 screenplay.json 中的 background_image 字段
- 支持参数:
  - `--force`: 强制重新生成所有背景图
  - `--location N`: 只生成指定场景的背景图

### .claude/scripts/manga_generate_images.py (阶段 2)
- 读取 screenplay.json
- 使用场景背景图 + 角色阶段参考图生成镜头
- 默认启用链式参考（每个镜头参考前一帧）
- 场景切换时重置链式参考
- 保存到 output/故事标题/shot_场景ID_镜头ID.png
- 更新 screenplay.json 中的 image_path
- 支持参数:
  - `--no-chain`: 禁用链式参考
  - `--force`: 强制重新生成所有图片
  - `--location N`: 只生成指定场景的镜头图片
  - `--aspect-ratio`: 覆盖画面比例
  - `--style`: 覆盖风格关键词

### .claude/scripts/manga_generate_videos.py (阶段 3)
- 读取 screenplay.json
- 为有图片的镜头调用 Veo 生成视频
- 保存到 output/故事标题/shot_X_X.mp4
- 更新 screenplay.json 中的 video_path
- 支持参数:
  - `--duration`: 视频时长（秒），范围 2-8（默认: 2）
  - `--fps`: 帧率（默认: 24）
  - `--resolution`: 分辨率（默认: 1080p）

### .claude/scripts/manga_concat.py
- 读取 screenplay.json
- 使用 ffmpeg 合并所有视频
- 输出完整漫剧视频到 output/ 目录
- 支持参数:
  - `--transition`: 转场效果 (none/crossfade/fade)，默认 crossfade
  - `--transition-duration`: 转场时长（秒），默认 0.5

### .claude/scripts/manga_validate.py (验证工具)
- 验证剧本一致性和质量
- 检查项目:
  - 角色锚定特征一致性
  - 叙事节奏变化（时长、构图多样性）
  - Prompt 格式规范（anime style 开头、Camera Type 格式）
  - 旁白质量（避免过于描述性）
- 用法: `python .claude/scripts/manga_validate.py [screenplay_path]`
- 如果不提供路径，将从当前目录读取 screenplay.json
