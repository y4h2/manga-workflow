# Manga Story - 故事与分镜

本文件包含 AI 漫剧生成的阶段 0（故事创作）和阶段 0.5（分镜规划）。

---

## 阶段 0：故事创作

### 步骤 0.1: 生成故事大纲

根据用户的创意描述，创建完整的故事大纲。故事大纲只包含叙事内容，不包含视觉提示词。

**故事大纲 JSON 结构 (story_outline.json)**:

```json
{
  "title": "荒岛求生",
  "genre": "生存冒险",
  "style_keywords": "anime style, cinematic lighting, muted color palette, atmospheric, detailed environment",
  "aspect_ratio": "16:9",

  "premise": "一名年轻女子在海难后独自漂流到荒岛，在与自然和孤独的抗争中重新找到生存的意义",

  "characters": [
    {
      "name": "林晓",
      "role": "主角",
      "personality": "坚韧、聪明、内心细腻，面对绝境时展现出惊人的求生意志",
      "appearance": "25岁年轻女性，及肩黑色长发，白色衬衫和卡其色短裤，肤色健康，眼神坚定",
      "anchor_features": {
        "face": "oval face, large almond-shaped eyes, small nose, soft lips",
        "hair": "black shoulder-length straight hair",
        "body": "slender build, 165cm height",
        "distinguishing": "small mole below left eye"
      },
      "phases": [
        {
          "phase_id": 1,
          "name": "初始状态",
          "beat_range": [1, 2],
          "appearance": "白色衬衫完整，卡其短裤，及肩黑发湿透贴脸，健康肤色"
        },
        {
          "phase_id": 2,
          "name": "求生中期",
          "beat_range": [3, 10],
          "appearance": "衬衫破损沾满沙土，头发凌乱用藤蔓扎起，皮肤晒红，眼神疲惫但坚定"
        },
        {
          "phase_id": 3,
          "name": "后期",
          "beat_range": [11, 14],
          "appearance": "衣服非常破旧风化，皮肤晒黑，头发用藤蔓扎起，眼神充满希望"
        }
      ]
    }
  ],

  "locations": [
    {
      "location_id": 1,
      "name": "暴风雨海面",
      "time_of_day": "night",
      "description": "夜晚的暴风雨大海，乌云密布，闪电，巨浪",
      "beats": [1, 2]
    },
    {
      "location_id": 2,
      "name": "荒岛沙滩",
      "time_of_day": "morning",
      "description": "热带岛屿沙滩，金色沙子，椰子树，碧蓝大海",
      "beats": [3, 4, 9]
    },
    {
      "location_id": 3,
      "name": "丛林深处",
      "time_of_day": "afternoon",
      "description": "茂密的热带丛林，高大的树木，藤蔓，斑驳的阳光",
      "beats": [5, 6, 7]
    }
  ],

  "narrative_arc": {
    "setup": "暴风雨中的游轮失事，林晓在黑暗的海水中挣扎求生",
    "inciting_incident": "林晓被海浪冲上荒岛沙滩，醒来后发现自己身处一座与世隔绝的小岛",
    "rising_action": "林晓开始艰难的求生之旅：探索环境、寻找淡水、搭建庇护所",
    "climax": "在濒临绝望的边缘，林晓发现了一艘破旧但可以修复的小木船",
    "resolution": "林晓修复小船，在黎明时分独自驶向大海"
  },

  "story_beats": [
    {
      "beat_id": 1,
      "beat_type": "setup",
      "intensity": 0.7,
      "suggested_duration": 3,
      "narration": "那天晚上的海面本来很平静……暴风雨来得那么突然。",
      "description": "夜晚的大海，乌云密布，闪电划破天空",
      "mood": "tense",
      "location": "暴风雨中的夜海",
      "characters_involved": ["林晓"]
    }
  ]
}
```

**字段说明**:

| 字段 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `title` | 顶层 | string | 故事标题 |
| `genre` | 顶层 | string | 故事类型（校园、奇幻、末日等）|
| `premise` | 顶层 | string | 一句话概括故事核心 |
| `characters` | 顶层 | array | 角色列表 |
| `locations` | 顶层 | array | 场景/地点列表 |
| `narrative_arc` | 顶层 | object | 五段式叙事结构 |
| `story_beats` | 顶层 | array | 故事节拍列表 |

**角色字段**:

| 字段 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `name` | character | string | 角色名称 |
| `role` | character | string | 角色定位（主角/配角/反派）|
| `personality` | character | string | 性格描述 |
| `appearance` | character | string | 基本外观描述 |
| `anchor_features` | character | object | **锚定特征**（确保角色一致性的关键特征）|
| `anchor_features.face` | character | string | 脸型、眼睛、鼻子、嘴巴特征 |
| `anchor_features.hair` | character | string | 发色、发型、长度 |
| `anchor_features.body` | character | string | 体型、身高 |
| `anchor_features.distinguishing` | character | string | 标识性特征（痣、疤痕等）|
| `phases` | character | array | 角色阶段列表 |
| `phase_id` | phase | number | 阶段唯一标识 |
| `name` | phase | string | 阶段名称（如"初始状态"、"求生中期"）|
| `beat_range` | phase | array | 该阶段覆盖的节拍范围 [start, end] |
| `appearance` | phase | string | 该阶段的角色外观描述 |

