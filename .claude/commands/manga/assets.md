# Manga Assets - 资产生成

本文件包含 AI 漫剧生成的阶段 1（角色阶段参考图生成）和阶段 1.5（场景背景生成）。

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
- 为每个场景生成纯背景图（无人物）
- 保存到 output/故事标题/loc_XX_bg.png
- 更新 screenplay.json 中的 background_image 字段

**参数说明:**
- `--force`: 强制重新生成所有背景图
- `--location N`: 只生成指定场景的背景图

### 步骤 1.5.2: 人工审核提示

生成完成后，向用户显示：

```
✅ 阶段 1.5 完成！

已生成:
- 场景背景图:
  - output/故事标题/loc_01_bg.png (暴风雨海面)
  - output/故事标题/loc_02_bg.png (荒岛沙滩)
  - output/故事标题/loc_03_bg.png (丛林深处)

📋 请审核背景图:

1. 风格一致性:
   - 检查所有背景图的色调和风格是否统一
   - 确保没有意外出现人物

2. 如某场景不满意:
   - 删除对应文件后说"重新生成场景 X 背景"

审核完成后，说"继续阶段2"开始生成镜头图片。
```
