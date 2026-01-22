#!/usr/bin/env python3
"""
TTS Backend 抽象基类

定义 TTS 后端的统一接口，支持多种 TTS 引擎切换。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class TTSRequest:
    """TTS 生成请求"""
    text: str                           # 要合成的文本
    voice: str                          # 语音名称
    mood: str                           # 情绪名称
    output_path: str                    # 输出文件路径

    # 语音参数
    rate: str = "+0%"                   # 语速
    pitch: str = "+0Hz"                 # 音调
    volume: str = "+0%"                 # 音量

    # 可选：情感参考音频（用于本地 TTS 如 F5-TTS）
    reference_audio: Optional[str] = None
    reference_text: Optional[str] = None

    # 后处理选项
    postprocess: bool = True            # 是否进行后处理
    normalize_loudness: float = -16.0   # 目标响度（LUFS）


@dataclass
class TTSResult:
    """TTS 生成结果"""
    success: bool                       # 是否成功
    duration: float = 0.0               # 音频时长（秒）
    output_path: Optional[str] = None   # 实际输出路径
    error: Optional[str] = None         # 错误信息
    metadata: dict = field(default_factory=dict)  # 额外元数据


class TTSBackend(ABC):
    """TTS 后端抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """后端名称"""
        pass

    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """是否支持流式生成"""
        pass

    @abstractmethod
    async def generate(self, request: TTSRequest) -> TTSResult:
        """生成音频

        Args:
            request: TTS 生成请求

        Returns:
            TTS 生成结果
        """
        pass

    @abstractmethod
    def get_available_voices(self) -> list[dict]:
        """获取可用语音列表

        Returns:
            语音信息列表，每个元素包含：
            - id: 语音 ID
            - name: 显示名称
            - gender: 性别
            - language: 语言
            - description: 描述
        """
        pass

    @abstractmethod
    def supports_emotion_reference(self) -> bool:
        """是否支持情感参考音频

        返回 True 表示支持通过参考音频来控制情感表达（如 F5-TTS）。
        返回 False 表示通过参数（rate/pitch/volume）来控制（如 Edge-TTS）。
        """
        pass

    def get_mood_parameters(self, mood: str) -> dict:
        """获取情绪参数

        子类可以重写此方法来自定义情绪参数映射。

        Args:
            mood: 情绪名称

        Returns:
            包含 rate, pitch, volume 的字典
        """
        # 默认情绪参数映射
        MOOD_PARAMETERS = {
            "neutral": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"},
            "happy": {"rate": "+5%", "pitch": "+5Hz", "volume": "+5%"},
            "sad": {"rate": "-8%", "pitch": "-5Hz", "volume": "-5%"},
            "angry": {"rate": "+8%", "pitch": "+8Hz", "volume": "+10%"},
            "fearful": {"rate": "+5%", "pitch": "+3Hz", "volume": "-3%"},
            "excited": {"rate": "+10%", "pitch": "+8Hz", "volume": "+8%"},
            "tender": {"rate": "-5%", "pitch": "+3Hz", "volume": "-5%"},
            "tense": {"rate": "+5%", "pitch": "+3Hz", "volume": "+0%"},
            "urgent": {"rate": "+12%", "pitch": "+5Hz", "volume": "+5%"},
            "calm": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"},
        }

        return MOOD_PARAMETERS.get(mood.lower(), MOOD_PARAMETERS["neutral"])

    async def batch_generate(self, requests: list[TTSRequest]) -> list[TTSResult]:
        """批量生成音频

        默认实现为顺序生成，子类可以重写以实现并行生成。

        Args:
            requests: TTS 生成请求列表

        Returns:
            TTS 生成结果列表
        """
        results = []
        for request in requests:
            result = await self.generate(request)
            results.append(result)
        return results

    def validate_voice(self, voice: str) -> bool:
        """验证语音是否可用

        Args:
            voice: 语音 ID

        Returns:
            是否可用
        """
        available_voices = self.get_available_voices()
        return any(v.get("id") == voice for v in available_voices)

    def get_emotion_reference_path(self, mood: str) -> Optional[str]:
        """获取情感参考音频路径

        仅对支持情感参考的后端有效。

        Args:
            mood: 情绪名称

        Returns:
            参考音频路径，不支持时返回 None
        """
        return None
