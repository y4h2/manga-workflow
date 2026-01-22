# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI 漫剧生成工作流 - 将创意描述转换为 AI 漫剧短视频。使用 Gemini API 进行图片和视频生成。

## Setup

```bash
pip install google-genai pillow
export GEMINI_API_KEY="your-api-key"
brew install ffmpeg  # for video concatenation
```

## Main Entry Point

使用 `/manga "创意描述"` 启动创作流程。这会触发 `.claude/commands/manga/manga.md` 中定义的工作流。

## Architecture

### 阶段化工作流

项目采用分阶段生成 + 人工审核机制：

```
阶段 0   → 故事创作 (story_outline.json)
阶段 0.5 → 分镜规划 (screenplay.json)
阶段 0.8 → 世界地图生成 (可选)
阶段 0.9 → 区域地图生成 (可选)
阶段 1   → 角色阶段参考图
阶段 1.5 → 场景背景图
阶段 2   → 镜头图片
阶段 3   → 视频生成 + 合并
```

### 指令路由

| 用户指令 | 加载文件 | 操作 |
|---------|---------|------|
| `/manga "描述"` | story.md | 阶段 0 |
| "继续阶段0.5" | story.md | 阶段 0.5 |
| "继续阶段0.8-1.5" | assets.md | 资产生成 |
| "继续阶段2-3" | production.md | 镜头和视频 |

### 核心脚本

所有脚本位于 `.claude/scripts/`：

| 脚本 | 用途 | 输入 |
|------|------|------|
| `manga_create_story.py` | 故事大纲写入 | stdin (JSON) |
| `manga_create_shots.py` | 分镜写入（含时长估算）| stdin (JSON) |
| `manga_generate_world_map.py` | 世界地图 | story_outline.json |
| `manga_generate_region_maps.py` | 区域地图 | story_outline.json |
| `manga_generate_phases.py` | 角色阶段参考图 | screenplay.json |
| `manga_generate_backgrounds.py` | 场景背景 | screenplay.json |
| `manga_generate_images.py` | 镜头图片 | screenplay.json |
| `manga_generate_videos.py` | 镜头视频 | screenplay.json |
| `manga_generate_narration.py` | **配音生成（含清单）**| screenplay.json |
| `manga_sync_video.py` | **音视频同步幻灯片**| screenplay.json + audio_manifest.json |
| `manga_concat.py` | 视频合并 | screenplay.json |
| `manga_validate.py` | 剧本验证 | screenplay.json |

### 共享模块 (manga_common.py)

包含所有脚本共用的：
- 模型配置 (`IMAGE_MODEL`, `VIDEO_MODEL`)
- 路径函数 (`get_screenplay_path()`, `get_output_dir_from_screenplay()`)
- 角色/场景辅助函数
- 分层地图风格继承函数 (`build_inherited_style()`)
- 剧本验证函数
- **配音时长估算函数**:
  - `estimate_duration(text, rate)` - 根据文字长度估算配音时长
  - `remove_rhythm_markers(text)` - 移除节奏标记
  - `sum_pause_markers(text)` - 计算停顿时长
  - `parse_rate_factor(rate)` - 解析语速参数
  - `get_mood_params(mood)` - 获取情绪对应的语速/音调

## 数据结构

### story_outline.json

故事层数据：
- `world_map` - 世界地图定义（可选）
- `regions` - 区域列表（可选）
- `characters` - 角色定义（含 `anchor_features` 和 `phases`）
- `locations` - 场景/地点列表
- `story_beats` - 故事节拍（含 `intensity` 0-1）

### screenplay.json

合并故事+分镜数据：
- `locations[].shots[]` - 每个场景的镜头列表
- `character_phases[]` - 角色阶段参考图信息
- 每个 shot 包含: `image_prompt`, `video_prompt`, `narration`, `mood`, `speaker`

**时长相关字段（估算优先工作流）**:
- `estimated_duration` - 根据文字长度估算的配音时长
- `actual_duration` - 实际配音时长（配音后填充）
- `display_duration` - 最终显示时长（用于视频生成）

**旁白组字段（多图共享旁白）**:
- `narration_group` - 旁白组 ID
- `group_position` - 组内位置
- `group_total` - 组内总数

### audio_manifest.json

