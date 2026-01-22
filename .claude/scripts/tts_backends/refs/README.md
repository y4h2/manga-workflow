# 情感参考音频 (Emotion Reference Audio)

此目录用于存放 F5-TTS-MLX 的情感参考音频文件。

## 文件命名

每个文件应以情绪名称命名：

```
refs/
├── happy.wav      # 欢快的参考音频
├── sad.wav        # 悲伤的参考音频
├── angry.wav      # 愤怒的参考音频
├── tender.wav     # 温柔的参考音频
├── tense.wav      # 紧张的参考音频
├── excited.wav    # 激动的参考音频
├── neutral.wav    # 中性的参考音频
└── narration.wav  # 旁白风格
```

## 音频要求

- **格式**: WAV (推荐) 或 MP3
- **时长**: 3-5 秒
- **采样率**: 24000 Hz (F5-TTS 默认)
- **通道**: 单声道
- **内容**: 带有对应情绪的中文语音

## 录制建议

1. **选择合适的声音**: 使用与目标角色相似的声音
2. **情绪一致性**: 确保参考音频的情绪表达清晰
3. **音质**: 尽量使用干净、无噪音的录音

## 参考文本

每个情绪有对应的参考文本（在 `f5_tts_backend.py` 中定义）：

| 情绪 | 参考文本 |
|------|---------|
| happy | 太好了！我真的太开心了！ |
| sad | 为什么……为什么会这样…… |
| angry | 可恶！我绝对不会原谅你的！ |
| tender | 没关系的，我会一直陪着你。 |
| tense | 小心！敌人就在附近！ |
| excited | 冲啊！胜利就在眼前！ |
| neutral | 今天的天气真不错。 |
| narration | 在很久很久以前，有一个美丽的村庄。 |

## 使用 Edge-TTS 生成参考音频

如果没有真人录音，可以使用 Edge-TTS 生成基础参考音频：

```bash
# 生成各情绪的参考音频
python -c "
import asyncio
import edge_tts

async def generate_refs():
    refs = {
        'happy': ('太好了！我真的太开心了！', '+10%', '+8Hz'),
        'sad': ('为什么……为什么会这样……', '-10%', '-8Hz'),
        'angry': ('可恶！我绝对不会原谅你的！', '+8%', '+8Hz'),
        'tender': ('没关系的，我会一直陪着你。', '-5%', '+3Hz'),
        'tense': ('小心！敌人就在附近！', '+8%', '+5Hz'),
        'excited': ('冲啊！胜利就在眼前！', '+12%', '+10Hz'),
        'neutral': ('今天的天气真不错。', '+0%', '+0Hz'),
        'narration': ('在很久很久以前，有一个美丽的村庄。', '-3%', '+0Hz'),
    }

    for mood, (text, rate, pitch) in refs.items():
        comm = edge_tts.Communicate(text, 'zh-CN-XiaoxiaoNeural', rate=rate, pitch=pitch)
        await comm.save(f'{mood}.wav')
        print(f'Generated: {mood}.wav')

asyncio.run(generate_refs())
"
```

## 注意事项

- 如果没有参考音频文件，F5-TTS 会使用默认声音
- 建议为主要情绪准备高质量的参考音频
- 可以使用 `create_emotion_reference()` 方法动态添加新情绪
