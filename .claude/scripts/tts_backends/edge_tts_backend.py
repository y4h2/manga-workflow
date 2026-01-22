#!/usr/bin/env python3
"""
Edge-TTS Backend 实现

基于微软 Edge TTS 的语音合成后端。
- 免费使用
- 支持多种中文语音
- 通过 rate/pitch/volume 参数控制情绪表达
"""

import asyncio
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .base import TTSBackend, TTSRequest, TTSResult


# 可用的中文语音配置
CHINESE_VOICES = {
    # 女声
    "xiaoxiao": {
        "id": "zh-CN-XiaoxiaoNeural",
        "name": "晓晓",
        "gender": "female",
        "language": "zh-CN",
        "style": "温暖",
        "description": "温暖女声，适合旁白、温柔角色"
    },
    "xiaoyi": {
        "id": "zh-CN-XiaoyiNeural",
        "name": "晓伊",
        "gender": "female",
        "language": "zh-CN",
        "style": "活泼",
        "description": "活泼女声，适合年轻女性角色"
    },
    "xiaobei": {
        "id": "zh-CN-liaoning-XiaobeiNeural",
        "name": "晓贝",
        "gender": "female",
        "language": "zh-CN",
        "style": "幽默",
        "description": "东北方言女声，适合喜剧角色"
    },
    # 男声
    "yunxi": {
        "id": "zh-CN-YunxiNeural",
        "name": "云希",
        "gender": "male",
        "language": "zh-CN",
        "style": "少年",
        "description": "阳光少年声，适合年轻男主角"
    },
    "yunjian": {
        "id": "zh-CN-YunjianNeural",
        "name": "云健",
        "gender": "male",
        "language": "zh-CN",
        "style": "热血",
        "description": "热血男声，适合战斗场景、激情时刻"
    },
    "yunyang": {
        "id": "zh-CN-YunyangNeural",
        "name": "云扬",
        "gender": "male",
        "language": "zh-CN",
        "style": "成熟",
        "description": "成熟男声，适合旁白、成熟角色"
    },
    "yunxia": {
        "id": "zh-CN-YunxiaNeural",
        "name": "云夏",
        "gender": "male",
        "language": "zh-CN",
        "style": "可爱",
        "description": "可爱男声，适合小孩、萌系角色"
    },
}

# 情绪参数映射（优化版，添加了 volume）
MOOD_PARAMETERS = {
    # === 基础情绪 ===
    "neutral": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"},
    "happy": {"rate": "+5%", "pitch": "+5Hz", "volume": "+5%"},
    "sad": {"rate": "-8%", "pitch": "-5Hz", "volume": "-5%"},
    "angry": {"rate": "+8%", "pitch": "+8Hz", "volume": "+10%"},
    "fearful": {"rate": "+5%", "pitch": "+3Hz", "volume": "-3%"},

    # === 复合情绪 ===
    "excited": {"rate": "+10%", "pitch": "+8Hz", "volume": "+8%"},
    "tender": {"rate": "-5%", "pitch": "+3Hz", "volume": "-5%"},
    "melancholy": {"rate": "-10%", "pitch": "-8Hz", "volume": "-8%"},
    "romantic": {"rate": "-5%", "pitch": "+5Hz", "volume": "-3%"},
    "warm": {"rate": "-3%", "pitch": "+2Hz", "volume": "+0%"},
    "love": {"rate": "-5%", "pitch": "+3Hz", "volume": "-3%"},

    # === 紧张系列 ===
    "tense": {"rate": "+5%", "pitch": "+3Hz", "volume": "+0%"},
    "urgent": {"rate": "+12%", "pitch": "+5Hz", "volume": "+5%"},
    "chase": {"rate": "+15%", "pitch": "+8Hz", "volume": "+8%"},
    "danger": {"rate": "+8%", "pitch": "+10Hz", "volume": "+10%"},
    "suspense": {"rate": "+3%", "pitch": "+2Hz", "volume": "-3%"},

    # === 悲伤系列 ===
    "farewell": {"rate": "-8%", "pitch": "-5Hz", "volume": "-5%"},
    "loss": {"rate": "-12%", "pitch": "-8Hz", "volume": "-8%"},
    "regret": {"rate": "-10%", "pitch": "-5Hz", "volume": "-5%"},

    # === 叙事风格 ===
    "narration": {"rate": "-3%", "pitch": "+0Hz", "volume": "+0%"},
    "mysterious": {"rate": "-5%", "pitch": "-3Hz", "volume": "-3%"},
    "epic": {"rate": "-8%", "pitch": "-5Hz", "volume": "+5%"},
    "solemn": {"rate": "-10%", "pitch": "-8Hz", "volume": "+3%"},

    # === 平静系列 ===
    "calm": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"},
    "peaceful": {"rate": "-3%", "pitch": "+0Hz", "volume": "-3%"},

    # === 欢快系列 ===
    "joyful": {"rate": "+8%", "pitch": "+8Hz", "volume": "+8%"},
    "playful": {"rate": "+5%", "pitch": "+5Hz", "volume": "+3%"},

    # === 战斗/动作 ===
    "battle": {"rate": "+12%", "pitch": "+8Hz", "volume": "+10%"},
    "surprise": {"rate": "+8%", "pitch": "+10Hz", "volume": "+5%"},
}


