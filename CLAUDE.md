# Manga Workflow

AI 漫剧生成工作流 - 将创意描述转换为 AI 漫剧短视频。

## 快速开始

### 前置条件

```bash
# 安装依赖
pip install google-genai pillow

# 设置 API Key
export GEMINI_API_KEY="your-api-key"

# 安装 ffmpeg (用于视频合并)
brew install ffmpeg
```

获取 API Key: https://aistudio.google.com/apikey

### 使用方法

```bash
# 启动创作流程
/manga "你的创意描述"
```

## 工作流程

```
阶段 0: 故事创作
    ↓ 生成完整剧情（起承转合、人物发展）
    ↓ 定义角色阶段（phases）和场景/地点（locations）
    ↓ 定义角色锚定特征（anchor_features）
[人工审核] ← 审核故事逻辑
    ↓
阶段 0.5: 分镜规划
    ↓ 按场景分组镜头
    ↓ 每个场景 2-4 个镜头
    ↓ 自动注入角色锚定特征到 image_prompt
[人工审核] ← 审核分镜内容
    ↓
阶段 1: 角色阶段参考图生成
    ↓ 为每个角色阶段生成三视图参考图
    ↓ 使用锚定特征增强生成
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

## 指令路由

| 用户指令 | 操作 |
|---------|------|
| `/manga "描述"` | 开始阶段 0 |
| "继续阶段0.5" | 执行阶段 0.5 |
| "继续阶段1" | 执行阶段 1 |
| "继续阶段1.5" | 执行阶段 1.5 |
| "继续阶段2" | 执行阶段 2 |
| "继续阶段3" | 执行阶段 3 |
| "验证剧本" | 验证剧本一致性 |
| "帮我一键生成" | 自动执行所有生成步骤 |

## 文件结构

```
.claude/
├── commands/manga/
│   ├── manga.md      # 主入口、指令路由
│   ├── story.md      # 阶段 0, 0.5 - 故事和分镜
│   ├── assets.md     # 阶段 1, 1.5 - 角色和背景
│   ├── production.md # 阶段 2, 3 - 镜头和视频
│   └── reference.md  # 创作指南、最佳实践
└── scripts/
    ├── manga_common.py            # 共享模块
    ├── manga_create_story.py      # 故事大纲创建
    ├── manga_create_shots.py      # 分镜创建
    ├── manga_generate_turnaround.py # 基础三视图
    ├── manga_generate_phases.py   # 角色阶段参考图
    ├── manga_generate_backgrounds.py # 场景背景
    ├── manga_generate_images.py   # 镜头图片
    ├── manga_generate_videos.py   # 视频生成
    ├── manga_concat.py            # 视频合并
    └── manga_validate.py          # 剧本验证
```

## 角色一致性机制

采用双重机制保障角色一致性：

1. **视觉参考（主要）**
   - 角色三视图 (character_turnaround.png)
   - 阶段参考图 (char_角色名_phase_XX.png)
   - 作为 image-to-image 的参考输入

2. **锚定特征（辅助）**
   - `anchor_features` 字段定义角色核心特征
   - 增强 Prompt 的文字描述
   - 帮助 AI 理解角色关键特征

## 输出目录

生成的文件保存在 `output/故事标题/` 目录下：

```
output/故事标题/
├── story_outline.json     # 故事大纲
├── screenplay.json        # 完整剧本
├── character_turnaround.png # 基础三视图
├── char_角色名_phase_01.png # 阶段参考图
├── loc_01_bg.png          # 场景背景
├── shot_1_1.png           # 镜头图片
├── shot_1_1.mp4           # 镜头视频
└── final.mp4              # 最终合成视频
```
