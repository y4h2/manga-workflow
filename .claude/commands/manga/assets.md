# Manga Assets - 资产生成

本文件包含 AI 漫剧生成的资产生成阶段：
- 阶段 0.8：世界地图生成
- 阶段 0.9：区域地图生成
- 阶段 1：角色阶段参考图生成
- 阶段 1.5：场景背景生成

---

## 阶段 0.8：世界地图生成 (可选)

**前置条件**: 阶段 0.5 审核通过，且 `story_outline.json` 包含 `world_map` 定义

### 步骤 0.8.1: 生成世界地图

执行以下命令：

```bash
python .claude/scripts/manga_generate_world_map.py
```

脚本会：
- 读取 story_outline.json 中的 world_map 定义
- 生成鸟瞰俯视风格的世界地图
- 展示整体地形布局和区域分布
- 保存到 output/故事标题/world_map.png
- 更新 story_outline.json 中的 world_map_image 字段

**参数说明:**
- `--force`: 强制重新生成世界地图

### 步骤 0.8.2: 人工审核提示

生成完成后，向用户显示：

```
✅ 阶段 0.8 完成！

已生成:
- 世界地图: output/故事标题/world_map.png

📋 请审核世界地图:

1. 布局合理性:
   - 检查区域分布是否符合故事设定
   - 检查地形特征是否正确

2. 风格基调:
   - 检查色调是否符合 style_base 定义
   - 确认整体氛围是否正确

3. 如不满意:
   - 删除文件后说"重新生成世界地图"

审核完成后，说"继续阶段0.9"开始生成区域地图。
```

---

## 阶段 0.9：区域地图生成 (可选)

**前置条件**: 阶段 0.8 审核通过（或跳过），且 `story_outline.json` 包含 `regions` 定义

### 步骤 0.9.1: 生成区域地图

执行以下命令：

```bash
python .claude/scripts/manga_generate_region_maps.py
```

脚本会：
- 读取 story_outline.json 中的 regions 定义
- 使用世界地图作为风格参考（如果存在）
- 为每个区域生成艺术概念风格的地图
- 保存到 output/故事标题/region_XX_map.png
- 更新 story_outline.json 中的 region_map_image 字段

**参数说明:**
- `--force`: 强制重新生成所有区域地图
- `--region N`: 只生成指定区域的地图

### 步骤 0.9.2: 人工审核提示

生成完成后，向用户显示：

```
✅ 阶段 0.9 完成！

已生成:
- 区域地图:
  - output/故事标题/region_01_map.png (荒岛)

📋 请审核区域地图:

1. 风格一致性:
   - 检查各区域地图是否与世界地图风格一致
   - 检查色调是否符合 style_modifiers 定义

2. 区域特征:
   - 检查区域独特特征是否正确呈现
   - 确认地理元素是否正确

3. 如某区域不满意:
   - 删除对应文件后说"重新生成区域 X 地图"

审核完成后，说"继续阶段1"开始生成角色阶段参考图。
```

---

## 阶段 1：角色阶段参考图生成

**前置条件**: 阶段 0.5 审核通过

### 步骤 1.1: 生成角色阶段参考图

执行以下命令：

```bash
python .claude/scripts/manga_generate_phases.py
```

脚本会：
- 读取 screenplay.json 中的 character_phases
- 为每个角色阶段生成三视图风格的参考图
- 保存到 output/故事标题/char_角色名_phase_XX.png
- 更新 screenplay.json 中的 reference_image 字段

**参数说明:**
- `--force`: 强制重新生成所有参考图
- `--phase N`: 只生成指定阶段的参考图

### 步骤 1.2: 人工审核提示

生成完成后，向用户显示：

```
✅ 阶段 1 完成！

已生成:
- 角色阶段参考图:
  - output/故事标题/char_林晓_phase_01.png (初始状态)
  - output/故事标题/char_林晓_phase_02.png (求生中期)
  - output/故事标题/char_林晓_phase_03.png (后期)

📋 请审核各阶段参考图:

1. 角色外观演变:
   - 检查各阶段外观是否符合剧情发展
   - 检查衣物、头发、皮肤状态的变化

2. 如某阶段不满意:
   - 删除对应文件后说"重新生成阶段 X"

审核完成后，说"继续阶段1.5"开始生成场景背景。
```

---

## 阶段 1.5：场景背景生成

**前置条件**: 阶段 1 审核通过

### 步骤 1.5.1: 生成场景背景图

执行以下命令：

```bash
python .claude/scripts/manga_generate_backgrounds.py
```