class EdgeTTSBackend(TTSBackend):
    """Edge-TTS 后端实现"""

    def __init__(self):
        """初始化 Edge-TTS 后端"""
        # 验证 edge-tts 是否安装
        try:
            import edge_tts
            self._edge_tts = edge_tts
        except ImportError:
            raise ImportError("edge-tts 未安装。请运行: pip install edge-tts")

    @property
    def name(self) -> str:
        return "Edge-TTS"

    @property
    def supports_streaming(self) -> bool:
        return True

    def get_available_voices(self) -> list[dict]:
        """获取可用语音列表"""
        return [
            {
                "id": key,
                "name": info["name"],
                "gender": info["gender"],
                "language": info["language"],
                "description": info["description"],
                "full_id": info["id"],
            }
            for key, info in CHINESE_VOICES.items()
        ]

    def supports_emotion_reference(self) -> bool:
        """Edge-TTS 不支持情感参考音频"""
        return False

    def get_mood_parameters(self, mood: str) -> dict:
        """获取情绪参数"""
        if not mood:
            return MOOD_PARAMETERS["neutral"]

        mood_lower = mood.lower().strip()

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

        return MOOD_PARAMETERS["neutral"]

    def _resolve_voice(self, voice: str) -> str:
        """解析语音名称为完整的 Edge-TTS 语音 ID"""
        voice_lower = voice.lower().strip()

        # 检查是否是简短 ID
        if voice_lower in CHINESE_VOICES:
            return CHINESE_VOICES[voice_lower]["id"]

        # 检查是否已经是完整 ID
        for key, info in CHINESE_VOICES.items():
            if info["id"].lower() == voice_lower:
                return info["id"]

        # 默认返回晓晓
        return CHINESE_VOICES["xiaoxiao"]["id"]

    def _process_text(self, text: str) -> str:
        """处理文本，优化朗读效果"""
        # 确保省略号格式一致
        text = text.replace('...', '……')
        return text

    def _get_volume_adjustment(self, volume_str: str) -> float:
        """将音量字符串转换为 dB 调整值"""
        if not volume_str:
            return 0.0

        match = re.match(r'([+-]?)(\d+)%', volume_str)
        if not match:
            return 0.0

        sign, value = match.groups()
        percent = int(value)

        # 将百分比转换为 dB（大约 6dB = 2倍音量）
        if sign == '-':
            return -percent * 0.08
        else:
            return percent * 0.08

    async def generate(self, request: TTSRequest) -> TTSResult:
        """生成音频"""
        try:
            # 解析语音
            voice_id = self._resolve_voice(request.voice)

            # 获取情绪参数
            if request.rate == "+0%" and request.pitch == "+0Hz":
                # 如果没有显式设置参数，从 mood 获取
                mood_params = self.get_mood_parameters(request.mood)
                rate = mood_params["rate"]
                pitch = mood_params["pitch"]
                volume = mood_params["volume"]
            else:
                rate = request.rate
                pitch = request.pitch
                volume = request.volume

            # 处理文本
            processed_text = self._process_text(request.text)

            # 生成音频
            if request.postprocess:
                # 生成到临时文件，然后后处理
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    temp_path = tmp.name

                communicate = self._edge_tts.Communicate(
                    processed_text, voice_id, rate=rate, pitch=pitch
                )
                await communicate.save(temp_path)

                # 后处理
                volume_db = self._get_volume_adjustment(volume)
                success = self._normalize_audio(
                    temp_path, request.output_path,
                    target_loudness=request.normalize_loudness,
                    volume_adjust_db=volume_db
                )

                # 清理临时文件
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

                if not success:
                    # 后处理失败，直接使用原始文件
                    communicate = self._edge_tts.Communicate(
                        processed_text, voice_id, rate=rate, pitch=pitch
                    )
                    await communicate.save(request.output_path)
            else:
                # 直接生成
                communicate = self._edge_tts.Communicate(
                    processed_text, voice_id, rate=rate, pitch=pitch
                )
                await communicate.save(request.output_path)

            # 获取时长
            duration = self._get_audio_duration(request.output_path)

            return TTSResult(
                success=True,
                duration=duration,
                output_path=request.output_path,
                metadata={
                    "voice": voice_id,
                    "rate": rate,
                    "pitch": pitch,
                    "volume": volume,
                    "mood": request.mood,
                }
            )

        except Exception as e:
            return TTSResult(
                success=False,
                error=str(e),
            )

    def _normalize_audio(
        self,
        input_path: str,
        output_path: str,
        target_loudness: float = -16.0,
        volume_adjust_db: float = 0.0
    ) -> bool:
        """规范化音频音量"""
        try:
            # 构建滤镜链
            filters = [
                f"loudnorm=I={target_loudness}:TP=-1.5:LRA=11",
                "afade=t=in:st=0:d=0.05",
                "afade=t=out:st=-1:d=0.1"
            ]

            # 如果有音量调整，添加 volume 滤镜
            if abs(volume_adjust_db) > 0.1:
                filters.append(f"volume={volume_adjust_db}dB")

            filter_str = ",".join(filters)

            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-af", filter_str,
                "-ar", "44100",
                "-ac", "1",
                output_path
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频文件时长"""
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                 '-of', 'csv=p=0', audio_path],
                capture_output=True, text=True
            )
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return 0.0

    async def batch_generate(self, requests: list[TTSRequest]) -> list[TTSResult]:
        """批量生成音频（并行）"""
        tasks = [self.generate(req) for req in requests]
        return await asyncio.gather(*tasks)
