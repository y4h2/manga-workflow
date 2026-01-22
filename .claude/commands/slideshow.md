# Slideshow 幻灯片视频生成

将镜头图片拼接成幻灯片视频，支持配音和情绪化语音。

## 使用方法

```
/slideshow [选项]
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--duration` | 每张图片显示时长（秒） | 3 |
| `--transition` | 转场效果：none/fade/crossfade | none |
| `--transition-duration` | 转场时长（秒） | 0.5 |
| `--narration` | 启用配音生成 | false |
| `--no-postprocess` | 禁用音频后处理 | false |
| `--output` | 输出文件名 | 自动生成 |

## 示例

```bash
# 基础用法（每张图片3秒，无转场）
/slideshow

# 自定义时长
/slideshow --duration 2

# 带淡入淡出转场
/slideshow --transition fade

# 带交叉淡化转场
/slideshow --transition crossfade --transition-duration 1

# 带配音（情绪化语音）
/slideshow --narration

# 带配音和转场
/slideshow --narration --transition crossfade
```

## 执行逻辑

当用户调用 `/slideshow` 时，执行以下步骤：

### 步骤 1: 检查前置条件

1. 检查 ffmpeg 是否安装：
```bash
ffmpeg -version
```

2. 如果未安装，提示用户：
```
ffmpeg 未安装，请先安装：
- macOS: brew install ffmpeg
- Linux: apt install ffmpeg
- Windows: https://ffmpeg.org/download.html
```

3. 加载 screenplay.json 获取项目路径和镜头列表

### 步骤 2: 解析参数

从用户输入解析参数，使用默认值填充未指定的参数：
- duration: 3
- transition: none
- transition_duration: 0.5
- narration: false
- no_postprocess: false
- output: {title}_幻灯片_{timestamp}.mp4

### 步骤 3: 生成配音（可选）

如果用户指定了 `--narration`，先生成配音音频：

```bash
# 带音频后处理（音量规范化、淡入淡出）
python .claude/scripts/manga_generate_narration.py <output_dir>

# 不带后处理（如果后处理失败或指定 --no-postprocess）
python .claude/scripts/manga_generate_narration.py <output_dir> --no-postprocess
```

**配音功能特性：**

1. **多角色语音** - 根据 `speaker` 字段为不同角色分配不同声音
2. **情绪化语音** - 根据 `mood` 字段自动调整语速和音调

**情绪参数对照表：**

| 情绪类别 | mood 值 | 语速 | 音调 | 适用场景 |
|---------|---------|------|------|---------|
| 激动类 | excited, battle, surprise, angry | +8~10% | +3~8Hz | 战斗、惊讶、愤怒 |
| 悲伤类 | sad, melancholy, farewell, loss | -5~8% | -3~5Hz | 分离、失落、忧郁 |
| 温柔类 | tender, romantic, warm, love | -3~5% | +2Hz | 温馨、告白、浪漫 |
| 紧张类 | tense, urgent, chase, danger, suspense | +5~10% | +3~5Hz | 追逐、危机、悬疑 |
| 平静类 | calm, neutral, narration, peaceful | -3~0% | +0Hz | 旁白、叙述、宁静 |
| 欢快类 | happy, joyful, playful | +5~8% | +3~5Hz | 开心、欢乐、俏皮 |
| 其他类 | mysterious, solemn, epic | -3~5% | -2~+2Hz | 神秘、庄重、史诗 |

> 注：参数范围已优化为温和值（±10% 以内），避免同一角色在不同情绪下声音差异过大。

**可用语音列表：**

| 语音 ID | 性别 | 风格 | 适用角色 |
|---------|------|------|---------|
| xiaoxiao | 女 | 温暖 | 旁白、温柔角色 |
| xiaoyi | 女 | 活泼 | 年轻女性角色 |
| yunxi | 男 | 少年 | 年轻男主角 |
| yunjian | 男 | 热血 | 战斗场景、激情时刻 |
| yunyang | 男 | 成熟 | 成熟角色、长辈 |
| yunxia | 男 | 可爱 | 萌系角色、小动物 |

### 步骤 4: 生成幻灯片视频

```bash
python .claude/scripts/manga_slideshow.py [参数]
```

### 步骤 5: 输出结果

显示生成的视频信息：
- 文件路径
- 分辨率
- 时长
- 文件大小
- 配音状态（如启用）

提供播放命令：
```bash
open "output/项目名/视频文件.mp4"
```