脚本会：
- 读取 screenplay.json 中的 locations
- **如果存在区域地图**：使用区域地图作为风格参考
- **风格继承**：自动继承 world_map → region → location 的风格链
- 为每个场景生成纯背景图（无人物）
- 保存到 output/故事标题/loc_XX_bg.png
- 更新 screenplay.json 中的 background_image 字段

**参数说明:**
- `--force`: 强制重新生成所有背景图
- `--location N`: 只生成指定场景的背景图
- `--no-reference`: 不使用区域地图作为参考（独立生成）

### 风格参考链

如果使用了分层地图系统，背景生成时会自动使用参考图片：

```
1. 区域地图 (region_map_image)
   ↓ 作为风格参考
2. 同区域前一个场景的背景图
   ↓ 作为一致性参考
3. 生成当前场景背景
```

这确保了同一区域内的所有场景保持视觉一致性。

### 步骤 1.5.2: 人工审核提示

生成完成后，向用户显示：

```
✅ 阶段 1.5 完成！

已生成:
- 场景背景图:
  - output/故事标题/loc_01_bg.png (暴风雨海面) [区域 1]
  - output/故事标题/loc_02_bg.png (荒岛沙滩) [区域 1]
  - output/故事标题/loc_03_bg.png (丛林深处) [区域 1]

📋 请审核背景图:

1. 风格一致性:
   - 检查同一区域内的背景图色调和风格是否统一
   - 检查是否与区域地图的视觉基调一致
   - 确保没有意外出现人物

2. 如某场景不满意:
   - 删除对应文件后说"重新生成场景 X 背景"

审核完成后，说"继续阶段2"开始生成镜头图片。
```

---

## 高级功能：分层背景生成

分层背景系统支持生成具有景深层次的背景，可用于视差滚动效果。

### 方案概览

| 方案 | 脚本 | 复杂度 | 效果 | 依赖 |
|------|------|--------|------|------|
| **C1** | `--depth-enhanced` | 低 | 单图，自然层次感 | 无额外依赖 |
| **C2** | `layered_background_c2.py` | 中高 | 自动深度分层 | torch, transformers |
| **C4** | `layered_background_c4.py` | 中 | 真正三层分离 | rembg, onnxruntime |

### 方案 C1: 深度感知单图（推荐入门）

通过增强 prompt 生成具有自然景深的单张背景图，无需额外依赖。

```bash
python .claude/scripts/manga_generate_backgrounds.py --depth-enhanced
```

生成的背景图会有明显的景深层次：
- 前景（15%）: 高细节，暖色调，轻微模糊
- 中景（60%）: 锐利细节，主要视觉焦点
- 背景（25%）: 大气透视，冷色调，雾化效果

### 方案 C2: 深度估计自动分层

使用 MiDaS 深度估计模型将已有背景图自动分割为多层。

```bash
# 安装依赖
pip install torch transformers scipy

# 运行分层提取
python solutions/layered_background_c2.py --location 1
```

输出文件：
- `loc_01_depth.png` - 深度图
- `loc_01_far.png` - 远景层（透明）
- `loc_01_mid.png` - 中景层（透明）
- `loc_01_near.png` - 近景层（透明）

### 方案 C4: Rembg 背景移除分层

分别生成三层场景元素（在绿色背景上），然后用 rembg 去除背景。

```bash
# 安装依赖
pip install rembg onnxruntime

# 生成分层背景
python solutions/layered_background_c4.py --location 1
```

这种方法生成真正分离的三层，每层都可以独立控制。

### 视差滚动视频

使用分层背景创建视差滚动效果的视频。

```bash
# 确保已安装 ffmpeg
brew install ffmpeg  # macOS

# 生成视差视频
python solutions/parallax_video.py --location 1 --duration 5 --direction right
```

参数说明：
- `--location N`: 场景 ID（必需）
- `--duration N`: 视频时长秒数（默认 5）
- `--direction`: 滚动方向 left/right（默认 right）
- `--simple`: 使用简化版视差效果

视差速度配置（内置）：
- 远景: 20 px/s
- 中景: 60 px/s
- 近景: 120 px/s

### 数据结构扩展

使用分层背景后，`screenplay.json` 中的 location 会包含额外字段：

```json
{
    "location_id": 1,
    "name": "海岸悬崖",
    "background_image": "output/xxx/loc_01_bg.png",
    "depth_enhanced": true,
    "depth_layers": {
        "enabled": true,
        "far_layer": "output/xxx/loc_01_far.png",
        "mid_layer": "output/xxx/loc_01_mid.png",
        "near_layer": "output/xxx/loc_01_near.png"
    }
}
```

### 使用建议

1. **快速开始**: 使用 `--depth-enhanced` 参数，无需额外安装
2. **需要视差效果**: 使用方案 C2 或 C4 生成真正的分层
3. **风格一致性**: 分层生成时会自动继承区域风格
