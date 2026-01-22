#!/usr/bin/env python3
"""
Manga Generate Narration - 多角色配音生成

支持为不同角色使用不同的声音，并通过 SSML 和情绪参数优化语音表现力。

使用方法:
    python manga_generate_narration.py <output_dir>

示例:
    python manga_generate_narration.py output/初心之雷

功能:
    - 多角色语音分配
    - 情绪感知的语速/音调控制
    - SSML 标签增强表现力
    - 音频后处理（音量规范化、淡入淡出）
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# 可用的中文语音配置
AVAILABLE_VOICES = {
    # 女声
    "xiaoxiao": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "gender": "female",
        "style": "温暖",
        "description": "温暖女声，适合旁白、温柔角色"
    },
    "xiaoyi": {
        "voice": "zh-CN-XiaoyiNeural",
        "gender": "female",
        "style": "活泼",
        "description": "活泼女声，适合年轻女性角色"
    },
    "xiaobei": {
        "voice": "zh-CN-liaoning-XiaobeiNeural",
        "gender": "female",
        "style": "幽默",
        "description": "东北方言女声，适合喜剧角色"
    },
    # 男声
    "yunxi": {
        "voice": "zh-CN-YunxiNeural",
        "gender": "male",
        "style": "少年",
        "description": "阳光少年声，适合年轻男主角"
    },
    "yunjian": {
        "voice": "zh-CN-YunjianNeural",
        "gender": "male",
        "style": "热血",
        "description": "热血男声，适合战斗场景、激情时刻"
    },
    "yunyang": {
        "voice": "zh-CN-YunyangNeural",
        "gender": "male",
        "style": "成熟",
        "description": "成熟男声，适合旁白、成熟角色"
    },
    "yunxia": {
        "voice": "zh-CN-YunxiaNeural",
        "gender": "male",
        "style": "可爱",
        "description": "可爱男声，适合小孩、萌系角色"
    },
}

# 默认角色-语音映射模板
DEFAULT_VOICE_MAPPINGS = {
    "旁白": "xiaoxiao",      # 旁白使用温暖女声
    "narrator": "xiaoxiao",
    "default": "yunxi",      # 默认使用少年声
}

# 情绪-参数映射表
# 根据场景情绪自动调整语速、音调和音量
# 注意：参数变化要温和，避免同一角色听起来像不同的人
# volume 参数用于后处理阶段的音量调整
#
# effects 字段用于 ffmpeg 后处理增强：
#   - tempo: 变速 (0.5-2.0)，不影响音调
#   - pitch_shift: 变调 (0.8-1.2)，使用 rubberband
#   - vibrato: 颤音效果 {"f": 频率, "d": 深度}
#   - echo: 回声效果 {"delay": 延迟ms, "decay": 衰减}
#   - filter: 滤波器 {"type": "lowpass"/"highpass", "freq": 频率}
MOOD_PARAMETERS = {
    # === 基础情绪 ===
    "neutral": {
        "rate": "+0%", "pitch": "+0Hz", "volume": "+0%", "description": "中性",
        "effects": {}
    },
    "happy": {
        "rate": "+5%", "pitch": "+5Hz", "volume": "+5%", "description": "开心",
        "effects": {"tempo": 1.03}
    },
    "sad": {
        "rate": "-8%", "pitch": "-5Hz", "volume": "-5%", "description": "悲伤",
        "effects": {"tempo": 0.95, "pitch_shift": 0.97}
    },
    "angry": {
        "rate": "+0%", "pitch": "+0Hz", "volume": "+15%", "description": "愤怒",
        "effects": {"tempo": 1.0, "pitch_shift": 1.08}  # 高音调，有力
    },
    "fearful": {
        "rate": "+0%", "pitch": "+0Hz", "volume": "-3%", "description": "恐惧",
        "effects": {"tempo": 1.05, "vibrato": {"f": 6, "d": 0.2}}  # 颤抖效果
    },

    # === 复合情绪 ===
    "excited": {
        "rate": "+10%", "pitch": "+8Hz", "volume": "+8%", "description": "激动",
        "effects": {"tempo": 1.05}
    },
    "tender": {
        "rate": "-5%", "pitch": "+3Hz", "volume": "-5%", "description": "温柔",
        "effects": {"tempo": 0.95, "pitch_shift": 0.98}
    },
    "melancholy": {
        "rate": "-10%", "pitch": "-8Hz", "volume": "-8%", "description": "忧郁",
        "effects": {"tempo": 0.92, "pitch_shift": 0.95}
    },
    "romantic": {
        "rate": "-5%", "pitch": "+5Hz", "volume": "-3%", "description": "浪漫",
        "effects": {"tempo": 0.95}
    },
    "warm": {
        "rate": "-3%", "pitch": "+2Hz", "volume": "+0%", "description": "温暖",
        "effects": {}
    },
    "love": {
        "rate": "-5%", "pitch": "+3Hz", "volume": "-3%", "description": "告白",
        "effects": {"tempo": 0.93}
    },

    # === 紧张系列 ===
    "tense": {
        "rate": "+5%", "pitch": "+3Hz", "volume": "+0%", "description": "紧张",
        "effects": {"tempo": 1.05}
    },
    "urgent": {
        "rate": "+12%", "pitch": "+5Hz", "volume": "+5%", "description": "紧急",
        "effects": {"tempo": 1.15}
    },
    "chase": {
        "rate": "+0%", "pitch": "+0Hz", "volume": "+5%", "description": "追逐",
        "effects": {"tempo": 1.25}  # 非常快，喘息感
    },
    "danger": {
        "rate": "+0%", "pitch": "+0Hz", "volume": "+18%", "description": "危机",
        "effects": {"tempo": 1.0, "pitch_shift": 1.12}  # 高音警报
    },
    "suspense": {
        "rate": "+3%", "pitch": "+2Hz", "volume": "-3%", "description": "悬疑",
        "effects": {"tempo": 0.98}
    },

    # === 悲伤系列 ===
    "farewell": {
        "rate": "-8%", "pitch": "-5Hz", "volume": "-5%", "description": "离别",
        "effects": {"tempo": 0.93, "pitch_shift": 0.96}
    },
    "loss": {
        "rate": "-12%", "pitch": "-8Hz", "volume": "-8%", "description": "失落",
        "effects": {"tempo": 0.90, "pitch_shift": 0.94}
    },
    "regret": {
        "rate": "-10%", "pitch": "-5Hz", "volume": "-5%", "description": "悔恨",
        "effects": {"tempo": 0.92}
    },

    # === 叙事风格 ===
    "narration": {
        "rate": "-3%", "pitch": "+0Hz", "volume": "+0%", "description": "旁白",
        "effects": {}
    },
    "mysterious": {
        "rate": "-5%", "pitch": "-3Hz", "volume": "-3%", "description": "神秘",
        "effects": {"tempo": 0.95, "pitch_shift": 0.92, "filter": {"type": "lowpass", "freq": 3500}}
    },
    "epic": {
        "rate": "-8%", "pitch": "-5Hz", "volume": "+5%", "description": "史诗",
        "effects": {"tempo": 0.92, "pitch_shift": 0.95, "echo": {"delay": 60, "decay": 0.25}}
    },
    "solemn": {
        "rate": "-10%", "pitch": "-8Hz", "volume": "+3%", "description": "庄重",
        "effects": {"tempo": 0.90, "pitch_shift": 0.93}
    },
    "memory": {
        "rate": "-5%", "pitch": "+0Hz", "volume": "-5%", "description": "回忆",
        "effects": {"tempo": 0.95, "filter": {"type": "lowpass", "freq": 4000}, "echo": {"delay": 40, "decay": 0.2}}
    },

    # === 平静系列 ===
    "calm": {
        "rate": "+0%", "pitch": "+0Hz", "volume": "-10%", "description": "平静",
        "effects": {"tempo": 0.90, "pitch_shift": 0.95}  # 慢、低、轻
    },
    "peaceful": {
        "rate": "-3%", "pitch": "+0Hz", "volume": "-3%", "description": "宁静",
        "effects": {"tempo": 0.95}
    },

    # === 欢快系列 ===
    "joyful": {
        "rate": "+8%", "pitch": "+8Hz", "volume": "+8%", "description": "欢乐",
        "effects": {"tempo": 1.05, "pitch_shift": 1.02}
    },
    "playful": {
        "rate": "+5%", "pitch": "+5Hz", "volume": "+3%", "description": "俏皮",
        "effects": {"tempo": 1.03}
    },

    # === 战斗/动作 ===
    "battle": {
        "rate": "+0%", "pitch": "+0Hz", "volume": "+12%", "description": "战斗",
        "effects": {"tempo": 1.15, "pitch_shift": 1.03}  # 快速激烈
    },
    "surprise": {
        "rate": "+8%", "pitch": "+10Hz", "volume": "+5%", "description": "惊讶",
        "effects": {"tempo": 1.08}
    },

    # === 特殊效果 ===
    "whisper": {
        "rate": "-5%", "pitch": "+0Hz", "volume": "-15%", "description": "低语",
        "effects": {"tempo": 0.92, "filter": {"type": "highpass", "freq": 300}}
    },
    "dream": {
        "rate": "-8%", "pitch": "+0Hz", "volume": "-8%", "description": "梦境",
        "effects": {"tempo": 0.90, "echo": {"delay": 80, "decay": 0.3}, "filter": {"type": "lowpass", "freq": 3000}}
    },
    "announcement": {
        "rate": "-3%", "pitch": "+0Hz", "volume": "+10%", "description": "宣告",
        "effects": {"echo": {"delay": 50, "decay": 0.2}}
    },
}

# 默认情绪参数
DEFAULT_MOOD_PARAMS = {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%", "description": "默认", "effects": {}}

# ============================================================================
# FFmpeg 后处理效果系统
# ============================================================================
#
# 使用 ffmpeg 音频滤镜对 Edge-TTS 生成的配音进行后处理，
# 实现更精细的情绪表达控制。
# ============================================================================

# 缓存 rubberband 可用性检查结果
_rubberband_available = None


def check_rubberband_available() -> bool:
    """检查 ffmpeg 是否支持 rubberband 滤镜

    Returns:
        是否可用
    """
    global _rubberband_available
    if _rubberband_available is not None:
        return _rubberband_available

    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True, text=True, timeout=10
        )
        _rubberband_available = "rubberband" in result.stdout
        if not _rubberband_available:
            print("提示: ffmpeg 未启用 rubberband 滤镜，变调效果将使用 asetrate+aresample 替代")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        _rubberband_available = False

    return _rubberband_available


def build_effect_filter_chain(effects: dict, sample_rate: int = 44100) -> str:
    """根据 effects 参数构建 ffmpeg 滤镜链

    Args:
        effects: 效果参数字典，可包含：
            - tempo: 变速 (0.5-2.0)，不影响音调
            - pitch_shift: 变调 (0.8-1.2)
            - vibrato: 颤音 {"f": 频率, "d": 深度}
            - echo: 回声 {"delay": 延迟ms, "decay": 衰减}
            - filter: 滤波 {"type": "lowpass"/"highpass", "freq": 频率}
        sample_rate: 采样率

    Returns:
        ffmpeg 滤镜链字符串，如 "atempo=1.2,rubberband=pitch=1.1"
    """
    if not effects:
        return ""

    filters = []

    # 变速（不变调）- 使用 atempo
    tempo = effects.get("tempo", 1.0)
    if tempo != 1.0:
        # atempo 范围 0.5-2.0，超出需要级联
        if tempo > 2.0:
            # 拆分为多个 atempo
            filters.append("atempo=2.0")
            remaining = tempo / 2.0
            while remaining > 2.0:
                filters.append("atempo=2.0")
                remaining /= 2.0
            if remaining != 1.0:
                filters.append(f"atempo={remaining:.3f}")
        elif tempo < 0.5:
            # 拆分为多个 atempo
            filters.append("atempo=0.5")
            remaining = tempo / 0.5
            while remaining < 0.5:
                filters.append("atempo=0.5")
                remaining /= 0.5
            if remaining != 1.0:
                filters.append(f"atempo={remaining:.3f}")
        else:
            filters.append(f"atempo={tempo:.3f}")

    # 变调 - 优先使用 rubberband，否则用 asetrate+aresample
    pitch_shift = effects.get("pitch_shift", 1.0)
    if pitch_shift != 1.0:
        if check_rubberband_available():
            # 使用 rubberband（高质量变调）
            filters.append(f"rubberband=pitch={pitch_shift:.3f}")
        else:
            # 回退方案：asetrate 改变采样率 + aresample 恢复采样率
            # 这会同时改变速度，需要用 atempo 补偿
            new_rate = int(sample_rate * pitch_shift)
            filters.append(f"asetrate={new_rate}")
            filters.append(f"aresample={sample_rate}")
            # 补偿速度变化
            if pitch_shift != 1.0:
                compensation = 1.0 / pitch_shift
                if 0.5 <= compensation <= 2.0:
                    filters.append(f"atempo={compensation:.3f}")

    # 颤音（恐惧/紧张效果）
    vibrato = effects.get("vibrato")
    if vibrato:
        f = vibrato.get("f", 5)  # 频率 Hz
        d = vibrato.get("d", 0.3)  # 深度 0-1
        filters.append(f"vibrato=f={f}:d={d}")

    # 回声（史诗/空旷效果）
    echo = effects.get("echo")
    if echo:
        delay = echo.get("delay", 50)  # 延迟 ms
        decay = echo.get("decay", 0.3)  # 衰减 0-1
        # aecho 参数：in_gain:out_gain:delays:decays
        filters.append(f"aecho=0.8:0.7:{delay}:{decay}")

    # 滤波器
    audio_filter = effects.get("filter")
    if audio_filter:
        filter_type = audio_filter.get("type", "lowpass")
        freq = audio_filter.get("freq", 3000)
        if filter_type == "lowpass":
            filters.append(f"lowpass=f={freq}")
        elif filter_type == "highpass":
            filters.append(f"highpass=f={freq}")
        elif filter_type == "bandpass":
            # 带通需要两个参数
            low = audio_filter.get("low", 300)
            high = audio_filter.get("high", 3000)
            filters.append(f"highpass=f={low}")
            filters.append(f"lowpass=f={high}")

    return ",".join(filters) if filters else ""


def apply_segment_effects(input_path: str, output_path: str, effects: dict) -> bool:
    """对单个音频片段应用 ffmpeg 效果

    用于处理效果标记（如 [echo], [vibrato]）标记的片段。
    在 TTS 生成后、拼接前应用效果。

    Args:
        input_path: 输入音频路径
        output_path: 输出音频路径
        effects: 效果参数字典，可包含：
            - echo: {"delay": ms, "decay": 0-1}
            - vibrato: {"f": Hz, "d": 0-1}
            - filter: {"type": "lowpass"/"highpass", "freq": Hz}
            - tempo: float (0.5-2.0)

    Returns:
        是否成功
    """
    import shutil

    if not effects:
        # 没有效果，直接复制
        shutil.copy(input_path, output_path)
        return True

    try:
        filter_chain = build_effect_filter_chain(effects)
        if not filter_chain:
            shutil.copy(input_path, output_path)
            return True

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", filter_chain,
            "-ar", "44100", "-ac", "1",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"警告: ffmpeg 效果处理失败: {result.stderr[:200]}")
            # 回退：直接复制
            shutil.copy(input_path, output_path)
            return True  # 返回 True 以继续流程

        return True

    except FileNotFoundError:
        print("警告: ffmpeg 未安装，跳过效果处理")
        shutil.copy(input_path, output_path)
        return True
    except Exception as e:
        print(f"效果处理失败: {e}")
        return False


# ============================================================================
# 节奏标记系统 (Rhythm Marker System)
# ============================================================================
#
# 支持在旁白文本中使用标记语法控制词级别的节奏变化：
# - [fast]...[/fast]       加速 +15%
# - [slow]...[/slow]       减速 -15%
# - [emphasis]...[/emphasis] 重读（稍慢+稍响）
# - [pause:Nms]            停顿 N 毫秒
# - [pitch:+N]...[/pitch]  音调变化
#
# 技术实现：分段生成 + ffmpeg 音频拼接
# ============================================================================

# 节奏标记参数配置
RHYTHM_MARKERS = {
    "fast": {"rate": "+15%", "pitch": "+0Hz", "volume": "+0%"},
    "slow": {"rate": "-15%", "pitch": "+0Hz", "volume": "+0%"},
    "emphasis": {"rate": "-5%", "pitch": "+0Hz", "volume": "+10%"},
}

# 标记正则表达式
RHYTHM_MARKER_PATTERN = re.compile(
    r'\[(?P<tag>fast|slow|emphasis)\](?P<content>.*?)\[/(?P=tag)\]|'
    r'\[pause:(?P<pause>\d+)(?:ms)?\]|'
    r'\[pitch:(?P<pitch>[+-]?\d+)\](?P<pitch_content>.*?)\[/pitch\]',
    re.DOTALL
)


def convert_rhythm_to_ssml(text: str, base_rate: str = "+0%", base_pitch: str = "+0Hz") -> str:
    """将节奏标记转换为 SSML 格式

    使用 SSML 的 <prosody> 和 <break> 标签，让 TTS 自然朗读整句话，
    而不是拆分成多个片段。这样可以避免片段之间的不自然停顿。

    注意：Edge-TTS 会自动添加外层 <speak> 和 <prosody> 标签，
    所以这里只需要转换内部的节奏标记。

    Args:
        text: 包含节奏标记的文本
        base_rate: 基础语速
        base_pitch: 基础音调

    Returns:
        包含 SSML 标签的文本（不含外层 <speak>）

    示例:
        >>> convert_rhythm_to_ssml("成为[emphasis]宝可梦大师[/emphasis]")
        '成为<prosody rate="-5%" pitch="+2Hz">宝可梦大师</prosody>'
    """
    result = text

    # 转换 [fast]...[/fast] -> <prosody rate="...">...</prosody>
    result = re.sub(
        r'\[fast\](.*?)\[/fast\]',
        lambda m: f'<prosody rate="+15%">{m.group(1)}</prosody>',
        result,
        flags=re.DOTALL
    )

    # 转换 [slow]...[/slow]
    result = re.sub(
        r'\[slow\](.*?)\[/slow\]',
        lambda m: f'<prosody rate="-15%">{m.group(1)}</prosody>',
        result,
        flags=re.DOTALL
    )

    # 转换 [emphasis]...[/emphasis] -> <prosody rate="-5%" pitch="+2Hz">...</prosody>
    result = re.sub(
        r'\[emphasis\](.*?)\[/emphasis\]',
        lambda m: f'<prosody rate="-5%" pitch="+2Hz">{m.group(1)}</prosody>',
        result,
        flags=re.DOTALL
    )

    # 转换 [pitch:+N]...[/pitch]
    result = re.sub(
        r'\[pitch:([+-]?\d+)\](.*?)\[/pitch\]',
        lambda m: f'<prosody pitch="{m.group(1)}Hz">{m.group(2)}</prosody>',
        result,
        flags=re.DOTALL
    )

    # 转换 [pause:Nms] -> <break time="Nms"/>
    result = re.sub(
        r'\[pause:(\d+)(?:ms)?\]',
        r'<break time="\1ms"/>',
        result
    )

    # 移除效果标记（这些需要后处理，不能用 SSML 实现）
    result = re.sub(r'\[(?:echo|vibrato|lowpass|highpass)\](.*?)\[/(?:echo|vibrato|lowpass|highpass)\]', r'\1', result, flags=re.DOTALL)
    result = re.sub(r'\[tempo:[\d.]+\](.*?)\[/tempo\]', r'\1', result, flags=re.DOTALL)

    # 不添加外层 <speak>，Edge-TTS 会自动添加
    return result


def has_pause_markers(text: str) -> bool:
    """检查文本是否包含 pause 标记（需要拆分处理）"""
    return bool(re.search(r'\[pause:\d+(?:ms)?\]', text))


def has_effect_markers(text: str) -> bool:
    """检查文本是否包含效果标记（需要 ffmpeg 后处理）"""
    return bool(EFFECT_MARKER_PATTERN.search(text))

# ============================================================================
# FFmpeg 效果标记系统 (Effect Marker System)
# ============================================================================
#
# 支持在旁白文本中使用 ffmpeg 效果标记：
# - [echo]文本[/echo]           回声效果（史诗、空旷场景）
# - [vibrato]文本[/vibrato]     颤音效果（恐惧、紧张）
# - [lowpass]文本[/lowpass]     低通滤波（回忆、梦境）
# - [highpass]文本[/highpass]   高通滤波（电话音、低语）
# - [tempo:1.2]文本[/tempo]     变速（加速/减速特定段落）
#
# 技术实现：TTS 生成后对片段应用 ffmpeg 后处理
# ============================================================================

# 效果标记正则表达式
EFFECT_MARKER_PATTERN = re.compile(
    r'\[(?P<effect>echo|vibrato|lowpass|highpass)\](?P<effect_content>.*?)\[/(?P=effect)\]|'
    r'\[tempo:(?P<tempo>[\d.]+)\](?P<tempo_content>.*?)\[/tempo\]',
    re.DOTALL
)

# 效果参数预设
EFFECT_PRESETS = {
    "echo": {"echo": {"delay": 50, "decay": 0.25}},
    "vibrato": {"vibrato": {"f": 6, "d": 0.25}},
    "lowpass": {"filter": {"type": "lowpass", "freq": 3500}},
    "highpass": {"filter": {"type": "highpass", "freq": 400}},
}


def _extract_effect_from_text(text: str) -> tuple[str, dict]:
    """从文本中提取效果标记（用于单个片段内部的效果）

    如果文本包含效果标记，返回内部文本和效果参数。
    只处理最外层的效果标记（不支持嵌套）。

    Args:
        text: 可能包含效果标记的文本

    Returns:
        (clean_text, effects) 元组
        - clean_text: 移除效果标记后的文本
        - effects: 效果参数字典（可能为空）
    """
    if not text:
        return text, {}

    # 尝试匹配效果标记
    match = EFFECT_MARKER_PATTERN.search(text)
    if not match:
        return text, {}

    effects = {}

    if match.group("effect"):
        # [echo], [vibrato], [lowpass], [highpass] 标记
        effect_type = match.group("effect")
        content = match.group("effect_content")
        effects = EFFECT_PRESETS.get(effect_type, {}).copy()

        # 替换整个匹配为内容
        before = text[:match.start()]
        after = text[match.end():]
        clean_text = before + content + after

        # 递归检查是否还有效果标记（处理串联情况）
        remaining_text, remaining_effects = _extract_effect_from_text(clean_text)
        if remaining_effects:
            # 合并效果（后面的覆盖前面的同类效果）
            effects.update(remaining_effects)
        return remaining_text, effects

    elif match.group("tempo"):
        # [tempo:N]...[/tempo] 标记
        tempo_value = float(match.group("tempo"))
        content = match.group("tempo_content")
        effects = {"tempo": tempo_value}

        before = text[:match.start()]
        after = text[match.end():]
        clean_text = before + content + after

        remaining_text, remaining_effects = _extract_effect_from_text(clean_text)
        if remaining_effects:
            effects.update(remaining_effects)
        return remaining_text, effects

    return text, {}


def _parse_effect_markers_to_segments(text: str, base_rate: str, base_pitch: str) -> list[dict]:
    """将包含效果标记的文本解析为片段列表

    用于处理没有节奏标记但有效果标记的情况。
    每个效果标记及其之间的普通文本会成为独立的片段。

    Args:
        text: 包含效果标记的文本
        base_rate: 基础语速
        base_pitch: 基础音调

    Returns:
        片段列表
    """
    if not text:
        return []

    segments = []
    last_end = 0

    for match in EFFECT_MARKER_PATTERN.finditer(text):
        # 添加标记前的普通文本
        if match.start() > last_end:
            plain_text = text[last_end:match.start()].strip()
            if plain_text:
                segments.append({
                    "text": plain_text,
                    "rate": base_rate,
                    "pitch": base_pitch,
                    "volume": "+0%"
                })

        # 处理匹配的效果标记
        if match.group("effect"):
            effect_type = match.group("effect")
            content = match.group("effect_content").strip()
            if content:
                effects = EFFECT_PRESETS.get(effect_type, {}).copy()
                segments.append({
                    "text": content,
                    "rate": base_rate,
                    "pitch": base_pitch,
                    "volume": "+0%",
                    "effects": effects
                })
        elif match.group("tempo"):
            tempo_value = float(match.group("tempo"))
            content = match.group("tempo_content").strip()
            if content:
                segments.append({
                    "text": content,
                    "rate": base_rate,
                    "pitch": base_pitch,
                    "volume": "+0%",
                    "effects": {"tempo": tempo_value}
                })

        last_end = match.end()

    # 添加最后的普通文本
    if last_end < len(text):
        plain_text = text[last_end:].strip()
        if plain_text:
            segments.append({
                "text": plain_text,
                "rate": base_rate,
                "pitch": base_pitch,
                "volume": "+0%"
            })

    return segments


def parse_rhythm_markers(text: str, base_rate: str = "+0%", base_pitch: str = "+0Hz") -> list[dict]:
    """解析节奏标记和效果标记，返回片段列表

    支持两类标记：
    1. 节奏标记（影响 TTS 参数）：
       - [fast]...[/fast]       加速 +15%
       - [slow]...[/slow]       减速 -15%
       - [emphasis]...[/emphasis] 重读
       - [pause:Nms]            停顿
       - [pitch:+N]...[/pitch]  音调变化

    2. 效果标记（TTS 后 ffmpeg 处理）：
       - [echo]...[/echo]       回声效果
       - [vibrato]...[/vibrato] 颤音效果
       - [lowpass]...[/lowpass] 低通滤波
       - [highpass]...[/highpass] 高通滤波
       - [tempo:N]...[/tempo]   变速效果

    Args:
        text: 包含标记的文本
        base_rate: 基础语速（从 mood 继承）
        base_pitch: 基础音调（从 mood 继承）

    Returns:
        片段列表，每个片段包含：
        - {"text": "...", "rate": "...", "pitch": "...", "volume": "...", "effects": {...}} 文本片段
        - {"pause": N} 静音片段（毫秒）

    示例:
        >>> parse_rhythm_markers("[echo]很久以前[/echo]，有个少年")
        [
            {"text": "很久以前", "rate": "+0%", "pitch": "+0Hz", "volume": "+0%",
             "effects": {"echo": {"delay": 50, "decay": 0.25}}},
            {"text": "，有个少年", "rate": "+0%", "pitch": "+0Hz", "volume": "+0%"}
        ]
    """
    segments = []
    last_end = 0

    for match in RHYTHM_MARKER_PATTERN.finditer(text):
        # 添加标记前的普通文本
        if match.start() > last_end:
            plain_text = text[last_end:match.start()].strip()
            if plain_text:
                # 检查普通文本中是否有效果标记
                clean_text, effects = _extract_effect_from_text(plain_text)
                if clean_text.strip():
                    segment = {
                        "text": clean_text.strip(),
                        "rate": base_rate,
                        "pitch": base_pitch,
                        "volume": "+0%"
                    }
                    if effects:
                        segment["effects"] = effects
                    segments.append(segment)

        # 处理匹配的标记
        if match.group("tag"):
            # [fast], [slow], [emphasis] 标记
            tag = match.group("tag")
            content = match.group("content").strip()
            if content:
                marker_params = RHYTHM_MARKERS[tag]
                # 检查内容中是否有效果标记
                clean_content, effects = _extract_effect_from_text(content)
                if clean_content.strip():
                    segment = {
                        "text": clean_content.strip(),
                        "rate": _combine_rate(base_rate, marker_params["rate"]),
                        "pitch": _combine_pitch(base_pitch, marker_params["pitch"]),
                        "volume": marker_params["volume"]
                    }
                    if effects:
                        segment["effects"] = effects
                    segments.append(segment)
        elif match.group("pause"):
            # [pause:Nms] 标记
            pause_ms = int(match.group("pause"))
            segments.append({"pause": pause_ms})
        elif match.group("pitch"):
            # [pitch:+N]...[/pitch] 标记
            pitch_delta = match.group("pitch")
            content = match.group("pitch_content").strip()
            if content:
                clean_content, effects = _extract_effect_from_text(content)
                if clean_content.strip():
                    segment = {
                        "text": clean_content.strip(),
                        "rate": base_rate,
                        "pitch": _combine_pitch(base_pitch, f"{pitch_delta}Hz"),
                        "volume": "+0%"
                    }
                    if effects:
                        segment["effects"] = effects
                    segments.append(segment)

        last_end = match.end()

    # 添加最后的普通文本
    if last_end < len(text):
        plain_text = text[last_end:].strip()
        if plain_text:
            # 检查是否有效果标记需要解析为多个片段
            if EFFECT_MARKER_PATTERN.search(plain_text):
                # 使用效果标记解析器生成多个片段
                effect_segments = _parse_effect_markers_to_segments(plain_text, base_rate, base_pitch)
                segments.extend(effect_segments)
            else:
                # 无效果标记，作为单个片段
                segments.append({
                    "text": plain_text,
                    "rate": base_rate,
                    "pitch": base_pitch,
                    "volume": "+0%"
                })

    # 如果没有任何节奏标记，尝试解析纯效果标记
    if not segments and text.strip():
        # 检查是否有效果标记
        if EFFECT_MARKER_PATTERN.search(text):
            # 使用专门的效果标记解析器，生成多个片段
            segments = _parse_effect_markers_to_segments(text.strip(), base_rate, base_pitch)
        else:
            # 无任何标记，作为单个片段
            segments.append({
                "text": text.strip(),
                "rate": base_rate,
                "pitch": base_pitch,
                "volume": "+0%"
            })

    return segments


def _combine_rate(base: str, delta: str) -> str:
    """合并两个 rate 值

    Args:
        base: 基础 rate，如 "+5%" 或 "-10%"
        delta: 增量 rate，如 "+15%" 或 "-15%"

    Returns:
        合并后的 rate，如 "+20%"
    """
    base_val = int(base.replace("%", "").replace("+", ""))
    delta_val = int(delta.replace("%", "").replace("+", ""))
    combined = base_val + delta_val
    # 限制范围 [-50%, +50%]
    combined = max(-50, min(50, combined))
    return f"{'+' if combined >= 0 else ''}{combined}%"


def _combine_pitch(base: str, delta: str) -> str:
    """合并两个 pitch 值

    Args:
        base: 基础 pitch，如 "+5Hz" 或 "-10Hz"
        delta: 增量 pitch，如 "+10Hz" 或 "-5Hz"

    Returns:
        合并后的 pitch，如 "+15Hz"
    """
    base_val = int(base.replace("Hz", "").replace("+", ""))
    delta_val = int(delta.replace("Hz", "").replace("+", ""))
    combined = base_val + delta_val
    # 限制范围 [-50Hz, +50Hz]
    combined = max(-50, min(50, combined))
    return f"{'+' if combined >= 0 else ''}{combined}Hz"


def has_rhythm_markers(text: str) -> bool:
    """检查文本是否包含节奏标记或效果标记"""
    return bool(RHYTHM_MARKER_PATTERN.search(text) or EFFECT_MARKER_PATTERN.search(text))


def generate_silence(duration_ms: int, output_path: str) -> bool:
    """使用 ffmpeg 生成静音片段

    Args:
        duration_ms: 静音时长（毫秒）
        output_path: 输出文件路径

    Returns:
        是否成功
    """
    try:
        duration_sec = duration_ms / 1000.0
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=mono",
            "-t", str(duration_sec),
            "-ar", "44100",
            "-ac", "1",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"生成静音片段失败: {e}")
        return False
    except FileNotFoundError:
        print("警告: ffmpeg 未安装")
        return False


def trim_audio_end(input_path: str, output_path: str, trim_ms: int = 150) -> bool:
    """裁剪音频尾部固定时长

    简单直接地裁剪尾部的固定毫秒数，避免 silenceremove 的不确定性。
    Edge-TTS 通常在末尾添加约 100-200ms 的静音。

    Args:
        input_path: 输入音频路径
        output_path: 输出音频路径
        trim_ms: 要裁剪的尾部毫秒数

    Returns:
        是否成功
    """
    try:
        # 获取音频时长
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', input_path],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())

        # 计算新时长
        new_duration = max(0.1, duration - trim_ms / 1000.0)

        # 裁剪
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-t", str(new_duration),
            "-ar", "44100", "-ac", "1",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return True

    except Exception:
        import shutil
        shutil.copy(input_path, output_path)
        return True


def trim_silence(input_path: str, output_path: str, threshold_db: float = -50, min_duration: float = 0.15) -> bool:
    """去除音频尾部的静音（使用固定裁剪替代）

    Args:
        input_path: 输入音频路径
        output_path: 输出音频路径
        threshold_db: 未使用
        min_duration: 未使用

    Returns:
        是否成功
    """
    # 使用固定裁剪 150ms，比 silenceremove 更可控
    return trim_audio_end(input_path, output_path, trim_ms=150)


def trim_silence_old(input_path: str, output_path: str, threshold_db: float = -50, min_duration: float = 0.15) -> bool:
    """去除音频尾部的静音（旧版本，使用 silenceremove）

    Args:
        input_path: 输入音频路径
        output_path: 输出音频路径
        threshold_db: 静音阈值（dB）
        min_duration: 最小静音时长（秒）

    Returns:
        是否成功
    """
    try:
        # 只去除尾部静音，保留开头
        filter_chain = (
            f"silenceremove=stop_periods=-1:stop_duration={min_duration}:stop_threshold={threshold_db}dB"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-af", filter_chain,
            "-ar", "44100",
            "-ac", "1",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # 如果失败，直接复制原文件
            import shutil
            shutil.copy(input_path, output_path)
        return True

    except Exception:
        # 失败时直接复制
        import shutil
        shutil.copy(input_path, output_path)
        return True


def concat_audio_segments(segment_paths: list[str], output_path: str, crossfade_ms: int = 10, trim_silence_enabled: bool = True) -> bool:
    """使用 ffmpeg 拼接所有音频片段

    Args:
        segment_paths: 音频片段文件路径列表
        output_path: 输出文件路径
        crossfade_ms: 交叉淡化时长（毫秒），用于平滑片段衔接
        trim_silence_enabled: 是否去除每个片段首尾的静音

    Returns:
        是否成功
    """
    if not segment_paths:
        return False

    if len(segment_paths) == 1:
        # 只有一个片段，直接复制
        try:
            subprocess.run(["cp", segment_paths[0], output_path], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    try:
        # 如果启用静音裁剪，先处理每个片段
        paths_to_concat = segment_paths
        trimmed_paths = []

        if trim_silence_enabled:
            temp_trim_dir = tempfile.mkdtemp(prefix="trim_")
            for i, path in enumerate(segment_paths):
                # 检查是否是静音片段（silence_*.mp3），静音片段不需要裁剪
                if "silence_" in os.path.basename(path) or "_silence" in os.path.basename(path):
                    trimmed_paths.append(path)
                else:
                    trimmed_path = os.path.join(temp_trim_dir, f"trimmed_{i:03d}.mp3")
                    trim_silence(path, trimmed_path)
                    trimmed_paths.append(trimmed_path)
            paths_to_concat = trimmed_paths

        # 创建文件列表
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            list_file = f.name
            for path in paths_to_concat:
                # 需要转义单引号
                escaped_path = path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        # 使用 concat demuxer 拼接
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-ar", "44100",
            "-ac", "1",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        # 清理临时文件
        os.remove(list_file)
        if trim_silence_enabled and trimmed_paths:
            import shutil
            shutil.rmtree(temp_trim_dir, ignore_errors=True)

        return True

    except subprocess.CalledProcessError as e:
        print(f"音频拼接失败: {e}")
        return False
    except FileNotFoundError:
        print("警告: ffmpeg 未安装")
        return False


async def generate_segment_audio(
    segment: dict,
    voice: str,
    output_path: str
) -> bool:
    """为单个片段生成音频

    如果片段包含效果标记（effects 字段），会在 TTS 生成后应用 ffmpeg 效果。

    Args:
        segment: 片段数据，包含：
            - text/rate/pitch/volume: TTS 参数
            - effects: 可选的 ffmpeg 效果参数（来自效果标记）
            - pause: 静音时长（毫秒）
        voice: 语音名称
        output_path: 输出文件路径

    Returns:
        是否成功
    """
    if "pause" in segment:
        # 生成静音
        return generate_silence(segment["pause"], output_path)

    if "text" not in segment or not segment["text"]:
        return False

    # 检查是否有片段级效果
    segment_effects = segment.get("effects", {})

    try:
        import edge_tts

        text = process_text_for_pause(segment["text"])
        rate = segment.get("rate", "+0%")
        pitch = segment.get("pitch", "+0Hz")
        # volume 目前 edge-tts 不支持单独设置，但我们记录它用于后处理
        # volume = segment.get("volume", "+0%")

        if segment_effects:
            # 有效果标记：先生成到临时文件，再应用效果
            temp_path = output_path.replace(".mp3", "_raw.mp3")
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(temp_path)

            # 应用片段效果
            success = apply_segment_effects(temp_path, output_path, segment_effects)

            # 清理临时文件
            try:
                os.remove(temp_path)
            except OSError:
                pass

            return success
        else:
            # 无效果标记：直接生成到目标路径
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(output_path)
            return True

    except Exception as e:
        print(f"生成片段音频失败: {e}")
        return False


def strip_all_markers(text: str) -> str:
    """移除所有节奏和效果标记，只保留纯文本和 pause

    Args:
        text: 包含标记的文本

    Returns:
        移除标记后的文本（保留 pause）
    """
    result = text

    # 移除节奏标记，保留内容
    result = re.sub(r'\[(?:fast|slow|emphasis)\](.*?)\[/(?:fast|slow|emphasis)\]', r'\1', result, flags=re.DOTALL)
    result = re.sub(r'\[pitch:[+-]?\d+\](.*?)\[/pitch\]', r'\1', result, flags=re.DOTALL)

    # 移除效果标记，保留内容
    result = re.sub(r'\[(?:echo|vibrato|lowpass|highpass)\](.*?)\[/(?:echo|vibrato|lowpass|highpass)\]', r'\1', result, flags=re.DOTALL)
    result = re.sub(r'\[tempo:[\d.]+\](.*?)\[/tempo\]', r'\1', result, flags=re.DOTALL)

    return result


async def generate_audio_with_rhythm(
    text: str,
    voice: str,
    output_path: str,
    base_rate: str = "+0%",
    base_pitch: str = "+0Hz",
    postprocess: bool = True,
    effects: dict = None
) -> bool:
    """生成配音音频

    策略：
    1. 移除所有节奏/效果标记（Edge-TTS 不支持内联 SSML）
    2. 只保留 [pause:Nms] 用于插入停顿
    3. 使用整句的 rate/pitch（从 mood 继承）保持语音连贯

    Args:
        text: 包含标记的文本
        voice: 语音名称
        output_path: 输出路径
        base_rate: 基础语速（从 mood 继承）
        base_pitch: 基础音调（从 mood 继承）
        postprocess: 是否后处理
        effects: 情绪效果参数

    Returns:
        是否成功
    """
    # 移除节奏/效果标记，只保留文本和 pause
    clean_text = strip_all_markers(text)

    # 检查是否有 pause 标记
    if not has_pause_markers(clean_text):
        # 无 pause：直接生成整句
        return await generate_audio_with_postprocess(
            clean_text, voice, output_path,
            base_rate, base_pitch, postprocess, effects
        )

    # 有 pause：需要分段处理
    # 用 pause 标记分割文本
    parts = re.split(r'(\[pause:\d+(?:ms)?\])', clean_text)

    temp_dir = tempfile.mkdtemp(prefix="manga_audio_")
    segment_paths = []

    try:
        for i, part in enumerate(parts):
            if not part.strip():
                continue

            segment_path = os.path.join(temp_dir, f"segment_{i:03d}.mp3")

            # 检查是否是 pause 标记
            pause_match = re.match(r'\[pause:(\d+)(?:ms)?\]', part)
            if pause_match:
                pause_ms = int(pause_match.group(1))
                success = generate_silence(pause_ms, segment_path)
            else:
                # 普通文本
                try:
                    import edge_tts
                    communicate = edge_tts.Communicate(part.strip(), voice, rate=base_rate, pitch=base_pitch)
                    await communicate.save(segment_path)
                    success = True
                except Exception as e:
                    print(f"生成片段音频失败: {e}")
                    success = False

            if success and os.path.exists(segment_path):
                segment_paths.append(segment_path)

        if not segment_paths:
            return False

        # 拼接（不裁剪静音，因为现在是完整句子）
        if postprocess:
            concat_path = os.path.join(temp_dir, "concat_raw.mp3")
            if concat_audio_segments(segment_paths, concat_path, trim_silence_enabled=False):
                normalize_audio(concat_path, output_path, effects=effects)
            else:
                return False
        else:
            concat_audio_segments(segment_paths, output_path, trim_silence_enabled=False)

        return True

    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass


# ============================================================================
# 情绪渐变系统 (Emotion Gradient System)
# ============================================================================
#
# 在长文本中实现情绪的自然过渡，避免突然的情绪跳跃。
# 通过将文本分段并对每段应用不同强度的情绪参数来实现。
# ============================================================================


def split_text_into_segments(text: str, num_segments: int = 3) -> list[str]:
    """将文本分成指定数量的段落

    按句子边界（。！？）分割，然后合并成指定数量的段落。

    Args:
        text: 原始文本
        num_segments: 目标段落数

    Returns:
        段落列表
    """
    if not text:
        return []

    # 按句子分割（保留分隔符）
    sentences = re.split(r'([。！？])', text)

    # 重新组合句子（将分隔符附加到前面的文本）
    full_sentences = []
    for i in range(0, len(sentences) - 1, 2):
        sentence = sentences[i]
        if i + 1 < len(sentences):
            sentence += sentences[i + 1]
        if sentence.strip():
            full_sentences.append(sentence.strip())

    # 处理最后可能没有标点的部分
    if len(sentences) % 2 == 1 and sentences[-1].strip():
        full_sentences.append(sentences[-1].strip())

    if not full_sentences:
        return [text]

    if len(full_sentences) <= num_segments:
        return full_sentences

    # 将句子合并成指定数量的段落
    sentences_per_segment = len(full_sentences) // num_segments
    segments = []

    for i in range(num_segments):
        start = i * sentences_per_segment
        if i == num_segments - 1:
            # 最后一段包含所有剩余句子
            end = len(full_sentences)
        else:
            end = start + sentences_per_segment
        segment = ''.join(full_sentences[start:end])
        if segment:
            segments.append(segment)

    return segments


def blend_mood_params(start_params: dict, end_params: dict, ratio: float) -> dict:
    """线性插值混合两个情绪参数

    Args:
        start_params: 起始情绪参数
        end_params: 结束情绪参数
        ratio: 混合比例 (0.0 = 完全起始, 1.0 = 完全结束)

    Returns:
        混合后的参数字典
    """
    def interpolate_param(start: str, end: str, ratio: float, suffix: str) -> str:
        """插值单个参数"""
        start_val = int(start.replace(suffix, "").replace("+", ""))
        end_val = int(end.replace(suffix, "").replace("+", ""))
        blended = int(start_val + (end_val - start_val) * ratio)
        return f"{'+' if blended >= 0 else ''}{blended}{suffix}"

    return {
        "rate": interpolate_param(
            start_params.get("rate", "+0%"),
            end_params.get("rate", "+0%"),
            ratio, "%"
        ),
        "pitch": interpolate_param(
            start_params.get("pitch", "+0Hz"),
            end_params.get("pitch", "+0Hz"),
            ratio, "Hz"
        ),
        "volume": interpolate_param(
            start_params.get("volume", "+0%"),
            end_params.get("volume", "+0%"),
            ratio, "%"
        ),
    }


def apply_emotion_gradient(text: str, start_mood: str, end_mood: str, num_segments: int = 3) -> list[dict]:
    """在长文本中实现情绪渐变

    将文本分成多段，每段使用渐变后的情绪参数。

    Args:
        text: 原始文本
        start_mood: 起始情绪
        end_mood: 结束情绪
        num_segments: 分段数量

    Returns:
        片段列表，每个片段包含 text, rate, pitch, volume

    示例:
        >>> segments = apply_emotion_gradient("你好。再见。", "happy", "sad", 2)
        >>> # 返回两个片段，第一个偏 happy，第二个偏 sad
    """
    start_params = MOOD_PARAMETERS.get(start_mood, DEFAULT_MOOD_PARAMS)
    end_params = MOOD_PARAMETERS.get(end_mood, DEFAULT_MOOD_PARAMS)

    segments = split_text_into_segments(text, num_segments)

    if not segments:
        return []

    result = []
    for i, segment in enumerate(segments):
        if len(segments) > 1:
            ratio = i / (len(segments) - 1)
        else:
            ratio = 0.5  # 只有一段时使用中间值

        blended = blend_mood_params(start_params, end_params, ratio)
        result.append({
            "text": segment,
            "rate": blended["rate"],
            "pitch": blended["pitch"],
            "volume": blended["volume"],
        })

    return result


async def generate_audio_with_gradient(
    text: str,
    voice: str,
    output_path: str,
    start_mood: str,
    end_mood: str,
    num_segments: int = 3,
    postprocess: bool = True,
    effects: dict = None
) -> bool:
    """使用情绪渐变生成音频

    Args:
        text: 原始文本
        voice: 语音名称
        output_path: 输出路径
        start_mood: 起始情绪
        end_mood: 结束情绪
        num_segments: 分段数量
        postprocess: 是否进行后处理
        effects: 情绪效果参数（渐变场景通常不使用，除非显式传入）

    Returns:
        是否成功
    """
    segments = apply_emotion_gradient(text, start_mood, end_mood, num_segments)

    if not segments:
        return False

    if len(segments) == 1:
        # 只有一段，直接生成
        seg = segments[0]
        await generate_audio_with_postprocess(
            seg["text"], voice, output_path,
            seg["rate"], seg["pitch"], postprocess,
            effects=effects
        )
        return True

    # 多段：分段生成后拼接
    temp_dir = tempfile.mkdtemp(prefix="manga_gradient_")
    segment_paths = []

    try:
        for i, seg in enumerate(segments):
            segment_path = os.path.join(temp_dir, f"gradient_{i:03d}.mp3")
            success = await generate_segment_audio(seg, voice, segment_path)
            if success and os.path.exists(segment_path):
                segment_paths.append(segment_path)

        if not segment_paths:
            return False

        # 拼接
        if postprocess:
            concat_path = os.path.join(temp_dir, "concat_raw.mp3")
            if concat_audio_segments(segment_paths, concat_path):
                normalize_audio(concat_path, output_path, effects=effects)
            else:
                return False
        else:
            concat_audio_segments(segment_paths, output_path)

        return True

    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass


def load_screenplay(screenplay_path: str) -> dict:
    """加载剧本"""
    with open(screenplay_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_voice_config(screenplay: dict) -> dict:
    """获取或生成语音配置

    如果剧本中已有 voice_config，使用它；
    否则根据角色自动推断语音配置。
    """
    if "voice_config" in screenplay:
        return screenplay["voice_config"]

    # 自动推断语音配置
    voice_config = {
        "旁白": "xiaoxiao",
        "narrator": "xiaoxiao",
    }

    # 从角色阶段中提取角色名
    characters = set()
    for phase in screenplay.get("character_phases", []):
        char_name = phase.get("character", "")
        if char_name:
            characters.add(char_name)

    # 为角色分配语音
    male_voices = ["yunxi", "yunjian", "yunyang"]
    female_voices = ["xiaoyi", "xiaoxiao"]

    male_idx = 0
    female_idx = 0

    for char in characters:
        # 简单的性别推断（可以扩展）
        if any(keyword in char for keyword in ["皮卡丘", "小", "妹", "女", "娘"]):
            # 对于宝可梦等非人类角色，使用可爱声音
            if "皮卡丘" in char:
                voice_config[char] = "yunxia"  # 可爱男声
            else:
                voice_config[char] = female_voices[female_idx % len(female_voices)]
                female_idx += 1
        else:
            voice_config[char] = male_voices[male_idx % len(male_voices)]
            male_idx += 1

    return voice_config


def identify_speaker(shot: dict, screenplay: dict, voice_config: dict) -> str:
    """识别镜头的说话人

    优先级：
    1. shot 中明确指定的 speaker 字段
    2. 根据 narration 内容自动推断
    3. 使用默认声音
    """
    # 1. 明确指定
    if "speaker" in shot:
        return shot["speaker"]

    narration = shot.get("narration", "")

    # 2. 根据内容推断
    # 检测角色名是否出现在旁白中（作为对话标记）
    for char_name in voice_config.keys():
        if char_name == "旁白" or char_name == "narrator":
            continue
        # 如果旁白是角色台词特征（如"皮卡丘"的"皮卡"）
        if "皮卡" in narration and "皮卡丘" in voice_config:
            return "皮卡丘"

    # 3. 检测是否为旁白（描述性内容）
    descriptive_patterns = ["这是", "那是", "只见", "忽然", "突然", "渐渐"]
    for pattern in descriptive_patterns:
        if narration.startswith(pattern):
            return "旁白"

    # 4. 默认：主角（第一个非旁白角色）
    for char_name in voice_config.keys():
        if char_name not in ["旁白", "narrator"]:
            return char_name

    return "default"


def get_mood_parameters(mood: str) -> dict:
    """根据情绪获取语音参数

    Args:
        mood: 情绪名称（英文或中文）

    Returns:
        包含 rate, pitch, volume, description 的字典
    """
    if not mood:
        return DEFAULT_MOOD_PARAMS

    mood_lower = mood.lower().strip()

    # 直接匹配
    if mood_lower in MOOD_PARAMETERS:
        return MOOD_PARAMETERS[mood_lower]

    # 中文关键词匹配
    chinese_mood_map = {
        "激动": "excited", "战斗": "battle", "惊讶": "surprise", "愤怒": "angry",
        "悲伤": "sad", "忧郁": "melancholy", "离别": "farewell", "失落": "loss",
        "温柔": "tender", "浪漫": "romantic", "温暖": "warm", "告白": "love",
        "紧张": "tense", "紧急": "urgent", "追逐": "chase", "危机": "danger", "悬疑": "suspense",
        "平静": "calm", "中性": "neutral", "旁白": "narration", "宁静": "peaceful",
        "开心": "happy", "欢乐": "joyful", "俏皮": "playful",
        "神秘": "mysterious", "庄重": "solemn", "史诗": "epic",
        "恐惧": "fearful", "悔恨": "regret",
    }

    for cn_mood, en_mood in chinese_mood_map.items():
        if cn_mood in mood_lower:
            return MOOD_PARAMETERS[en_mood]

    return DEFAULT_MOOD_PARAMS


def get_volume_adjustment(volume_str: str) -> float:
    """将音量字符串转换为 dB 调整值

    Args:
        volume_str: 音量字符串，如 "+10%", "-5%"

    Returns:
        dB 调整值
    """
    if not volume_str:
        return 0.0

    match = re.match(r'([+-]?)(\d+)%', volume_str)
    if not match:
        return 0.0

    sign, value = match.groups()
    percent = int(value)

    # 将百分比转换为 dB（大约 6dB = 2倍音量）
    # 10% ≈ 0.8dB, 20% ≈ 1.6dB
    if sign == '-':
        return -percent * 0.08
    else:
        return percent * 0.08


def process_text_for_pause(text: str) -> str:
    """处理文本，优化停顿效果

    通过调整标点符号来优化朗读效果：
    - 省略号后保持原样（自然停顿）
    - 感叹号/问号后保持原样

    Args:
        text: 原始文本

    Returns:
        处理后的文本
    """
    # edge-tts 会自动处理标点停顿，这里只做必要的清理
    # 确保省略号格式一致
    text = text.replace('...', '……')
    return text


async def generate_audio_edge_tts(
    text: str,
    voice: str,
    output_path: str,
    rate: str = "+0%",
    pitch: str = "+0Hz"
):
    """使用 edge-tts 生成语音

    Args:
        text: 要朗读的文本
        voice: 语音名称
        output_path: 输出文件路径
        rate: 语速
        pitch: 音调
    """
    import edge_tts

    # 处理文本
    processed_text = process_text_for_pause(text)

    # 使用 edge-tts 原生参数
    communicate = edge_tts.Communicate(processed_text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)


def get_audio_duration_for_fade(input_path: str) -> float:
    """获取音频时长用于淡出计算

    Args:
        input_path: 音频文件路径

    Returns:
        时长（秒），失败返回 0
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', input_path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
        return 0.0


