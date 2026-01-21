# Manga Production - 镜头与视频

本文件包含 AI 漫剧生成的阶段 2（镜头图片生成）和阶段 3（视频生成）。

---

## 阶段 2：镜头图片生成

**前置条件**: 阶段 1.5 审核通过

当用户说「继续阶段2」或「帮我生成图片」时执行。

### 步骤 2.1: 生成镜头图片

执行以下命令：

```bash
python .claude/scripts/manga_generate_images.py
```

脚本会：
- 读取 screenplay.json
- 使用场景背景图 + 角色阶段参考图生成镜头
- 默认启用链式参考（每个镜头参考前一个镜头的图片）
- 保存到 output/故事标题/shot_场景ID_镜头ID.png
- 更新 screenplay.json 中的 image_path

**参数说明:**
- `--no-chain`: 禁用链式参考
- `--force`: 强制重新生成所有图片
- `--location N`: 只生成指定场景的镜头图片
- `--aspect-ratio`: 覆盖画面比例
- `--style`: 覆盖风格关键词

### 步骤 2.2: 人工审核提示

生成完成后，向用户显示：

```
✅ 阶段 2 完成！

已生成镜头图片:
- output/故事标题/shot_1_1.png
- output/故事标题/shot_1_2.png
- ...

📋 请审核图片效果:

1. 查看所有图片:
   - macOS: open output/故事标题/

2. 如某个镜头不满意:
   - 删除对应的 shot_X_X.png
   - 说"重新生成图片"会只生成缺失的镜头

3. 检查角色一致性:
   - 对比各镜头中的角色外观是否与对应阶段一致

审核完成后，说"继续阶段3"开始生成视频。
```

---

## 阶段 3：视频生成

**前置条件**: 阶段 2 审核通过

当用户说「继续阶段3」或「帮我生成视频」时执行。

### 步骤 3.1: 生成镜头视频

执行以下命令：

```bash
python .claude/scripts/manga_generate_videos.py --duration 3
```

**参数说明:**
- `--duration 3`: 每个视频时长 3 秒（范围 2-8 秒，建议 2-4 秒）

脚本会：
- 读取 screenplay.json
- 使用镜头图片作为视频起始帧
- 为每个镜头生成指定时长的视频
- 保存到 output/故事标题/shot_X_X.mp4
- 更新 screenplay.json 中的 video_path

### 步骤 3.2: 合并视频（可选）

如果用户需要合并视频：

1. 首先检查 ffmpeg 是否安装：
```bash
ffmpeg -version
```

2. 如果 ffmpeg 已安装，执行合并脚本：
```bash
# 使用交叉淡入淡出转场（推荐）
python .claude/scripts/manga_concat.py --transition crossfade --transition-duration 0.5

# 或无转场（直接拼接）
python .claude/scripts/manga_concat.py --transition none
```

**转场效果说明:**
- `crossfade`: 交叉淡入淡出，前一场景淡出同时后一场景淡入（推荐）
- `fade`: 淡入淡出到黑色
- `none`: 无转场，直接拼接

3. 如果 ffmpeg 未安装，提示用户安装：
```
ffmpeg 未安装，请先安装：
- macOS: brew install ffmpeg
- Linux: apt install ffmpeg
- Windows: https://ffmpeg.org/download.html
```

### 步骤 3.3: 完成提示

生成完成后，向用户显示：

```
🎉 漫剧生成完成！

输出文件:
- 项目引用: screenplay.json (指向项目目录)
- 剧本: output/故事标题/screenplay.json
- 角色阶段参考图: output/故事标题/char_角色名_phase_XX.png
- 场景背景图: output/故事标题/loc_XX_bg.png
- 镜头图片: output/故事标题/shot_X_X.png
- 镜头视频: output/故事标题/shot_X_X.mp4
- 合并视频: output/故事标题/故事标题_时间戳.mp4 (如已合并)

感谢使用 AI 漫剧生成器！
```
