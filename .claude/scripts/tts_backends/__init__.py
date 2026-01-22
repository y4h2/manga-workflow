#!/usr/bin/env python3
"""
TTS Backend Factory

提供统一的后端创建接口，支持通过环境变量或显式参数切换不同的 TTS 引擎。

使用方式:

    # 使用默认后端（Edge-TTS）
    backend = create_backend()

    # 使用指定后端
    backend = create_backend("f5")

    # 通过环境变量切换
    # TTS_BACKEND=f5 python script.py

环境变量:
    TTS_BACKEND: 指定 TTS 后端类型
        - "edge" (默认): 使用 Edge-TTS（微软云端 TTS）
        - "f5": 使用 F5-TTS-MLX（本地 TTS，需要安装）
"""

import os
from typing import Optional

from .base import TTSBackend, TTSRequest, TTSResult

__all__ = ["create_backend", "TTSBackend", "TTSRequest", "TTSResult", "get_available_backends"]


# 可用后端列表
AVAILABLE_BACKENDS = {
    "edge": {
        "name": "Edge-TTS",
        "description": "微软云端 TTS，免费使用，情绪通过 rate/pitch/volume 参数控制",
        "requires": ["edge-tts"],
        "supports_emotion_reference": False,
    },
    "f5": {
        "name": "F5-TTS-MLX",
        "description": "本地 TTS，Mac M-series 优化，支持情感参考音频",
        "requires": ["f5-tts-mlx"],
        "supports_emotion_reference": True,
    },
}


def get_available_backends() -> dict:
    """获取可用后端列表

    Returns:
        后端信息字典
    """
    return AVAILABLE_BACKENDS.copy()


def create_backend(backend_type: Optional[str] = None) -> TTSBackend:
    """创建 TTS 后端实例

    优先级:
    1. 显式指定的 backend_type
    2. TTS_BACKEND 环境变量
    3. 默认使用 edge

    Args:
        backend_type: 后端类型，可选 "edge" 或 "f5"

    Returns:
        TTS 后端实例

    Raises:
        ValueError: 不支持的后端类型
        ImportError: 缺少必要的依赖
    """
    if backend_type is None:
        backend_type = os.environ.get("TTS_BACKEND", "edge")

    backend_type = backend_type.lower().strip()

    if backend_type == "f5":
        try:
            from .f5_tts_backend import F5TTSBackend
            return F5TTSBackend()
        except ImportError as e:
            raise ImportError(
                f"F5-TTS-MLX 未安装。请运行: pip install f5-tts-mlx\n"
                f"原始错误: {e}"
            )

    elif backend_type == "edge":
        try:
            from .edge_tts_backend import EdgeTTSBackend
            return EdgeTTSBackend()
        except ImportError as e:
            raise ImportError(
                f"edge-tts 未安装。请运行: pip install edge-tts\n"
                f"原始错误: {e}"
            )

    else:
        raise ValueError(
            f"不支持的 TTS 后端: {backend_type}\n"
            f"可用选项: {', '.join(AVAILABLE_BACKENDS.keys())}"
        )


def check_backend_available(backend_type: str) -> tuple[bool, Optional[str]]:
    """检查后端是否可用

    Args:
        backend_type: 后端类型

    Returns:
        (是否可用, 错误信息)
    """
    if backend_type not in AVAILABLE_BACKENDS:
        return False, f"不支持的后端: {backend_type}"

    try:
        create_backend(backend_type)
        return True, None
    except ImportError as e:
        return False, str(e)
