#!/usr/bin/env python3
"""
F5-TTS-MLX Backend 实现

基于 F5-TTS-MLX 的本地语音合成后端。
- 使用 MLX 框架，为 Apple Silicon 优化
- 支持情感参考音频进行自然的情绪表达
- 无需联网，完全本地运行

安装:
    pip install f5-tts-mlx

参考:
    https://github.com/lucasnewman/f5-tts-mlx
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

from .base import TTSBackend, TTSRequest, TTSResult


# 情感参考音频目录
REFS_DIR = Path(__file__).parent / "refs"

# 预设情绪参考音频映射
EMOTION_REFS = {
    "happy": "happy.wav",
    "sad": "sad.wav",
    "angry": "angry.wav",
    "tender": "tender.wav",
    "tense": "tense.wav",
    "excited": "excited.wav",
    "neutral": "neutral.wav",
    "narration": "narration.wav",
}

# 情绪对应的参考文本（用于 F5-TTS 的 ref_text）
EMOTION_REF_TEXTS = {
    "happy": "太好了！我真的太开心了！",
    "sad": "为什么……为什么会这样……",
    "angry": "可恶！我绝对不会原谅你的！",
    "tender": "没关系的，我会一直陪着你。",
    "tense": "小心！敌人就在附近！",
    "excited": "冲啊！胜利就在眼前！",
    "neutral": "今天的天气真不错。",
    "narration": "在很久很久以前，有一个美丽的村庄。",
}


class F5TTSBackend(TTSBackend):
    """F5-TTS-MLX 后端实现"""

    def __init__(self):
        """初始化 F5-TTS 后端"""
        self._model = None
        self._model_loaded = False

        # 验证 f5-tts-mlx 是否安装
        try:
            import f5_tts_mlx
            self._f5_tts = f5_tts_mlx
        except ImportError:
            raise ImportError(
                "f5-tts-mlx 未安装。请运行:\n"
                "  pip install f5-tts-mlx\n\n"
                "或从源码安装:\n"
                "  git clone https://github.com/lucasnewman/f5-tts-mlx.git\n"
                "  cd f5-tts-mlx\n"
                "  pip install -e ."
            )

        # 确保参考音频目录存在
        REFS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_model(self):
        """懒加载模型"""
        if self._model_loaded:
            return

        try:
            from f5_tts_mlx import F5TTS
            self._model = F5TTS.from_pretrained("lucasnewman/f5-tts-mlx")
            self._model_loaded = True
            print("F5-TTS 模型已加载")
        except Exception as e:
            raise RuntimeError(f"加载 F5-TTS 模型失败: {e}")

    @property
    def name(self) -> str:
        return "F5-TTS-MLX"

    @property
    def supports_streaming(self) -> bool:
        return False

    def get_available_voices(self) -> list[dict]:
        """获取可用语音列表

        F5-TTS 是 zero-shot 模型，不需要预定义语音。
        通过参考音频来定义声音。
        """
        # 返回预设的情绪声音
        return [
            {
                "id": mood,
                "name": f"{mood.capitalize()} Voice",
                "gender": "neutral",
                "language": "zh-CN",
                "description": f"基于 {mood} 情感的参考声音",
            }
            for mood in EMOTION_REFS.keys()
        ]

    def supports_emotion_reference(self) -> bool:
        """F5-TTS 支持情感参考音频"""
        return True

    def get_emotion_reference_path(self, mood: str) -> Optional[str]:
        """获取情感参考音频路径"""
        mood_lower = mood.lower().strip() if mood else "neutral"

        # 中文到英文的映射
        chinese_mood_map = {
            "激动": "excited", "开心": "happy", "悲伤": "sad", "愤怒": "angry",
            "温柔": "tender", "紧张": "tense", "中性": "neutral", "旁白": "narration",
        }

        if mood_lower in chinese_mood_map:
            mood_lower = chinese_mood_map[mood_lower]

        # 获取参考音频文件名
        ref_file = EMOTION_REFS.get(mood_lower, EMOTION_REFS.get("neutral"))
        if not ref_file:
            return None

        ref_path = REFS_DIR / ref_file

        # 检查文件是否存在
        if ref_path.exists():
            return str(ref_path)

        return None

    def get_reference_text(self, mood: str) -> str:
        """获取情感参考文本"""
        mood_lower = mood.lower().strip() if mood else "neutral"

        # 中文到英文的映射
        chinese_mood_map = {
            "激动": "excited", "开心": "happy", "悲伤": "sad", "愤怒": "angry",
            "温柔": "tender", "紧张": "tense", "中性": "neutral", "旁白": "narration",
        }

        if mood_lower in chinese_mood_map:
            mood_lower = chinese_mood_map[mood_lower]

        return EMOTION_REF_TEXTS.get(mood_lower, EMOTION_REF_TEXTS["neutral"])

    async def generate(self, request: TTSRequest) -> TTSResult:
        """生成音频"""
        try:
            # 确保模型已加载
            self._load_model()

            # 获取参考音频和文本
            ref_audio_path = request.reference_audio
            ref_text = request.reference_text

            if not ref_audio_path:
                ref_audio_path = self.get_emotion_reference_path(request.mood)

            if not ref_text:
                ref_text = self.get_reference_text(request.mood)

            # 检查参考音频是否存在
            if ref_audio_path and not Path(ref_audio_path).exists():
                # 参考音频不存在，使用默认或不使用
                ref_audio_path = None
                print(f"警告: 参考音频不存在，将使用默认声音")

            # 生成音频
            if ref_audio_path:
                audio = self._model.generate(
                    text=request.text,
                    ref_audio=ref_audio_path,
                    ref_text=ref_text,
                )
            else:
                # 没有参考音频时的处理
                audio = self._model.generate(
                    text=request.text,
                )

            # 保存音频
            output_path = Path(request.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # F5-TTS 输出格式处理
            if hasattr(audio, 'save'):
                audio.save(str(output_path))
            else:
                # 如果返回的是 numpy array，使用 scipy 保存
                import scipy.io.wavfile as wav
                sample_rate = getattr(audio, 'sample_rate', 24000)
                wav.write(str(output_path), sample_rate, audio)

            # 后处理
            if request.postprocess:
                self._postprocess_audio(request.output_path, request.normalize_loudness)

            # 获取时长
            duration = self._get_audio_duration(request.output_path)

            return TTSResult(
                success=True,
                duration=duration,
                output_path=request.output_path,
                metadata={
                    "ref_audio": ref_audio_path,
                    "ref_text": ref_text,
                    "mood": request.mood,
                }
            )

        except Exception as e:
            return TTSResult(
                success=False,
                error=str(e),
            )

    def _postprocess_audio(self, audio_path: str, target_loudness: float = -16.0) -> bool:
        """后处理音频"""
        try:
            import tempfile

            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                temp_path = tmp.name

            # 使用 ffmpeg 进行后处理
            cmd = [
                "ffmpeg", "-y", "-i", audio_path,
                "-af", f"loudnorm=I={target_loudness}:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.05,afade=t=out:st=-1:d=0.1",
                "-ar", "44100",
                "-ac", "1",
                temp_path
            ]
            subprocess.run(cmd, capture_output=True, check=True)

            # 替换原文件
            import shutil
            shutil.move(temp_path, audio_path)

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

    def create_emotion_reference(self, emotion: str, audio_path: str, text: str) -> bool:
        """创建情感参考音频

        用于扩展情感参考库。

        Args:
            emotion: 情绪名称
            audio_path: 音频文件路径
            text: 音频对应的文本

        Returns:
            是否成功
        """
        try:
            import shutil

            # 确保目录存在
            REFS_DIR.mkdir(parents=True, exist_ok=True)

            # 复制音频文件
            ref_filename = f"{emotion}.wav"
            ref_path = REFS_DIR / ref_filename

            # 转换为 WAV 格式（如果需要）
            if not audio_path.endswith('.wav'):
                subprocess.run([
                    "ffmpeg", "-y", "-i", audio_path,
                    "-ar", "24000", "-ac", "1",
                    str(ref_path)
                ], capture_output=True, check=True)
            else:
                shutil.copy(audio_path, ref_path)

            # 更新映射
            EMOTION_REFS[emotion] = ref_filename
            EMOTION_REF_TEXTS[emotion] = text

            print(f"情感参考已创建: {emotion} -> {ref_path}")
            return True

        except Exception as e:
            print(f"创建情感参考失败: {e}")
            return False

    def list_emotion_references(self) -> list[dict]:
        """列出所有可用的情感参考"""
        refs = []
        for emotion, filename in EMOTION_REFS.items():
            ref_path = REFS_DIR / filename
            refs.append({
                "emotion": emotion,
                "filename": filename,
                "exists": ref_path.exists(),
                "ref_text": EMOTION_REF_TEXTS.get(emotion, ""),
            })
        return refs