def normalize_audio(
    input_path: str,
    output_path: str,
    target_loudness: float = -16.0,
    volume_adjust_db: float = 0.0,
    effects: dict = None
):
    """规范化音频音量 + 应用情绪效果

    使用 ffmpeg 进行音量规范化、淡入淡出和情绪效果处理。
    效果应用顺序：情绪效果 → 响度规范化 → 淡入淡出 → 音量微调

    Args:
        input_path: 输入音频路径
        output_path: 输出音频路径
        target_loudness: 目标响度（LUFS），默认 -16
        volume_adjust_db: 额外的音量调整（dB），用于情绪表达
        effects: 情绪效果参数字典（来自 MOOD_PARAMETERS 的 effects 字段）
    """
    try:
        # 获取音频时长用于淡出
        duration = get_audio_duration_for_fade(input_path)
        fade_out_duration = 0.1
        fade_out_start = max(0, duration - fade_out_duration) if duration > 0 else 0

        filters = []

        # 1. 情绪效果（先应用，避免影响响度计算）
        if effects:
            effect_chain = build_effect_filter_chain(effects)
            if effect_chain:
                filters.append(effect_chain)

        # 2. 响度规范化
        filters.append(f"loudnorm=I={target_loudness}:TP=-1.5:LRA=11")

        # 3. 淡入淡出
        filters.append("afade=t=in:st=0:d=0.05")
        if fade_out_start > 0:
            filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={fade_out_duration}")

        # 4. 音量微调
        if abs(volume_adjust_db) > 0.1:
            filters.append(f"volume={volume_adjust_db}dB")

        filter_str = ",".join(filters)

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", filter_str,
            "-ar", "44100",  # 采样率
            "-ac", "1",      # 单声道
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"音频处理失败: {e}")
        # 如果后处理失败，尝试不使用效果
        if effects:
            print("尝试回退：不使用情绪效果...")
            return normalize_audio(input_path, output_path, target_loudness, volume_adjust_db, effects=None)
        return False
    except FileNotFoundError:
        print("警告: ffmpeg 未安装，跳过音频后处理")
        return False