**场景字段**:

| 字段 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `location_id` | location | number | 场景唯一标识 |
| `name` | location | string | 场景名称 |
| `time_of_day` | location | string | 时间段：dawn/morning/noon/afternoon/dusk/evening/night/midnight |
| `description` | location | string | 场景描述 |
| `beats` | location | array | 该场景包含的节拍 ID 列表 |

**节拍字段**:

| 字段 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `beat_id` | story_beat | number | 节拍唯一标识 |
| `beat_type` | story_beat | string | 节拍类型：setup/inciting_incident/rising_action/climax/resolution |
| `intensity` | story_beat | number | **情感强度** 0-1，用于控制叙事节奏 |
| `suggested_duration` | story_beat | number | **建议镜头时长**（秒），基于场景类型 |
| `narration` | story_beat | string | 中文旁白 |
| `description` | story_beat | string | 场景描述（用于理解，不用于生成）|
| `mood` | story_beat | string | 情绪标签 |
| `location` | story_beat | string | 场景地点 |
| `characters_involved` | story_beat | array | 参与角色列表 |

**故事创作原则**:

1. **场景数量与密度**:
   - 建议 **10-14 个节拍**，确保叙事完整且过渡平滑
   - 每个重要情节点用 2-3 个节拍展开，避免跳跃
   - 宁可多不可少：细腻的过渡比突兀的跳跃更重要

2. **环境细节描述**:
   - 每个 `description` 必须包含具体的 **光线、天气、植被/建筑** 描述
   - 示例：「清晨阳光洒在沙滩上，海草和漂流物散落四周，远处是茂密的热带丛林」
   - 避免抽象描述如「一个美丽的地方」

3. **基调统一与情绪控制**:
   - 在 `style_keywords` 中定义整体基调（如 `muted color palette, atmospheric`）
   - 情绪变化要渐进：horror → tense → melancholic → contemplative → hopeful
   - 避免情绪大起大落，保持叙事节奏稳定

4. **场景连贯性**:
   - 相邻节拍在 **时间和空间** 上要紧密衔接
   - 使用「时间锚点」：清晨、正午、黄昏、夜晚、黎明
   - 使用「空间过渡」：从沙滩→丛林→溪边→庇护所，而非直接跳跃

5. **角色状态演变**:
   - 角色外观应随剧情变化（衣物破损、头发凌乱、神情变化）
   - 使用 `phases` 定义角色不同阶段的外观
   - 每个阶段通过 `beat_range` 关联到对应的故事节拍

6. **叙事结构分配**:
   | 阶段 | 建议节拍数 | 说明 |
   |------|-----------|------|
   | setup | 2-3 | 建立世界观和灾难/冲突 |
   | inciting_incident | 1-2 | 触发主线的关键事件 |
   | rising_action | 4-6 | 主角面对挑战、成长的过程 |
   | climax | 2 | 故事最高潮和转折点 |
   | resolution | 2 | 收束和情感升华 |

7. **角色锚定特征**:
   - 每个主要角色必须定义 `anchor_features`，包含面部、发型、体型、标识特征
   - 锚定特征使用英文描述，确保在 image_prompt 中被正确识别
   - 锚定特征应在每个包含该角色的 image_prompt 中重复出现
   - 示例：`"face": "oval face, large almond-shaped eyes"` 而非 `"face": "漂亮的脸"`
   - **注意**：锚定特征是对阶段参考图的文字补充，生成镜头时仍需使用参考图作为视觉输入

8. **情感强度曲线**:
   - `intensity` 字段范围 0-1，用于控制叙事节奏
   - 开场和结尾通常 0.3-0.5（平缓）
   - 高潮部分 0.8-1.0（紧张）
   - 建议的强度曲线：setup(0.3) → inciting(0.5) → rising(0.6-0.8) → climax(1.0) → resolution(0.4)
   - `suggested_duration` 基于强度自动调整：高强度镜头较短(1-2秒)，低强度镜头较长(3-4秒)

**description 字段写作模板**:
```
[时间/光线] + [地点/环境] + [角色状态/动作] + [周围细节] + [氛围/情绪暗示]
```

示例：
- ❌ 「女主角在丛林里走」
- ✅ 「黄昏时分，橙红色的晚霞染红了天空，林晓在丛林边缘的大树下忙碌着，用捡来的树枝和棕榈叶搭建简陋的庇护所，地上散落着她收集的椰子和野果」

### 步骤 0.2: 使用脚本写入 story_outline.json

使用 Bash 工具执行以下命令，将故事 JSON 通过管道传递给脚本：

