# 稳定视差滚动方案研究

## 问题分析

当前 C4 方案（绿幕+rembg）存在的问题：
- Gemini 生成的绿色背景不纯净，包含渐变和噪点
- rembg 为真实照片设计，对 AI 生成图边缘处理差
- 三层分别生成+去背+合成，错误会累积

## 六大替代方案对比

| 方案 | 稳定性 | 质量 | 速度 | 成本 | 复杂度 |
|------|--------|------|------|------|--------|
| **Ken Burns** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | 免费 | 最低 |
| **C2+ (MiDaS改进)** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 免费 | 低 |
| **3D Photo Inpainting** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | 低 | 高 |
| **AnimateDiff+ControlNet** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | 中 | 高 |
| **ComfyUI DepthFlow** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 免费 | 中 |
| **Runway Gen-4.5** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | 高 | 最低 |

---

## 方案详细分析

### 1. Ken Burns 效果（最简单最稳定）

**原理**: 对单张背景图进行缩放/平移动画，无需分层

**FFmpeg 实现**:
```bash
# Zoom In
ffmpeg -loop 1 -i bg.png -vf "zoompan=z='1+0.02*in/150':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1920x1080:fps=30" -t 5 output.mp4

# Pan Right
ffmpeg -loop 1 -i bg.png -vf "zoompan=z='1':x='in*3':y='0':d=150:s=1920x1080:fps=30" -t 5 output.mp4
```

**优点**:
- 极度稳定，完全确定性
- FFmpeg 直接实现，零 Python 依赖
- 毫秒级生成

**缺点**:
- 无真正的视差效果
- 适合简单内容

**适用场景**: 快速预览、简单背景、不需要深度感的场景

---

### 2. C2+ 改进版（推荐短期方案）

**改进点**:
1. **升级模型**: `Intel/dpt-large` → `Intel/dpt-beit-large-512` (性能+28%)
2. **深度图平滑**: 添加中值滤波去噪 (kernel=5)
3. **自适应分层**: 用 Otsu 阈值替代固定线性分层
4. **边缘羽化增强**: 高斯模糊半径 3→5
5. **缓动曲线**: 视频开头结尾添加 ease-in-out

**关键代码改进**:
```python
# 深度图预处理
from scipy.ndimage import median_filter
depth = median_filter(depth, size=5)

# Otsu 自适应阈值
from skimage.filters import threshold_multiotsu
thresholds = threshold_multiotsu(depth, classes=num_layers)
```

**优点**:
- 改进效果明显
- 无需额外依赖
- 向后兼容

---

### 3. 3D Photo Inpainting（高质量）

**项目**: https://github.com/vt-vl-lab/3d-photo-inpainting

**原理**:
1. 估计深度
2. 生成点云
3. 使用 inpainting 填充遮挡区域
4. 渲染 3D 摄像机运动

**安装**:
```bash
git clone https://github.com/vt-vl-lab/3d-photo-inpainting
pip install -r requirements.txt
# 下载预训练模型
```

**优点**:
- 真实的 3D 摄像机运动
- 自动处理遮挡问题
- 电影级视差效果

**缺点**:
- 设置复杂
- 处理速度慢
- 需要 GPU

---

### 4. AnimateDiff + ControlNet

**原理**: 使用 Stable Diffusion 生态的视频生成

**工作流**:
```
静态图 → ControlNet(Depth) → AnimateDiff → 视频
```

**优点**:
- 可以生成复杂动画
- 与 SD 生态兼容

**缺点**:
- 生成结果不确定性高
- 需要大量 VRAM
- 速度慢

---

### 5. DepthFlow（推荐中期方案）

**项目**: https://github.com/BrokenSource/DepthFlow

**安装**:
```bash
pip install depthflow
```

**使用**:
```python
from depthflow import DepthFlow

df = DepthFlow()
df.set_image("background.png")
df.set_motion("dolly", duration=5.0)
df.render("output.mp4")
```

**支持的摄像机运动**:
- `dolly`: 推拉镜头
- `zoom`: 变焦
- `circle`: 环绕
- `pan`: 平移
- `shake`: 抖动

**优点**:
- 开源免费
- 效果可控
- 多种运动类型

**缺点**:
- 相对较新的项目
- 需要 GPU

---

### 6. Runway Gen-4.5（商业方案）

**API 使用**:
```python
import runwayml

client = runwayml.Client()
task = client.video.create(
    model="runway-gen4-turbo",
    image_prompt="path/to/image.png",
    motion_vector={"camera_motion": "dolly_in"}
)
```

**优点**:
- 最高质量
- 最简单的 API
- 无需本地 GPU

**缺点**:
- 付费服务（$0.05-0.15/秒）
- 需要网络
- 结果有一定随机性

---

## 推荐实施路径

### 短期（立即可用）

1. **Ken Burns**: 零风险备选方案
2. **C2+ 改进版**: 增强现有深度分层

### 中期（1-2周）

3. **DepthFlow 集成**: 更专业的视差效果

### 长期（可选）

4. **3D Photo Inpainting**: 电影级效果
5. **Runway API**: 商业项目的高质量选项

---

## 技术资源

- [MiDaS v3.1](https://github.com/isl-org/MiDaS)
- [DepthFlow](https://github.com/BrokenSource/DepthFlow)
- [3D Photo Inpainting](https://github.com/vt-vl-lab/3d-photo-inpainting)
- [FFmpeg zoompan](https://trac.ffmpeg.org/wiki/ZoomPan)
- [Runway Gen-4](https://docs.runwayml.com)

---

## 附录：FFmpeg zoompan 参数

```
zoompan 滤镜参数:
  z: 缩放级别表达式 (1=原始, >1=放大)
  x: 平移 X 坐标
  y: 平移 Y 坐标
  d: 帧数
  s: 输出尺寸
  fps: 帧率

变量:
  iw, ih: 输入宽高
  in: 当前帧号
  zoom: 当前缩放级别
  on: 输出帧号
```

**常用效果**:
```bash
# Zoom In (中心放大)
zoompan=z='min(zoom+0.002,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'

# Zoom Out (中心缩小)
zoompan=z='1.5-0.002*in':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'

# Pan Left to Right
zoompan=z='1':x='in*2':y='0'

# Pan Right to Left
zoompan=z='1':x='iw-ow-in*2':y='0'

# Pan Up to Down
zoompan=z='1':x='0':y='in*2'

# Ken Burns (Zoom + Pan)
zoompan=z='1+0.001*in':x='in':y='ih/2-(ih/zoom/2)'
```
