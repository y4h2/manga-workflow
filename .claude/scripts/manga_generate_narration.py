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
# 根据场景情绪自动调整语速和音调
# 注意：参数变化要温和，避免同一角色听起来像不同的人
MOOD_PARAMETERS = {
    # 激动情绪 (语速稍快，音调稍高)
    "excited": {"rate": "+10%", "pitch": "+5Hz", "description": "激动"},
    "battle": {"rate": "+10%", "pitch": "+5Hz", "description": "战斗"},
    "surprise": {"rate": "+8%", "pitch": "+8Hz", "description": "惊讶"},
    "angry": {"rate": "+8%", "pitch": "+3Hz", "description": "愤怒"},

    # 悲伤情绪 (语速稍慢，音调稍低)
    "sad": {"rate": "-8%", "pitch": "-5Hz", "description": "悲伤"},
    "melancholy": {"rate": "-8%", "pitch": "-5Hz", "description": "忧郁"},
    "farewell": {"rate": "-5%", "pitch": "-3Hz", "description": "离别"},
    "loss": {"rate": "-8%", "pitch": "-5Hz", "description": "失落"},

    # 温柔情绪 (语速稍慢，音调略高)
    "tender": {"rate": "-5%", "pitch": "+2Hz", "description": "温柔"},
    "romantic": {"rate": "-5%", "pitch": "+2Hz", "description": "浪漫"},
    "warm": {"rate": "-3%", "pitch": "+2Hz", "description": "温暖"},
    "love": {"rate": "-5%", "pitch": "+2Hz", "description": "告白"},

    # 紧张情绪 (语速稍快，音调稍高)
    "tense": {"rate": "+8%", "pitch": "+5Hz", "description": "紧张"},
    "urgent": {"rate": "+10%", "pitch": "+5Hz", "description": "紧急"},
    "chase": {"rate": "+8%", "pitch": "+5Hz", "description": "追逐"},
    "danger": {"rate": "+8%", "pitch": "+5Hz", "description": "危机"},
    "suspense": {"rate": "+5%", "pitch": "+3Hz", "description": "悬疑"},

    # 平静情绪 (默认)
    "calm": {"rate": "+0%", "pitch": "+0Hz", "description": "平静"},
    "neutral": {"rate": "+0%", "pitch": "+0Hz", "description": "中性"},
    "narration": {"rate": "+0%", "pitch": "+0Hz", "description": "旁白"},
    "peaceful": {"rate": "-3%", "pitch": "+0Hz", "description": "宁静"},

    # 欢快情绪 (语速稍快，音调稍高)
    "happy": {"rate": "+5%", "pitch": "+5Hz", "description": "开心"},
    "joyful": {"rate": "+8%", "pitch": "+5Hz", "description": "欢乐"},
    "playful": {"rate": "+5%", "pitch": "+3Hz", "description": "俏皮"},

    # 神秘/庄重 (语速稍慢)
    "mysterious": {"rate": "-3%", "pitch": "-2Hz", "description": "神秘"},
    "solemn": {"rate": "-5%", "pitch": "-2Hz", "description": "庄重"},
    "epic": {"rate": "-3%", "pitch": "+2Hz", "description": "史诗"},
}

# 默认情绪参数
DEFAULT_MOOD_PARAMS = {"rate": "+0%", "pitch": "+0Hz", "description": "默认"}

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