配音清单（位于 `output/故事标题/audio/`）：
- `generated_at` - 生成时间
- `total_duration` - 总时长
- `entries[]` - 音频条目列表
  - `type: "single"` - 独立旁白
  - `type: "group"` - 旁白组（多图共享）

### 项目引用机制

根目录 `screenplay.json` 可能是项目引用：
```json
{"project_path": "output/故事标题", "title": "..."}
```
实际剧本在 `output/故事标题/screenplay.json`。`get_screenplay_path()` 自动处理此逻辑。

## 关键概念

### 角色一致性双重机制

1. **视觉参考（主要）**: 阶段参考图作为 image-to-image 输入
2. **锚定特征（辅助）**: `anchor_features` 增强 Prompt 文字描述

### 分层地图风格继承

```
World (style_base) → Region (style_modifiers) → Location (local_features)
```

同一区域内的场景自动继承统一视觉风格。

### 节奏控制

根据 `intensity` 字段动态调整：
- 0.0-0.4 (slow): 2-3 镜头, 3-4秒/镜头
- 0.4-0.7 (moderate): 3-4 镜头, 2-3秒/镜头
- 0.7-1.0 (fast): 4-6 镜头, 1-2秒/镜头

### 估算优先工作流（音画同步）

实现精确的音画同步：

```
阶段 A: 估算（分镜创建时自动计算）
  ↓ 根据旁白文字长度估算配音时长
阶段 B: 配音生成
  ↓ 生成配音 → 记录实际时长 → 输出 audio_manifest.json
阶段 C: 校验调整
  ↓ 比对估算 vs 实际 → 如偏差 > 20% → 给出警告
阶段 D: 视频生成
  使用 display_duration 生成幻灯片 → 合并音频 → 生成字幕
```

**估算公式**: `时长 = 字符数 × 0.28秒 × 语速系数 + 停顿时长`

### 旁白组（多图共享旁白）

快节奏场景支持多张图片共用一段旁白：

```json
{
  "shot_id": "4-3",
  "narration": "快跑！皮卡丘！",
  "narration_group": "chase_1",
  "group_position": 1,
  "group_total": 2
}
```

配音时只生成一个音频文件，时长平均分配给组内所有镜头。

## 常用命令

```bash
# 写入故事大纲
echo '<JSON>' | python .claude/scripts/manga_create_story.py

# 写入分镜（自动估算配音时长）
echo '<JSON>' | python .claude/scripts/manga_create_shots.py

# 生成资产（按顺序）
python .claude/scripts/manga_generate_world_map.py
python .claude/scripts/manga_generate_region_maps.py
python .claude/scripts/manga_generate_phases.py
python .claude/scripts/manga_generate_backgrounds.py

# 生成镜头和视频
python .claude/scripts/manga_generate_images.py
python .claude/scripts/manga_generate_videos.py --duration 3

# 生成配音（带清单）
python .claude/scripts/manga_generate_narration.py output/故事标题

# 生成同步视频（使用 audio_manifest.json）
python .claude/scripts/manga_sync_video.py output/故事标题

# 合并视频
python .claude/scripts/manga_concat.py --transition crossfade

# 验证剧本
python .claude/scripts/manga_validate.py

# 重新生成特定内容
python .claude/scripts/manga_generate_phases.py --phase 2 --force
python .claude/scripts/manga_generate_backgrounds.py --location 1 --force
python .claude/scripts/manga_generate_images.py --location 1 --force
```

## 输出目录结构

```
output/故事标题/
├── story_outline.json
├── screenplay.json
├── world_map.png              # 阶段 0.8
├── region_01_map.png          # 阶段 0.9
├── char_角色名_phase_01.png   # 阶段 1
├── loc_01_bg.png              # 阶段 1.5
├── shot_1_1.png               # 阶段 2
├── shot_1_1.mp4               # 阶段 3
├── audio/                     # 配音目录
│   ├── audio_manifest.json    # 音频清单（含时长信息）
│   ├── narration_1-1.mp3      # 独立旁白
│   └── narration_group_*.mp3  # 组旁白
├── *_同步版.mp4               # 音画同步版本
├── *_最终版.mp4               # 带字幕最终版
└── final.mp4                  # 合并视频
```

## Prompt 规范

- `image_prompt` 必须以 "anime style" 开头
- `video_prompt` 必须包含 `[Camera Type]` 格式
- 每个 shot 需要指定 `mood`（用于语音情绪控制）和 `speaker`（用于多角色配音）