async def generate_audio_with_postprocess(
    text: str,
    voice: str,
    output_path: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    postprocess: bool = True,
    effects: dict = None
):
    """生成语音并进行后处理

    Args:
        text: 要朗读的文本
        voice: 语音名称
        output_path: 最终输出路径
        rate: 语速
        pitch: 音调
        postprocess: 是否进行后处理
        effects: 情绪效果参数（来自 MOOD_PARAMETERS 的 effects 字段）
    """
    if postprocess:
        # 先生成到临时文件
        temp_path = output_path.replace(".mp3", "_raw.mp3")
        await generate_audio_edge_tts(text, voice, temp_path, rate, pitch)

        # 后处理（包含情绪效果）
        if normalize_audio(temp_path, output_path, effects=effects):
            # 删除临时文件
            try:
                os.remove(temp_path)
            except OSError:
                pass
        else:
            # 后处理失败，使用原始文件
            os.rename(temp_path, output_path)
    else:
        await generate_audio_edge_tts(text, voice, output_path, rate, pitch)


def infer_mood_from_content(narration: str, action: str = "") -> str:
    """从内容推断情绪

    如果镜头没有明确的 mood 字段，根据文本内容推断。

    Args:
        narration: 旁白文本
        action: 动作描述

    Returns:
        推断的情绪名称
    """
    text = (narration + " " + action).lower()

    # 情绪关键词映射
    mood_keywords = {
        "battle": ["战斗", "攻击", "冲锋", "击", "打", "战"],
        "excited": ["激动", "兴奋", "太好了", "终于"],
        "angry": ["愤怒", "生气", "可恶", "该死", "混蛋"],
        "surprise": ["惊讶", "什么", "怎么可能", "不会吧", "竟然"],
        "sad": ["悲伤", "难过", "哭", "泪", "对不起", "抱歉"],
        "farewell": ["再见", "离别", "分开", "永别", "告别"],
        "tender": ["温柔", "轻声", "柔和", "抚摸"],
        "romantic": ["爱", "喜欢你", "心动", "脸红"],
        "tense": ["紧张", "小心", "危险", "快跑", "逃"],
        "urgent": ["快", "赶紧", "来不及", "紧急"],
        "happy": ["开心", "高兴", "太棒了", "哈哈", "笑"],
        "mysterious": ["神秘", "奇怪", "诡异", "古老"],
        "peaceful": ["平静", "宁静", "安详", "祥和"],
    }

    for mood, keywords in mood_keywords.items():
        for keyword in keywords:
            if keyword in text:
                return mood

    # 标点符号推断
    if "！" in narration and len(narration) < 20:
        return "excited"
    if "……" in narration:
        return "sad"
    if "？" in narration and "！" in narration:
        return "surprise"

    return "neutral"