```bash
echo '<生成的JSON数据>' | python .claude/scripts/manga_create_story.py
```

脚本会：
- 验证故事结构完整性
- 验证 narrative_arc 五段式结构
- 验证角色定义和阶段
- 验证场景/地点定义
- 自动规范化中文标点符号
- 添加元数据
- 写入 story_outline.json 文件

### 步骤 0.3: 人工审核提示

生成完成后，向用户显示：

```
✅ 阶段 0 完成！

已生成:
- 项目引用: screenplay.json (指向项目目录)
- 故事大纲: output/故事标题/story_outline.json
- 输出目录: output/故事标题/

📋 请审核故事内容:

1. 故事逻辑:
   - 检查叙事结构是否完整（起承转合）
   - 检查场景之间是否有因果关系
   - 检查情感曲线是否合理

2. 角色设定:
   - 检查角色动机是否清晰
   - 检查角色外观描述是否具体
   - 检查角色阶段划分是否合理

3. 场景/地点:
   - 检查 locations 是否覆盖所有节拍
   - 检查时间段设置是否合理

4. 如需修改，可直接编辑 story_outline.json

审核完成后，说"继续阶段0.5"开始生成分镜。
```

---

## 阶段 0.5：分镜规划

### 步骤 0.5.1: 按场景分组生成分镜

根据故事大纲，为每个场景生成具体的镜头分镜。

**分镜数据结构**:
```json
{
  "locations": [
    {
      "location_id": 1,
      "name": "暴风雨海面",
      "time_of_day": "night",
      "background_prompt": "anime style, stormy night sea, dark clouds covering sky, lightning bolts, turbulent ocean with white foam, teal and orange color grading, desaturated cool tones, deep blue-gray shadows, film grain texture, no characters, background only",
      "character_phase": 1,
      "shots": [
        {
          "shot_id": "1-1",
          "composition": "wide shot",
          "narration": "暴风雨来得那么突然……",
          "action": "游轮在风浪中摇晃",
          "character_visible": false,
          "image_prompt": "anime style, wide shot of stormy night sea, cruise ship silhouette in distance, lightning flash, turbulent waves, teal and orange color grading, no characters",
          "video_prompt": "[Wide shot] [Slow pan right] Dark stormy sea with lightning flashing, ship silhouette rocking, rain pouring"
        },
        {
          "shot_id": "1-2",
          "composition": "medium shot",
          "narration": "我拼命抓住木板……",
          "action": "女主在海中挣扎",
          "character_visible": true,
          "image_prompt": "anime style, medium shot of young woman struggling in dark sea, gripping wooden plank, waves crashing, lightning illumination, teal and orange color grading",
          "video_prompt": "[Medium shot] [Static with shake] Woman struggling in water, gripping wooden plank, waves washing over"
        }
      ]
    }
  ]
}
```

**镜头字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `shot_id` | string | 镜头 ID，格式: "场景ID-镜头序号" |
| `composition` | string | 景别: wide shot/medium shot/close-up/extreme close-up/POV shot |
| `narration` | string | 中文旁白 |
| `action` | string | 角色动作描述 |
| `character_visible` | boolean | 该镜头是否包含角色 |
| `image_prompt` | string | 图片生成提示词，必须以 "anime style" 开头 |
| `video_prompt` | string | 视频提示词，格式: [镜头类型] [运动描述] [动作描述] |

**分镜设计原则**:

1. **每个场景 2-4 个镜头**: 不要太多，保持叙事紧凑
2. **character_visible**: 明确标注是否包含角色，用于决定是否使用角色参考图
3. **image_prompt 必须以 "anime style" 开头**
4. **保持同一场景内的视觉一致性**

**色调统一原则**（确保视觉风格一致）:

每个 image_prompt 必须包含以下色调控制词：
```
teal and orange color grading, film grain texture, consistent muted color palette
```

### 步骤 0.5.2: 使用脚本写入 screenplay.json

使用 Bash 工具执行以下命令：

```bash
echo '<生成的JSON数据>' | python .claude/scripts/manga_create_shots.py
```

脚本会：
- 加载 story_outline.json
- 验证分镜与故事的一致性
- 验证 locations 结构
- 验证每个镜头的必需字段
- 合并故事信息和分镜信息
- 自动关联角色阶段
- 写入 screenplay.json 文件

### 步骤 0.5.3: 人工审核提示

生成完成后，向用户显示：

```
✅ 阶段 0.5 完成！

已生成:
- 完整剧本: output/故事标题/screenplay.json

📋 请审核分镜内容:

1. 视觉提示词:
   - 检查 image_prompt 是否准确描述画面
   - 检查 video_prompt 是否包含合适的镜头运动

2. 镜头设计:
   - 检查 composition 是否合适
   - 检查 character_visible 是否正确

3. 角色阶段关联:
   - 检查各场景的 character_phase 是否正确

4. 如需修改，可直接编辑 screenplay.json

审核完成后，说"继续阶段1"开始生成角色阶段参考图。
```
