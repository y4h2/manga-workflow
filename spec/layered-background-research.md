# 游戏场景生成技术与漫剧工作流的融合分析

## 核心发现：两个正交的分层系统

### 现有分层地图系统 (水平维度 - 风格一致性)
```
World Map → Region Map → Location
   ↓            ↓           ↓
style_base  style_mods  local_features
```
- 解决：**区域间的视觉风格一致性**
- 实现：区域地图作为 image-to-image 参考

### 分层背景方案 (垂直维度 - 景深层次)
```
Far Layer → Mid Layer → Near Layer
   ↓            ↓           ↓
  天空         主体        前景
```
- 解决：**单个场景的深度感和视差效果**
- 用途：增强画面层次感，支持视差滚动

### 两者结合的架构
```
        ┌──────────────────────────────────────────┐
        │            World Map (style_base)         │
        └─────────────────┬────────────────────────┘
                          ↓ 风格继承
        ┌─────────────────────────────────────────────┐
        │         Region Map (style_modifiers)         │
        └─────────────────┬───────────────────────────┘
                          ↓ 风格参考 (image-to-image)
    ┌─────────────────────────────────────────────────────┐
    │                   Location Background               │
    │  ┌─────────────────────────────────────────────┐   │
    │  │  Far Layer   │  远景（继承区域风格）        │   │
    │  ├─────────────────────────────────────────────┤   │
    │  │  Mid Layer   │  中景（继承区域风格）        │   │ 深度分层
    │  ├─────────────────────────────────────────────┤   │
    │  │  Near Layer  │  近景（继承区域风格）        │   │
    │  └─────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────┘
```

**关键点**: 每个深度层都继承区域的风格，确保三层之间以及与其他场景之间的视觉一致性

---

## 一、游戏场景生成的主要方法

### 1. 程序化生成 (PCG) 经典算法

| 方法 | 原理 | 典型应用 |
|------|------|---------|
| **Perlin/Simplex Noise** | 梯度噪声生成自然纹理和地形 | 地形高度图、云层、水面 |
| **Cellular Automata** | 网格单元根据邻居状态演化 | 洞穴系统、有机地图布局 |
| **Wave Function Collapse (WFC)** | 约束传播确保相邻瓦片兼容 | 城市、迷宫、室内场景 |
| **L-System** | 递归规则生成分形结构 | 植被、建筑、自然形态 |
| **BSP (Binary Space Partitioning)** | 递归分割空间 | 房间/走廊布局 |

### 2. AI/ML 驱动的现代方法

| 方法 | 原理 | 典型应用 |
|------|------|---------|
| **GAN** | 生成器+判别器对抗训练 | 纹理、地形、角色外观 |
| **VAE** | 潜在空间编码+解码 | 风格混合、变体生成 |
| **NeRF** | 神经网络编码3D场景 | 环境光照、远景细节 |
| **Diffusion Models** | 迭代去噪生成 | 当前主流图像生成 |
| **RL (强化学习)** | MDP框架优化生成 | 平衡质量/多样性/可玩性 |
| **LLM** | 语义理解和生成 | 故事驱动的内容生成 |

### 3. 工业实践

- **Unreal PCG Framework**: 节点式程序化工具，支持生物群落、建筑等
- **Genie 3 (DeepMind)**: 从文本生成交互式世界
- **混合方法**: 程序化生成结构 + 手工精修细节

---

## 二、技术限制

**关键发现**: Gemini 目前不支持生成真正的透明背景 PNG

- 请求 "transparent background" 只会得到棋盘格图案的假透明
- PNG 格式不等于有 alpha 通道
- 这是 Gemini 图像生成的已知限制

---

## 三、可行的替代方案

### 方案 C1: 深度感知单图 (推荐)

**原理**: 不分离生成，而是通过 prompt 控制单张图片的层次结构

```
实现方式:
1. 在 background_prompt 中明确指定景深层次:
   "anime style background with clear depth layers:
    - distant sky and mountains (background, 20% top)
    - main scene elements (midground, 60% center)
    - foreground details like grass, rocks (foreground, 20% bottom)"

2. 生成具有自然景深的单张图片
3. 无需透明通道，直接使用

优点:
- 无需额外处理
- 视觉效果自然
- 改动最小

代码改动: ~30 行，只需修改 build_background_prompt()
```

### 方案 C2: 生成后提取分层 (中等复杂度)

**原理**: 生成完整背景 → 用 AI 提取深度图 → 分割为多层

```
实现方式:
1. 正常生成单张完整背景 (loc_01_bg.png)
2. 使用深度估计模型 (如 MiDaS, ZoeDepth) 生成深度图
3. 基于深度图分割为 3 层 mask
4. 提取各层并保存

工具链:
- pip install transformers torch  # 深度估计
- Pillow / OpenCV  # 图像处理

输出文件:
loc_01_bg.png          # 原始完整背景
loc_01_depth.png       # 深度图
loc_01_far.png         # 远景 (含透明)
loc_01_mid.png         # 中景 (含透明)
loc_01_near.png        # 近景 (含透明)

代码改动: 新增 manga_extract_layers.py (~150 行)
```

### 方案 C4: 纯前景生成 + Rembg (实用)

**原理**: 分别生成场景元素，用 rembg 去除背景后叠加

```
实现方式:
1. 生成远景: "sky and distant mountains on solid green background"
2. 生成中景: "forest trees on solid green background"
3. 生成近景: "foreground grass and rocks on solid green background"
4. 用 rembg 去除绿色背景
5. 按层叠加合成

工具链:
- pip install rembg onnxruntime
- rembg 自动处理背景移除

输出:
loc_01_far.png   # 远景 (透明背景)
loc_01_mid.png   # 中景 (透明背景)
loc_01_near.png  # 近景 (透明背景)
loc_01_bg.png    # 合成后完整背景

代码改动: 新增 manga_generate_layered_bg.py (~200 行)
```

---

## 四、推荐实现路径

| 阶段 | 方案 | 复杂度 | 效果 |
|------|------|--------|------|
| **短期** | C1 深度感知单图 | 低 | 自然层次感 |
| **中期** | C4 Rembg 分层 | 中 | 真正分层叠加 |
| **可选** | C2 深度提取 | 中高 | 自动分层 |

---

## 五、数据结构扩展

```json
// screenplay.json - location 扩展字段
{
    "location_id": 1,
    "name": "海岸悬崖",
    "region_id": 1,
    "background_image": "output/xxx/loc_01_bg.png",

    // 新增：分层背景信息（可选）
    "depth_layers": {
        "enabled": true,
        "far_layer": "output/xxx/loc_01_far.png",
        "mid_layer": "output/xxx/loc_01_mid.png",
        "near_layer": "output/xxx/loc_01_near.png"
    }
}
```

---

## 六、依赖要求

```bash
# 基础依赖 (已有)
pip install google-genai pillow

# 分层功能新增
pip install rembg onnxruntime

# 深度估计 (可选)
pip install torch transformers scipy

# 视差视频 (系统工具)
brew install ffmpeg  # macOS
```

---

## Sources

- Procedural Content Generation in Games
- Unreal Engine PCG Framework
- NeRF for Procedural Worlds
- Genie 3 World Model
- GANs for Terrain Generation
