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

  "world_map": {
    "world_id": 1,
    "name": "南太平洋",
    "description": "广阔的南太平洋海域，散布着无数热带岛屿",
    "style_base": {
      "color_palette": "teal and orange, muted tropical colors",
      "lighting_style": "natural dramatic lighting",
      "atmosphere": "isolated, vast, natural beauty",
      "art_style": "anime style, cinematic"
    },
    "geography_anchors": ["endless blue ocean", "tropical climate", "volcanic islands"],
    "world_map_image": null
  },

  "regions": [
    {
      "region_id": 1,
      "name": "荒岛",
      "description": "与世隔绝的热带小岛",
      "parent_world": 1,
      "style_modifiers": {
        "color_accent": "lush green vegetation, golden sand",
        "unique_features": "dense jungle, white beaches, rocky cliffs"
      },
      "geography": {
        "terrain_type": "volcanic island",
        "vegetation": "tropical rainforest, palm trees",
        "water_features": "freshwater stream, coastal reefs"
      },
      "region_map_image": null,
      "locations": [1, 2, 3]
    }
  ],

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
      "region_id": 1,
      "name": "暴风雨海面",
      "time_of_day": "night",
      "description": "夜晚的暴风雨大海，乌云密布，闪电，巨浪",
      "local_features": {
        "ground": "turbulent ocean surface",
        "props": "debris, floating wood"
      },
      "beats": [1, 2]
    },
    {
      "location_id": 2,
      "region_id": 1,
      "name": "荒岛沙滩",
      "time_of_day": "morning",
      "description": "热带岛屿沙滩，金色沙子，椰子树，碧蓝大海",
      "local_features": {
        "ground": "white sand with shells",
        "flora": "coconut palms",
        "props": "driftwood, rocks"
      },
      "beats": [3, 4, 9]
    },
    {
      "location_id": 3,
      "region_id": 1,
      "name": "丛林深处",
      "time_of_day": "afternoon",
      "description": "茂密的热带丛林，高大的树木，藤蔓，斑驳的阳光",
      "local_features": {
        "ground": "forest floor with fallen leaves",
        "flora": "tall trees, vines, ferns",
        "props": "rocks, fallen logs"
      },
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
| `world_map` | 顶层 | object | **世界地图定义**（可选，用于分层地图系统）|
| `regions` | 顶层 | array | **区域列表**（可选，用于分层地图系统）|
| `characters` | 顶层 | array | 角色列表 |
| `locations` | 顶层 | array | 场景/地点列表 |
| `narrative_arc` | 顶层 | object | 五段式叙事结构 |
| `story_beats` | 顶层 | array | 故事节拍列表 |

**世界地图字段** (可选，用于保证场景风格一致性):

| 字段 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `world_id` | world_map | number | 世界唯一标识 |
| `name` | world_map | string | 世界名称 |
| `description` | world_map | string | 世界描述 |
| `style_base` | world_map | object | **全局风格基础** |
| `style_base.color_palette` | world_map | string | 全局色调（如 "teal and orange, muted colors"）|
| `style_base.lighting_style` | world_map | string | 光线风格（如 "natural dramatic lighting"）|
| `style_base.atmosphere` | world_map | string | 整体氛围（如 "isolated, vast"）|
| `style_base.art_style` | world_map | string | 艺术风格（如 "anime style, cinematic"）|
| `geography_anchors` | world_map | array | 地理锚点列表（如 ["ocean", "tropical climate"]）|
| `world_map_image` | world_map | string | 生成的世界地图图片路径 |

**区域字段** (可选):

| 字段 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `region_id` | region | number | 区域唯一标识 |
| `name` | region | string | 区域名称 |
| `description` | region | string | 区域描述 |
| `parent_world` | region | number | 所属世界 ID |
| `style_modifiers` | region | object | **区域风格修饰** |
| `style_modifiers.color_accent` | region | string | 区域色彩强调（如 "lush green, golden sand"）|
| `style_modifiers.unique_features` | region | string | 区域独特特征（如 "dense jungle, white beaches"）|
| `geography` | region | object | 区域地理信息 |
| `geography.terrain_type` | region | string | 地形类型（如 "volcanic island"）|
| `geography.vegetation` | region | string | 植被类型（如 "tropical rainforest"）|
| `geography.water_features` | region | string | 水体特征（如 "freshwater stream"）|
| `region_map_image` | region | string | 生成的区域地图图片路径 |
| `locations` | region | array | 该区域包含的场景 ID 列表 |

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
| `region_id` | location | number | **所属区域 ID**（可选，用于分层地图系统）|
| `name` | location | string | 场景名称 |
| `time_of_day` | location | string | 时间段：dawn/morning/noon/afternoon/dusk/evening/night/midnight |
| `description` | location | string | 场景描述 |
| `local_features` | location | object | **场景特定细节**（可选）|
| `local_features.ground` | location | string | 地面特征（如 "white sand with shells"）|
| `local_features.flora` | location | string | 植物特征（如 "coconut palms"）|
| `local_features.props` | location | string | 道具/物品（如 "driftwood, rocks"）|
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

9. **分层地图系统** (可选但推荐):
   - 对于有多个区域的故事，建议使用 `world_map` + `regions` + `locations` 三层结构
   - **风格继承链**：World → Region → Location
     - 世界层：定义全局色调（color_palette）、光线风格（lighting_style）、艺术风格（art_style）
     - 区域层：继承世界风格 + 区域特色（style_modifiers）
     - 场景层：继承区域风格 + 场景细节（local_features、time_of_day）
   - 示例风格继承：
     ```
     世界: teal and orange colors, cinematic lighting
       ↓
     区域: + lush green vegetation, dense jungle
       ↓
     场景: + white sand beach, morning light
     ```
   - 分层地图可以确保同一区域内的场景保持视觉一致性
   - 如果不使用分层地图系统，系统会自动创建默认的世界和区域

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
          "speaker": "旁白",
          "composition": "wide shot",
          "narration": "暴风雨来得那么突然……",
          "action": "游轮在风浪中摇晃",
          "character_visible": false,
          "mood": "tense",
          "image_prompt": "anime style, wide shot of stormy night sea, cruise ship silhouette in distance, lightning flash, turbulent waves, teal and orange color grading, no characters",
          "video_prompt": "[Wide shot] [Slow pan right] Dark stormy sea with lightning flashing, ship silhouette rocking, rain pouring"
        },
        {
          "shot_id": "1-2",
          "speaker": "林晓",
          "composition": "medium shot",
          "narration": "我拼命抓住木板……",
          "action": "女主在海中挣扎",
          "character_visible": true,
          "mood": "urgent",
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
| `speaker` | string | **说话人**（可选，自动推断）：角色名称或"旁白" |
| `composition` | string | 景别: wide shot/medium shot/close-up/extreme close-up/POV shot |
| `narration` | string | 中文旁白/台词 |
| `action` | string | 角色动作描述 |
| `character_visible` | boolean | 该镜头是否包含角色 |
| `mood` | string | **情绪标签**（必填）：用于语音情绪控制，见下方情绪值列表 |
| `image_prompt` | string | 图片生成提示词，必须以 "anime style" 开头 |
| `video_prompt` | string | 视频提示词，格式: [镜头类型] [运动描述] [动作描述] |

**情绪 (mood) 值列表** - 用于语音情绪控制（语速、音调自动调整）:

| 类别 | 可用值 | 效果 |
|------|--------|------|
| 激动类 | `excited`, `battle`, `surprise`, `angry` | 语速+8~10%, 音调+3~8Hz |
| 悲伤类 | `sad`, `melancholy`, `farewell`, `loss` | 语速-5~8%, 音调-3~5Hz |
| 温柔类 | `tender`, `romantic`, `warm`, `love` | 语速-3~5%, 音调+2Hz |
| 紧张类 | `tense`, `urgent`, `chase`, `danger`, `suspense` | 语速+5~10%, 音调+3~5Hz |
| 平静类 | `calm`, `neutral`, `narration`, `peaceful` | 语速-3~0%, 音调+0Hz |
| 欢快类 | `happy`, `joyful`, `playful` | 语速+5~8%, 音调+3~5Hz |
| 其他类 | `mysterious`, `solemn`, `epic` | 语速-3~5%, 音调-2~+2Hz |

> 参数已优化为温和值（±10%以内），确保同一角色在不同情绪下声音自然连贯。

**重要**：AI 在生成分镜时必须为每个镜头指定 `mood` 字段，根据该镜头的情绪氛围选择合适的值。

**说话人 (speaker) 说明**:

`speaker` 字段用于多角色配音，指定该旁白/台词由哪个角色或旁白朗读。

**重要**：AI 在生成分镜时应该为每个镜头明确指定 `speaker`。

说话人类型：
- **角色名称**：如 "小智"、"皮卡丘" - 该角色的台词或内心独白
- **"旁白"**：第三人称叙述，描述性文字

判断原则：
- 第一人称视角的台词/内心独白 → 使用角色名称
- 第三人称描述性叙述 → 使用 "旁白"
- 角色特有的叫声/口头禅 → 使用该角色名称

示例：
```json
{
  "shots": [
    {
      "shot_id": "1-1",
      "speaker": "小智",
      "narration": "成为宝可梦大师……这是我从小的梦想。"
    },
    {
      "shot_id": "4-1",
      "speaker": "旁白",
      "narration": "那是……烈雀群。它们看起来很生气。"
    },
    {
      "shot_id": "4-9",
      "speaker": "皮卡丘",
      "narration": "皮卡……丘！！！"
    }
  ]
}
```

**语音配置 (voice_config)**:

剧本中会自动生成 `voice_config` 字段，用于多角色配音：

```json
{
  "voice_config": {
    "小智": "yunxi",      // 阳光少年声
    "皮卡丘": "yunxia",   // 可爱声音
    "大木博士": "yunyang", // 成熟男声
    "旁白": "xiaoxiao"    // 温暖女声
  }
}
```

可用语音列表：
| 语音 ID | 性别 | 风格 | 适用角色 |
|---------|------|------|---------|
| `xiaoxiao` | 女 | 温暖 | 旁白、温柔角色 |
| `xiaoyi` | 女 | 活泼 | 年轻女性角色 |
| `yunxi` | 男 | 少年 | 年轻男主角 |
| `yunjian` | 男 | 热血 | 战斗场景、激情时刻 |
| `yunyang` | 男 | 成熟 | 成熟角色、长辈 |
| `yunxia` | 男 | 可爱 | 萌系角色、小动物 |

**分镜设计原则**:

1. **镜头数量随节奏变化**: 根据场景关联的节拍强度动态调整
   | 节奏类型 | 强度范围 | 镜头数 | 时长/镜头 | 适用场景 |
   |---------|---------|--------|----------|---------|
   | slow (慢) | 0.0-0.4 | 2-3 | 3-4秒 | 开场、沉思、情感铺垫 |
   | moderate (中) | 0.4-0.7 | 3-4 | 2-3秒 | 对话、发现、日常叙事 |
   | fast (快) | 0.7-1.0 | 4-6 | 1-2秒 | 动作、追逐、高潮冲突 |

2. **character_visible**: 明确标注是否包含角色，用于决定是否使用角色参考图
3. **image_prompt 必须以 "anime style" 开头**
4. **保持同一场景内的视觉一致性**
5. **节奏平衡**: 确保故事中包含多种节奏类型，避免单调

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