async def generate_all_narrations(
    screenplay: dict,
    output_dir: str,
    voice_config: dict,
    enable_postprocess: bool = True
):
    """生成所有镜头的旁白音频

    支持三种模式：
    1. 普通模式：使用全局 mood 参数（无节奏标记）
    2. 节奏标记模式：解析 [fast]/[slow]/[emphasis]/[pause] 标记，分段生成
    3. 旁白组模式：多个镜头共享一段旁白

    Args:
        screenplay: 剧本数据
        output_dir: 输出目录
        voice_config: 语音配置
        enable_postprocess: 是否启用后处理（音量规范化、淡入淡出）

    Returns:
        (shot_info, manifest) - 镜头信息列表和音频清单
    """
    audio_dir = os.path.join(output_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    tasks = []
    shot_info = []
    rhythm_count = 0  # 统计使用节奏标记的镜头数
    group_count = 0   # 统计旁白组数量

    # 识别旁白组
    narration_info = identify_narration_groups(screenplay)
    groups = narration_info["groups"]
    processed_groups = set()

    for loc in screenplay.get("locations", []):
        for shot in loc.get("shots", []):
            shot_id = shot["shot_id"]
            narration_group = shot.get("narration_group")

            # 处理旁白组
            if narration_group:
                if narration_group in processed_groups:
                    # 已处理过的组，跳过
                    continue

                group_data = groups.get(narration_group, {})
                narration = group_data.get("narration", "")

                if not narration:
                    continue

                processed_groups.add(narration_group)
                group_count += 1

                speaker = identify_speaker(shot, screenplay, voice_config)
                voice_key = voice_config.get(speaker, voice_config.get("default", "yunxi"))
                voice_info = AVAILABLE_VOICES.get(voice_key, AVAILABLE_VOICES["yunxi"])
                voice_name = voice_info["voice"]

                mood = shot.get("mood", "")
                if not mood:
                    mood = infer_mood_from_content(narration, shot.get("action", ""))

                mood_params = get_mood_parameters(mood)
                rate = mood_params["rate"]
                pitch = mood_params["pitch"]
                mood_desc = mood_params["description"]
                effects = mood_params.get("effects", {})

                output_path = os.path.join(audio_dir, f"narration_group_{narration_group}.mp3")

                uses_rhythm = has_rhythm_markers(narration)
                if uses_rhythm:
                    rhythm_count += 1

                shot_info.append({
                    "shot_id": f"group:{narration_group}",
                    "speaker": speaker,
                    "voice": voice_key,
                    "mood": mood_desc,
                    "rate": rate,
                    "pitch": pitch,
                    "rhythm": uses_rhythm,
                    "group": True,
                    "group_shots": group_data.get("shots", []),
                    "narration": narration[:30] + "..." if len(narration) > 30 else narration,
                    "effects": bool(effects)  # 标记是否使用了情绪效果
                })

                if uses_rhythm:
                    tasks.append(generate_audio_with_rhythm(
                        narration, voice_name, output_path, rate, pitch,
                        postprocess=enable_postprocess,
                        effects=effects
                    ))
                else:
                    tasks.append(generate_audio_with_postprocess(
                        narration, voice_name, output_path, rate, pitch,
                        postprocess=enable_postprocess,
                        effects=effects
                    ))

                continue

            # 处理独立旁白
            narration = shot.get("narration", "")
            if not narration:
                continue

            speaker = identify_speaker(shot, screenplay, voice_config)

            # 获取语音配置
            voice_key = voice_config.get(speaker, voice_config.get("default", "yunxi"))
            voice_info = AVAILABLE_VOICES.get(voice_key, AVAILABLE_VOICES["yunxi"])
            voice_name = voice_info["voice"]

            # 获取情绪参数
            # 优先使用 shot 中明确指定的 mood
            mood = shot.get("mood", "")
            if not mood:
                # 如果没有明确的 mood，从内容推断
                mood = infer_mood_from_content(narration, shot.get("action", ""))

            mood_params = get_mood_parameters(mood)
            rate = mood_params["rate"]
            pitch = mood_params["pitch"]
            mood_desc = mood_params["description"]
            effects = mood_params.get("effects", {})

            output_path = os.path.join(audio_dir, f"narration_{shot_id}.mp3")

            # 检测是否使用节奏标记
            uses_rhythm = has_rhythm_markers(narration)
            if uses_rhythm:
                rhythm_count += 1

            shot_info.append({
                "shot_id": shot_id,
                "speaker": speaker,
                "voice": voice_key,
                "mood": mood_desc,
                "rate": rate,
                "pitch": pitch,
                "rhythm": uses_rhythm,  # 标记是否使用节奏控制
                "group": False,
                "narration": narration[:30] + "..." if len(narration) > 30 else narration,
                "effects": bool(effects)  # 标记是否使用了情绪效果
            })

            # 根据是否有节奏标记选择生成方法
            if uses_rhythm:
                # 使用节奏感知生成（分段生成 + 拼接）
                tasks.append(generate_audio_with_rhythm(
                    narration, voice_name, output_path, rate, pitch,
                    postprocess=enable_postprocess,
                    effects=effects
                ))
            else:
                # 使用普通生成
                tasks.append(generate_audio_with_postprocess(
                    narration, voice_name, output_path, rate, pitch,
                    postprocess=enable_postprocess,
                    effects=effects
                ))

    # 并发生成所有音频
    print(f"正在生成 {len(tasks)} 个音频文件...")
    print(f"  后处理: {'启用' if enable_postprocess else '禁用'}")
    if rhythm_count > 0:
        print(f"  节奏标记: {rhythm_count} 个镜头使用词级别节奏控制")
    if group_count > 0:
        print(f"  旁白组: {group_count} 个组（多图共享旁白）")

    await asyncio.gather(*tasks)

    # 生成音频清单
    manifest = generate_audio_manifest(screenplay, audio_dir, shot_info)

    # 保存清单
    manifest_path = os.path.join(audio_dir, "audio_manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"音频清单已保存: {manifest_path}")

    return shot_info, manifest


def print_voice_mapping(voice_config: dict, shot_info: list):
    """打印语音映射信息"""
    print("\n" + "=" * 80)
    print("角色语音配置")
    print("=" * 80)

    for char, voice_key in voice_config.items():
        voice_info = AVAILABLE_VOICES.get(voice_key, {})
        print(f"  {char}: {voice_key} ({voice_info.get('description', '')})")

    print("\n" + "-" * 80)
    print("镜头配音详情（含情绪参数）")
    print("-" * 80)
    print(f"{'镜头':<12} {'说话人':<8} {'语音':<8} {'情绪':<6} {'语速':<8} {'音调':<10} {'节奏':<4} {'组':<4} {'效果':<4} {'内容'}")
    print("-" * 80)

    for info in shot_info:
        rhythm_flag = "✓" if info.get('rhythm') else "-"
        group_flag = "✓" if info.get('group') else "-"
        effects_flag = "✓" if info.get('effects') else "-"
        shot_id_display = info['shot_id'][:12] if len(info['shot_id']) > 12 else info['shot_id']
        print(f"{shot_id_display:<12} {info['speaker']:<8} {info['voice']:<8} "
              f"{info.get('mood', '-'):<6} {info.get('rate', '+0%'):<8} "
              f"{info.get('pitch', '+0Hz'):<10} {rhythm_flag:<4} {group_flag:<4} {effects_flag:<4} {info['narration']}")

    print("=" * 80)

    # 情绪分布统计
    mood_counts = {}
    rhythm_count = 0
    group_count = 0
    effects_count = 0
    for info in shot_info:
        mood = info.get('mood', '默认')
        mood_counts[mood] = mood_counts.get(mood, 0) + 1
        if info.get('rhythm'):
            rhythm_count += 1
        if info.get('group'):
            group_count += 1
        if info.get('effects'):
            effects_count += 1

    if mood_counts:
        print("\n情绪分布统计:")
        for mood, count in sorted(mood_counts.items(), key=lambda x: -x[1]):
            pct = count / len(shot_info) * 100
            print(f"  {mood}: {count} ({pct:.1f}%)")

    if rhythm_count > 0:
        print(f"\n节奏标记统计:")
        print(f"  使用词级别节奏控制: {rhythm_count} 个镜头 ({rhythm_count / len(shot_info) * 100:.1f}%)")

    if group_count > 0:
        print(f"\n旁白组统计:")
        print(f"  多图共享旁白: {group_count} 个组")

    if effects_count > 0:
        print(f"\n后处理效果统计:")
        print(f"  使用ffmpeg情绪效果: {effects_count} 个镜头 ({effects_count / len(shot_info) * 100:.1f}%)")

    print("=" * 80)


def save_voice_config(screenplay_path: str, voice_config: dict):
    """保存语音配置到剧本"""
    with open(screenplay_path, 'r', encoding='utf-8') as f:
        screenplay = json.load(f)

    screenplay["voice_config"] = voice_config

    with open(screenplay_path, 'w', encoding='utf-8') as f:
        json.dump(screenplay, f, ensure_ascii=False, indent=2)

    print(f"语音配置已保存到: {screenplay_path}")


# ============================================================================
# 音频清单和时长同步功能
# ============================================================================


def get_audio_duration(audio_path: str) -> float:
    """获取音频文件时长

    Args:
        audio_path: 音频文件路径

    Returns:
        时长（秒）
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', audio_path],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def identify_narration_groups(screenplay: dict) -> dict:
    """识别旁白组

    扫描剧本，识别哪些镜头共享同一段旁白。

    Args:
        screenplay: 剧本数据

    Returns:
        {
            "groups": {
                "group_id": {
                    "shots": ["shot_id1", "shot_id2"],
                    "narration": "共享的旁白文本",
                    "first_shot": "shot_id1"  # 第一个镜头（包含旁白）
                }
            },
            "single": ["shot_id3", "shot_id4"]  # 独立旁白的镜头
        }
    """
    groups = {}
    singles = []

    for loc in screenplay.get("locations", []):
        for shot in loc.get("shots", []):
            shot_id = shot["shot_id"]
            narration_group = shot.get("narration_group")

            if narration_group:
                # 属于旁白组
                if narration_group not in groups:
                    groups[narration_group] = {
                        "shots": [],
                        "narration": "",
                        "first_shot": None
                    }

                groups[narration_group]["shots"].append(shot_id)

                # 只有组内第一个镜头有旁白文本
                if shot.get("group_position", 1) == 1 and shot.get("narration"):
                    groups[narration_group]["narration"] = shot["narration"]
                    groups[narration_group]["first_shot"] = shot_id
            elif shot.get("narration"):
                # 独立旁白
                singles.append(shot_id)

    return {
        "groups": groups,
        "single": singles
    }


def generate_audio_manifest(
    screenplay: dict,
    audio_dir: str,
    shot_info: list
) -> dict:
    """生成音频清单

    Args:
        screenplay: 剧本数据
        audio_dir: 音频目录
        shot_info: 镜头配音信息列表

    Returns:
        音频清单数据
    """
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "total_duration": 0.0,
        "entries": []
    }

    # 识别旁白组
    narration_info = identify_narration_groups(screenplay)
    groups = narration_info["groups"]
    singles = narration_info["single"]

    total_duration = 0.0

    # 处理独立旁白
    for shot_id in singles:
        audio_file = f"narration_{shot_id}.mp3"
        audio_path = os.path.join(audio_dir, audio_file)

        if os.path.exists(audio_path):
            duration = get_audio_duration(audio_path)
            total_duration += duration

            # 查找镜头信息
            shot_data = None
            for loc in screenplay.get("locations", []):
                for shot in loc.get("shots", []):
                    if shot["shot_id"] == shot_id:
                        shot_data = shot
                        break
                if shot_data:
                    break

            manifest["entries"].append({
                "id": shot_id,
                "type": "single",
                "audio_file": audio_file,
                "duration": round(duration, 2),
                "text": shot_data.get("narration", "") if shot_data else ""
            })

    # 处理旁白组
    for group_id, group_data in groups.items():
        audio_file = f"narration_group_{group_id}.mp3"
        audio_path = os.path.join(audio_dir, audio_file)

        if os.path.exists(audio_path):
            duration = get_audio_duration(audio_path)
            total_duration += duration

            shots = group_data["shots"]
            per_shot_duration = duration / len(shots) if shots else duration

            manifest["entries"].append({
                "id": group_id,
                "type": "group",
                "audio_file": audio_file,
                "duration": round(duration, 2),
                "text": group_data["narration"],
                "shots": shots,
                "per_shot_duration": round(per_shot_duration, 2)
            })

    manifest["total_duration"] = round(total_duration, 2)
    return manifest


def update_screenplay_durations(screenplay_path: str, manifest: dict) -> dict:
    """根据实际音频时长更新剧本

    Args:
        screenplay_path: 剧本文件路径
        manifest: 音频清单数据

    Returns:
        更新后的剧本数据
    """
    with open(screenplay_path, 'r', encoding='utf-8') as f:
        screenplay = json.load(f)

    # 构建时长映射
    duration_map = {}  # shot_id -> duration
    group_duration_map = {}  # group_id -> per_shot_duration

    for entry in manifest["entries"]:
        if entry["type"] == "single":
            duration_map[entry["id"]] = entry["duration"]
        elif entry["type"] == "group":
            for shot_id in entry.get("shots", []):
                group_duration_map[shot_id] = entry["per_shot_duration"]

    # 更新每个镜头的时长
    for loc in screenplay.get("locations", []):
        for shot in loc.get("shots", []):
            shot_id = shot["shot_id"]

            # 优先使用直接映射的时长
            if shot_id in duration_map:
                actual = duration_map[shot_id]
                shot["actual_duration"] = actual
                shot["display_duration"] = actual
            elif shot_id in group_duration_map:
                # 组内镜头使用平均时长
                per_shot = group_duration_map[shot_id]
                shot["actual_duration"] = per_shot
                shot["display_duration"] = per_shot

    # 保存更新后的剧本
    with open(screenplay_path, 'w', encoding='utf-8') as f:
        json.dump(screenplay, f, ensure_ascii=False, indent=2)

    print(f"剧本时长已更新: {screenplay_path}")
    return screenplay


def compare_durations(screenplay: dict, threshold: float = 0.2) -> list:
    """比对估算时长与实际时长

    Args:
        screenplay: 剧本数据
        threshold: 偏差阈值（默认 20%）

    Returns:
        偏差警告列表
    """
    warnings = []

    for loc in screenplay.get("locations", []):
        for shot in loc.get("shots", []):
            shot_id = shot["shot_id"]
            estimated = shot.get("estimated_duration", 0)
            actual = shot.get("actual_duration", 0)

            if estimated > 0 and actual > 0:
                deviation = abs(actual - estimated) / estimated
                if deviation > threshold:
                    direction = "长" if actual > estimated else "短"
                    warnings.append({
                        "shot_id": shot_id,
                        "estimated": estimated,
                        "actual": actual,
                        "deviation": round(deviation * 100, 1),
                        "message": f"镜头 {shot_id}: 实际时长比估算{direction} {deviation*100:.1f}% (估算: {estimated:.2f}s, 实际: {actual:.2f}s)"
                    })

    return warnings


def test_rhythm_parsing():
    """测试节奏标记和效果标记解析功能"""
    print("=" * 60)
    print("节奏标记 + 效果标记解析测试")
    print("=" * 60)

    test_cases = [
        # 基本节奏测试
        ("普通文本", "普通文本"),
        ("普通[fast]快速[/fast]普通", "普通 + 快速(+15%) + 普通"),
        ("为什么你就是[emphasis]不愿意[/emphasis]相信我呢", "普通 + 重读(-5%, +vol) + 普通"),
        ("[slow]慢慢地说[/slow]", "慢速(-15%)"),
        ("等一下[pause:500]好的", "普通 + 停顿500ms + 普通"),
        # 组合测试
        ("[fast]快跑！[/fast][pause:200]他们追上来了！", "快速 + 停顿 + 普通"),
        ("再见了……[slow]我的朋友[/slow]", "普通 + 慢速"),
        # 音调测试
        ("普通[pitch:+10]高音[/pitch]普通", "普通 + 音调+10Hz + 普通"),
        # === 效果标记测试 ===
        ("[echo]很久很久以前[/echo]", "回声效果"),
        ("[vibrato]害怕的声音[/vibrato]", "颤音效果"),
        ("[lowpass]模糊的回忆[/lowpass]", "低通滤波"),
        ("[highpass]电话那头[/highpass]", "高通滤波"),
        ("[tempo:1.3]快速念出来[/tempo]", "变速效果"),
        # 节奏 + 效果组合
        ("[fast][echo]史诗级快节奏[/echo][/fast]", "快速 + 回声"),
        ("[echo]很久以前[/echo]，有个[vibrato]害怕的[/vibrato]少年", "回声 + 普通 + 颤音"),
        ("[fast][tempo:1.3]极速狂飙[/tempo][/fast]", "快速 + tempo变速"),
    ]

    for text, expected_desc in test_cases:
        print(f"\n输入: {text}")
        print(f"预期: {expected_desc}")
        segments = parse_rhythm_markers(text)
        print(f"解析结果 ({len(segments)} 片段):")
        for i, seg in enumerate(segments):
            if "pause" in seg:
                print(f"  [{i}] 静音 {seg['pause']}ms")
            else:
                effects_str = ""
                if seg.get("effects"):
                    effect_names = list(seg["effects"].keys())
                    effects_str = f" effects={effect_names}"
                print(f"  [{i}] \"{seg['text']}\" rate={seg['rate']} pitch={seg['pitch']} vol={seg['volume']}{effects_str}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


async def test_moods_generation(output_dir: str, voice: str = "xiaoxiao"):
    """生成所有情绪的测试音频（含 ffmpeg 后处理效果）

    Args:
        output_dir: 输出目录
        voice: 使用的语音
    """
    print("=" * 60)
    print("情绪参数测试 - 生成各情绪的测试音频")
    print("（含 ffmpeg 后处理效果：变速/变调/颤音/回声/滤波）")
    print("=" * 60)

    # 检查 rubberband 可用性
    if check_rubberband_available():
        print("✓ rubberband 滤镜可用（高质量变调）")
    else:
        print("⚠ rubberband 不可用，将使用 asetrate+aresample 替代")

    # 测试文本
    test_text = "你好，今天天气真不错！让我们一起出发吧。"

    # 确保输出目录存在
    test_dir = os.path.join(output_dir, "mood_tests")
    os.makedirs(test_dir, exist_ok=True)

    # 获取语音 ID
    voice_info = AVAILABLE_VOICES.get(voice, AVAILABLE_VOICES["xiaoxiao"])
    voice_name = voice_info["voice"]

    print(f"\n使用语音: {voice} ({voice_info['description']})")
    print(f"测试文本: {test_text}")
    print(f"输出目录: {test_dir}")

    # 按类别组织情绪
    mood_categories = {
        "基础情绪": ["neutral", "happy", "sad", "angry", "fearful"],
        "复合情绪": ["excited", "tender", "melancholy", "romantic", "warm", "love"],
        "紧张系列": ["tense", "urgent", "chase", "danger", "suspense"],
        "悲伤系列": ["farewell", "loss", "regret"],
        "叙事风格": ["narration", "mysterious", "epic", "solemn", "memory"],
        "平静系列": ["calm", "peaceful"],
        "欢快系列": ["joyful", "playful"],
        "战斗动作": ["battle", "surprise"],
        "特殊效果": ["whisper", "dream", "announcement"],
    }

    total_count = 0
    effects_count = 0
    for category, moods in mood_categories.items():
        print(f"\n--- {category} ---")
        for mood in moods:
            params = get_mood_parameters(mood)
            effects = params.get("effects", {})
            output_path = os.path.join(test_dir, f"mood_test_{mood}.mp3")

            # 构建效果描述
            effect_desc = []
            if effects.get("tempo") and effects["tempo"] != 1.0:
                effect_desc.append(f"tempo={effects['tempo']}")
            if effects.get("pitch_shift") and effects["pitch_shift"] != 1.0:
                effect_desc.append(f"pitch={effects['pitch_shift']}")
            if effects.get("vibrato"):
                effect_desc.append("vibrato")
            if effects.get("echo"):
                effect_desc.append("echo")
            if effects.get("filter"):
                effect_desc.append(effects["filter"]["type"])

            effect_str = " [" + ", ".join(effect_desc) + "]" if effect_desc else ""
            print(f"  {mood}: rate={params['rate']} pitch={params['pitch']} vol={params['volume']}{effect_str}", end=" ")

            try:
                await generate_audio_with_postprocess(
                    test_text, voice_name, output_path,
                    params["rate"], params["pitch"],
                    postprocess=True,
                    effects=effects
                )
                print("✓")
                total_count += 1
                if effects:
                    effects_count += 1
            except Exception as e:
                print(f"✗ ({e})")

    print(f"\n" + "=" * 60)
    print(f"测试完成！生成了 {total_count} 个音频文件")
    print(f"  其中 {effects_count} 个使用了 ffmpeg 后处理效果")
    print(f"输出目录: {test_dir}")
    print("=" * 60)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python manga_generate_narration.py <output_dir> [options]")
        print("\n选项:")
        print("  --save-config     保存语音配置到剧本")
        print("  --no-postprocess  禁用音频后处理（音量规范化、淡入淡出）")
        print("  --test-rhythm     测试节奏标记解析功能")
        print("  --test-moods      生成各情绪的测试音频")
        print("\n环境变量:")
        print("  TTS_BACKEND       TTS 后端: edge (默认) 或 f5")
        print("\n示例:")
        print("  python manga_generate_narration.py output/初心之雷")
        print("  python manga_generate_narration.py output/初心之雷 --save-config")
        print("  python manga_generate_narration.py output/初心之雷 --no-postprocess")
        print("  python manga_generate_narration.py output/初心之雷 --test-rhythm")
        print("  python manga_generate_narration.py output/初心之雷 --test-moods")
        print("\n可用语音:")
        for key, info in AVAILABLE_VOICES.items():
            print(f"  {key}: {info['description']}")
        print("\n可用情绪参数 (优化版，含 volume):")
        print("  基础: neutral, happy, sad, angry, fearful")
        print("  复合: excited, tender, melancholy, romantic, warm, love")
        print("  紧张: tense, urgent, chase, danger, suspense")
        print("  悲伤: farewell, loss, regret")
        print("  叙事: narration, mysterious, epic, solemn")
        print("  平静: calm, peaceful")
        print("  欢快: joyful, playful")
        print("  战斗: battle, surprise")
        print("\n节奏标记语法 (词级别节奏控制):")
        print("  [fast]快速部分[/fast]       加速 +15%")
        print("  [slow]慢速部分[/slow]       减速 -15%")
        print("  [emphasis]重读[/emphasis]   重读 (稍慢+稍响)")
        print("  [pause:Nms]                 停顿 N 毫秒")
        print("  [pitch:+N]高音[/pitch]      音调变化 +N Hz")
        print("\n效果标记语法 (ffmpeg 后处理效果):")
        print("  [echo]文本[/echo]           回声效果 (史诗、空旷场景)")
        print("  [vibrato]文本[/vibrato]     颤音效果 (恐惧、紧张)")
        print("  [lowpass]文本[/lowpass]     低通滤波 (回忆、梦境)")
        print("  [highpass]文本[/highpass]   高通滤波 (电话音、低语)")
        print("  [tempo:N]文本[/tempo]       变速 (N=1.2 加速, N=0.8 减速)")
        print("\n示例:")
        print('  "为什么你就是[emphasis]不愿意[/emphasis]相信我呢……"')
        print('  "[fast]快跑！[/fast][pause:200]他们追上来了！"')
        print('  "[echo]很久很久以前[/echo]，在一个遥远的地方……"')
        print('  "他[vibrato]颤抖着[/vibrato]说道：我害怕……"')
        print('  "[lowpass]那是一段模糊的回忆[/lowpass]"')
        sys.exit(1)

    output_dir = sys.argv[1]
    save_config = "--save-config" in sys.argv
    enable_postprocess = "--no-postprocess" not in sys.argv
    test_rhythm = "--test-rhythm" in sys.argv
    test_moods = "--test-moods" in sys.argv

    # 测试模式
    if test_rhythm:
        test_rhythm_parsing()
        sys.exit(0)

    # 情绪测试模式
    if test_moods:
        await test_moods_generation(output_dir)
        sys.exit(0)

    screenplay_path = os.path.join(output_dir, "screenplay.json")

    if not os.path.exists(screenplay_path):
        print(f"Error: 剧本文件不存在: {screenplay_path}")
        sys.exit(1)

    # 加载剧本
    screenplay = load_screenplay(screenplay_path)
    print(f"加载剧本: {screenplay.get('title', 'Unknown')}")
    print(f"总镜头数: {screenplay.get('total_shots', '?')}")

    # 获取语音配置
    voice_config = get_voice_config(screenplay)

    # 生成所有旁白音频
    shot_info, manifest = await generate_all_narrations(
        screenplay, output_dir, voice_config,
        enable_postprocess=enable_postprocess
    )

    # 更新剧本中的实际时长
    updated_screenplay = update_screenplay_durations(screenplay_path, manifest)

    # 比对估算时长与实际时长
    warnings = compare_durations(updated_screenplay)
    if warnings:
        print(f"\n⚠️ 时长偏差警告 ({len(warnings)} 项):")
        for w in warnings:
            print(f"   {w['message']}")

    # 打印配音信息
    print_voice_mapping(voice_config, shot_info)

    # 可选：保存配置到剧本
    if save_config:
        save_voice_config(screenplay_path, voice_config)

    print(f"\n✅ 音频生成完成！")
    print(f"   音频文件: {os.path.join(output_dir, 'audio')}")
    print(f"   音频清单: {os.path.join(output_dir, 'audio', 'audio_manifest.json')}")
    print(f"   生成了 {len(shot_info)} 个音频")
    print(f"   总时长: {manifest['total_duration']:.1f} 秒 ({manifest['total_duration']/60:.1f} 分钟)")


if __name__ == "__main__":
    asyncio.run(main())