def parse_rhythm_markers(text: str, base_rate: str = "+0%", base_pitch: str = "+0Hz") -> list[dict]:
    """解析节奏标记，返回片段列表

    Args:
        text: 包含节奏标记的文本
        base_rate: 基础语速（从 mood 继承）
        base_pitch: 基础音调（从 mood 继承）

    Returns:
        片段列表，每个片段包含：
        - {"text": "...", "rate": "...", "pitch": "...", "volume": "..."} 文本片段
        - {"pause": N} 静音片段（毫秒）

    示例:
        >>> parse_rhythm_markers("普通[fast]快速[/fast]普通")
        [
            {"text": "普通", "rate": "+0%", "pitch": "+0Hz", "volume": "+0%"},
            {"text": "快速", "rate": "+15%", "pitch": "+0Hz", "volume": "+0%"},
            {"text": "普通", "rate": "+0%", "pitch": "+0Hz", "volume": "+0%"}
        ]
    """
    segments = []
    last_end = 0

    for match in RHYTHM_MARKER_PATTERN.finditer(text):
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

        # 处理匹配的标记
        if match.group("tag"):
            # [fast], [slow], [emphasis] 标记
            tag = match.group("tag")
            content = match.group("content").strip()
            if content:
                marker_params = RHYTHM_MARKERS[tag]
                # 合并基础参数和标记参数
                segments.append({
                    "text": content,
                    "rate": _combine_rate(base_rate, marker_params["rate"]),
                    "pitch": _combine_pitch(base_pitch, marker_params["pitch"]),
                    "volume": marker_params["volume"]
                })
        elif match.group("pause"):
            # [pause:Nms] 标记
            pause_ms = int(match.group("pause"))
            segments.append({"pause": pause_ms})
        elif match.group("pitch"):
            # [pitch:+N]...[/pitch] 标记
            pitch_delta = match.group("pitch")
            content = match.group("pitch_content").strip()
            if content:
                segments.append({
                    "text": content,
                    "rate": base_rate,
                    "pitch": _combine_pitch(base_pitch, f"{pitch_delta}Hz"),
                    "volume": "+0%"
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
    """检查文本是否包含节奏标记"""
    return bool(RHYTHM_MARKER_PATTERN.search(text))


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


def concat_audio_segments(segment_paths: list[str], output_path: str, crossfade_ms: int = 10) -> bool:
    """使用 ffmpeg 拼接所有音频片段

    Args:
        segment_paths: 音频片段文件路径列表
        output_path: 输出文件路径
        crossfade_ms: 交叉淡化时长（毫秒），用于平滑片段衔接

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
        # 创建文件列表
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            list_file = f.name
            for path in segment_paths:
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

    Args:
        segment: 片段数据，包含 text/rate/pitch/volume 或 pause
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

    try:
        import edge_tts

        text = process_text_for_pause(segment["text"])
        rate = segment.get("rate", "+0%")
        pitch = segment.get("pitch", "+0Hz")
        # volume 目前 edge-tts 不支持单独设置，但我们记录它用于后处理
        # volume = segment.get("volume", "+0%")

        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)
        return True

    except Exception as e:
        print(f"生成片段音频失败: {e}")
        return False


async def generate_audio_with_rhythm(
    text: str,
    voice: str,
    output_path: str,
    base_rate: str = "+0%",
    base_pitch: str = "+0Hz",
    postprocess: bool = True
) -> bool:
    """主函数：解析标记 → 分段生成 → 拼接

    Args:
        text: 包含节奏标记的文本
        voice: 语音名称
        output_path: 最终输出路径
        base_rate: 基础语速（从 mood 继承）
        base_pitch: 基础音调（从 mood 继承）
        postprocess: 是否进行后处理

    Returns:
        是否成功
    """
    # 解析节奏标记
    segments = parse_rhythm_markers(text, base_rate, base_pitch)

    if not segments:
        # 没有有效片段
        return False

    if len(segments) == 1 and "text" in segments[0]:
        # 只有一个文本片段（无标记或只有一个标记），使用简化流程
        await generate_audio_with_postprocess(
            segments[0]["text"],
            voice,
            output_path,
            segments[0].get("rate", base_rate),
            segments[0].get("pitch", base_pitch),
            postprocess
        )
        return True

    # 多个片段：分段生成
    temp_dir = tempfile.mkdtemp(prefix="manga_audio_")
    segment_paths = []

    try:
        for i, segment in enumerate(segments):
            segment_path = os.path.join(temp_dir, f"segment_{i:03d}.mp3")
            success = await generate_segment_audio(segment, voice, segment_path)
            if success and os.path.exists(segment_path):
                segment_paths.append(segment_path)
            else:
                print(f"警告: 片段 {i} 生成失败，跳过")

        if not segment_paths:
            print("错误: 没有成功生成任何片段")
            return False

        # 拼接所有片段
        if postprocess:
            # 先拼接到临时文件，再后处理
            concat_path = os.path.join(temp_dir, "concat_raw.mp3")
            if concat_audio_segments(segment_paths, concat_path):
                normalize_audio(concat_path, output_path)
            else:
                return False
        else:
            # 直接拼接到最终路径
            concat_audio_segments(segment_paths, output_path)

        return True

    finally:
        # 清理临时文件
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
        包含 rate, pitch, description 的字典
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
    }

    for cn_mood, en_mood in chinese_mood_map.items():
        if cn_mood in mood_lower:
            return MOOD_PARAMETERS[en_mood]

    return DEFAULT_MOOD_PARAMS


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


def normalize_audio(input_path: str, output_path: str, target_loudness: float = -16.0):
    """规范化音频音量

    使用 ffmpeg 进行音量规范化和淡入淡出处理。

    Args:
        input_path: 输入音频路径
        output_path: 输出音频路径
        target_loudness: 目标响度（LUFS），默认 -16
    """
    try:
        # 使用 loudnorm 滤镜规范化音量，并添加淡入淡出
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", f"loudnorm=I={target_loudness}:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.05,afade=t=out:st=-1:d=0.1",
            "-ar", "44100",  # 采样率
            "-ac", "1",      # 单声道
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"音频处理失败: {e}")
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
    postprocess: bool = True
):
    """生成语音并进行后处理

    Args:
        text: 要朗读的文本
        voice: 语音名称
        output_path: 最终输出路径
        rate: 语速
        pitch: 音调
        postprocess: 是否进行后处理
    """
    if postprocess:
        # 先生成到临时文件
        temp_path = output_path.replace(".mp3", "_raw.mp3")
        await generate_audio_edge_tts(text, voice, temp_path, rate, pitch)

        # 后处理
        if normalize_audio(temp_path, output_path):
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
                    "narration": narration[:30] + "..." if len(narration) > 30 else narration
                })

                if uses_rhythm:
                    tasks.append(generate_audio_with_rhythm(
                        narration, voice_name, output_path, rate, pitch,
                        postprocess=enable_postprocess
                    ))
                else:
                    tasks.append(generate_audio_with_postprocess(
                        narration, voice_name, output_path, rate, pitch,
                        postprocess=enable_postprocess
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
                "narration": narration[:30] + "..." if len(narration) > 30 else narration
            })

            # 根据是否有节奏标记选择生成方法
            if uses_rhythm:
                # 使用节奏感知生成（分段生成 + 拼接）
                tasks.append(generate_audio_with_rhythm(
                    narration, voice_name, output_path, rate, pitch,
                    postprocess=enable_postprocess
                ))
            else:
                # 使用普通生成
                tasks.append(generate_audio_with_postprocess(
                    narration, voice_name, output_path, rate, pitch,
                    postprocess=enable_postprocess
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
    print(f"{'镜头':<12} {'说话人':<8} {'语音':<8} {'情绪':<6} {'语速':<8} {'音调':<10} {'节奏':<4} {'组':<4} {'内容'}")
    print("-" * 80)

    for info in shot_info:
        rhythm_flag = "✓" if info.get('rhythm') else "-"
        group_flag = "✓" if info.get('group') else "-"
        shot_id_display = info['shot_id'][:12] if len(info['shot_id']) > 12 else info['shot_id']
        print(f"{shot_id_display:<12} {info['speaker']:<8} {info['voice']:<8} "
              f"{info.get('mood', '-'):<6} {info.get('rate', '+0%'):<8} "
              f"{info.get('pitch', '+0Hz'):<10} {rhythm_flag:<4} {group_flag:<4} {info['narration']}")

    print("=" * 80)

    # 情绪分布统计
    mood_counts = {}
    rhythm_count = 0
    group_count = 0
    for info in shot_info:
        mood = info.get('mood', '默认')
        mood_counts[mood] = mood_counts.get(mood, 0) + 1
        if info.get('rhythm'):
            rhythm_count += 1
        if info.get('group'):
            group_count += 1

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
    """测试节奏标记解析功能"""
    print("=" * 60)
    print("节奏标记解析测试")
    print("=" * 60)

    test_cases = [
        # 基本测试
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
                print(f"  [{i}] \"{seg['text']}\" rate={seg['rate']} pitch={seg['pitch']} vol={seg['volume']}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python manga_generate_narration.py <output_dir> [options]")
        print("\n选项:")
        print("  --save-config     保存语音配置到剧本")
        print("  --no-postprocess  禁用音频后处理（音量规范化、淡入淡出）")
        print("  --test-rhythm     测试节奏标记解析功能")
        print("\n示例:")
        print("  python manga_generate_narration.py output/初心之雷")
        print("  python manga_generate_narration.py output/初心之雷 --save-config")
        print("  python manga_generate_narration.py output/初心之雷 --no-postprocess")
        print("  python manga_generate_narration.py output/初心之雷 --test-rhythm")
        print("\n可用语音:")
        for key, info in AVAILABLE_VOICES.items():
            print(f"  {key}: {info['description']}")
        print("\n可用情绪参数:")
        print("  激动类: excited, battle, surprise, angry")
        print("  悲伤类: sad, melancholy, farewell, loss")
        print("  温柔类: tender, romantic, warm, love")
        print("  紧张类: tense, urgent, chase, danger, suspense")
        print("  平静类: calm, neutral, narration, peaceful")
        print("  欢快类: happy, joyful, playful")
        print("  其他类: mysterious, solemn, epic")
        print("\n节奏标记语法 (词级别节奏控制):")
        print("  [fast]快速部分[/fast]       加速 +15%")
        print("  [slow]慢速部分[/slow]       减速 -15%")
        print("  [emphasis]重读[/emphasis]   重读 (稍慢+稍响)")
        print("  [pause:Nms]                 停顿 N 毫秒")
        print("  [pitch:+N]高音[/pitch]      音调变化 +N Hz")
        print("\n示例:")
        print('  "为什么你就是[emphasis]不愿意[/emphasis]相信我呢……"')
        print('  "[fast]快跑！[/fast][pause:200]他们追上来了！"')
        sys.exit(1)

    output_dir = sys.argv[1]
    save_config = "--save-config" in sys.argv
    enable_postprocess = "--no-postprocess" not in sys.argv
    test_rhythm = "--test-rhythm" in sys.argv

    # 测试模式
    if test_rhythm:
        test_rhythm_parsing()
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
