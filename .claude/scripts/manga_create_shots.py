#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 漫剧生成 - 分镜创建脚本 (阶段 0.5)
读取故事大纲，按场景分组镜头，生成完整剧本

使用 locations 格式（场景化分镜）
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from manga_common import (
    SCREENPLAY_PATH,
    DEFAULT_SHOT_DURATION,
    VALID_SHOT_COMPOSITIONS,
    PACING_TYPES,
    load_story_outline,
    get_beat_by_id,
    get_character_phase_for_beat,
    build_phase_appearance_prompt,
    build_anchor_prompt,
    inject_anchor_to_prompt,
    get_suggested_shot_count,
    analyze_pacing_distribution,
    estimate_duration,
    get_mood_params,
)


# 默认语音配置
DEFAULT_VOICE_CONFIG = {
    "旁白": "xiaoxiao",      # 温暖女声旁白
    "narrator": "xiaoxiao",
}

# 可用语音列表
AVAILABLE_VOICES = {
    "xiaoxiao": {"gender": "female", "style": "温暖", "description": "温暖女声，适合旁白"},
    "xiaoyi": {"gender": "female", "style": "活泼", "description": "活泼女声，适合年轻女性"},
    "yunxi": {"gender": "male", "style": "少年", "description": "阳光少年声，适合年轻男主"},
    "yunjian": {"gender": "male", "style": "热血", "description": "热血男声，适合战斗场景"},
    "yunyang": {"gender": "male", "style": "成熟", "description": "成熟男声，适合成熟角色"},
    "yunxia": {"gender": "male", "style": "可爱", "description": "可爱声音，适合萌系角色"},
}


def normalize_chinese_punctuation(text: str) -> str:
    """规范化中文标点符号"""
    if not text:
        return text

    punctuation_map = {
        ",": "，", ".": "。", "!": "！", "?": "？",
        ":": "：", ";": "；", "(": "（", ")": "）",
        "[": "【", "]": "】", '"': '"',
    }

    result = text
    for eng, chn in punctuation_map.items():
        pattern = f"([\u4e00-\u9fff]){re.escape(eng)}"
        result = re.sub(pattern, f"\\1{chn}", result)
        pattern = f"{re.escape(eng)}([\u4e00-\u9fff])"
        result = re.sub(pattern, f"{chn}\\1", result)

    result = result.replace("...", "……").replace("--", "——")
    return result


def get_speaker(shot: dict, default_protagonist: str = None) -> str:
    """获取镜头的说话人

    优先使用 shot 中指定的 speaker，如果未指定则使用默认主角。
    说话人应该在 AI 生成分镜时就明确指定。

    Args:
        shot: 镜头数据（应包含 speaker 字段）
        default_protagonist: 默认主角名称（备选）

    Returns:
        说话人名称
    """
    # 优先使用明确指定的 speaker
    if "speaker" in shot and shot["speaker"]:
        return shot["speaker"]

    # 备选：使用默认主角
    if default_protagonist:
        return default_protagonist

    return "旁白"


def build_voice_config(story: dict) -> dict:
    """根据角色列表构建语音配置

    Args:
        story: 故事大纲数据

    Returns:
        角色名称到语音 ID 的映射
    """
    voice_config = dict(DEFAULT_VOICE_CONFIG)

    characters = story.get("characters", [])

    # 分配语音（按主角优先顺序）
    male_voices = ["yunxi", "yunjian", "yunyang"]  # 少年、热血、成熟
    female_voices = ["xiaoyi", "xiaoxiao"]  # 活泼、温暖
    cute_voice = "yunxia"  # 可爱

    male_idx = 0
    female_idx = 0

    # 按角色类型排序：主角优先
    sorted_chars = sorted(characters, key=lambda c: 0 if c.get("role") == "主角" else 1)

    for char in sorted_chars:
        char_name = char.get("name", "")
        if not char_name:
            continue

        # 检查是否已手动配置
        if char_name in voice_config:
            continue

        # 根据角色特征推断性别和语音类型
        appearance = (char.get("appearance", "") + " " + char.get("name", "")).lower()
        personality = char.get("personality", "").lower()
        role = char.get("role", "").lower()

        # 检测非人类角色（萌系/可爱角色）
        cute_keywords = ["可爱", "萌", "宝可梦", "精灵", "妖精", "皮卡丘", "pokemon", "pikachu"]
        if any(kw in char_name.lower() or kw in appearance for kw in cute_keywords):
            voice_config[char_name] = cute_voice
            continue

        # 检测性别
        female_keywords = ["女", "姐", "妹", "娘", "女性", "female", "woman", "girl", "母", "妈"]
        male_keywords = ["男", "哥", "弟", "少年", "男性", "male", "man", "boy", "父", "爸", "博士", "老"]

        is_female = any(kw in appearance for kw in female_keywords)
        is_male = any(kw in appearance for kw in male_keywords)

        # 角色类型也影响语音选择
        if is_female and not is_male:
            voice_config[char_name] = female_voices[female_idx % len(female_voices)]
            female_idx += 1
        elif is_male or role == "主角":
            # 主角默认使用少年声(yunxi)
            voice_config[char_name] = male_voices[male_idx % len(male_voices)]
            male_idx += 1
        else:
            # 无法判断性别时，根据角色顺序分配
            voice_config[char_name] = male_voices[male_idx % len(male_voices)]
            male_idx += 1

    return voice_config


def validate_shot(shot: dict, location_id: int, shot_index: int) -> list:
    """验证单个镜头"""
    errors = []
    shot_id = shot.get("shot_id", f"{location_id}-{shot_index + 1}")
    prefix = f"Shot {shot_id}"

    required_fields = ["shot_id", "narration", "image_prompt", "video_prompt"]
    for field in required_fields:
        if field not in shot:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")
        elif field != "shot_id" and not shot[field]:
            errors.append(f"{prefix}: 字段 '{field}' 不能为空")

    if "image_prompt" in shot and shot["image_prompt"]:
        if not shot["image_prompt"].lower().startswith("anime style"):
            errors.append(f"{prefix}: image_prompt 必须以 'anime style' 开头")

    if "composition" in shot:
        composition = shot["composition"].lower()
        valid_lower = [c.lower() for c in VALID_SHOT_COMPOSITIONS]
        if composition not in valid_lower:
            errors.append(f"{prefix}: 无效的 composition '{shot['composition']}'")

    return errors


def validate_location(location: dict, index: int) -> list:
    """验证场景数据"""
    errors = []
    loc_id = location.get("location_id", index + 1)
    prefix = f"Location {loc_id}"

    required_fields = ["location_id", "name", "background_prompt"]
    for field in required_fields:
        if field not in location:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")

    if "shots" not in location:
        errors.append(f"{prefix}: 缺少 shots 数组")
        return errors

    if not isinstance(location["shots"], list) or len(location["shots"]) == 0:
        errors.append(f"{prefix}: shots 不能为空")
        return errors

    for i, shot in enumerate(location["shots"]):
        errors.extend(validate_shot(shot, loc_id, i))

    return errors


def validate_shots_data(data: dict) -> list:
    """验证分镜数据"""
    errors = []

    if "locations" not in data:
        errors.append("缺少 locations 数组")
        return errors

    if not isinstance(data["locations"], list) or len(data["locations"]) == 0:
        errors.append("locations 不能为空")
        return errors

    for i, location in enumerate(data["locations"]):
        errors.extend(validate_location(location, i))

    return errors


def build_character_phases(story: dict) -> list:
    """从故事大纲构建角色阶段列表"""
    character_phases = []

    for char in story.get("characters", []):
        char_name = char.get("name", "")
        phases = char.get("phases", [])

        # 构建锚定特征
        anchor_prompt = build_anchor_prompt(char)

        if not phases:
            # 没有定义 phases，创建默认阶段
            character_phases.append({
                "phase_id": 1,
                "character": char_name,
                "name": "默认",
                "appearance_prompt": char.get("appearance", ""),
                "anchor_prompt": anchor_prompt,
                "beat_range": [1, 999],
                "reference_image": None
            })
        else:
            for phase in phases:
                character_phases.append({
                    "phase_id": phase.get("phase_id", 1),
                    "character": char_name,
                    "name": phase.get("name", ""),
                    "appearance_prompt": build_phase_appearance_prompt(phase, char),
                    "anchor_prompt": anchor_prompt,
                    "beat_range": phase.get("beat_range", [1, 999]),
                    "reference_image": None
                })

    return character_phases


def inject_anchor_features_to_shots(screenplay: dict, story: dict) -> dict:
    """将角色锚定特征自动注入到镜头的 image_prompt 中

    Args:
        screenplay: 剧本数据
        story: 故事大纲数据

    Returns:
        处理后的剧本数据
    """
    # 构建角色名称到角色数据的映射
    characters = {c.get("name", ""): c for c in story.get("characters", [])}

    # 记录每个角色的首次出场
    first_appearance = {}

    for loc in screenplay.get("locations", []):
        for shot in loc.get("shots", []):
            # 检测镜头中涉及的角色
            action = shot.get("action", "")
            image_prompt = shot.get("image_prompt", "")

            # 只处理包含角色的镜头
            if not shot.get("character_visible", True):
                continue

            for char_name, char_data in characters.items():
                if char_name in action:
                    # 检查角色是否有锚定特征
                    anchor = build_anchor_prompt(char_data)
                    if not anchor:
                        continue

                    is_first = char_name not in first_appearance
                    if is_first:
                        first_appearance[char_name] = shot.get("shot_id")

                    # 注入锚定特征
                    shot["image_prompt"] = inject_anchor_to_prompt(
                        image_prompt,
                        char_data,
                        is_first=is_first
                    )
                    # 只处理第一个匹配的角色
                    break

    return screenplay


def merge_story_and_shots(story: dict, shots_data: dict) -> dict:
    """合并故事大纲和分镜数据为完整剧本"""
    screenplay = {}

    # 复制故事大纲字段
    for field in ["title", "genre", "style_keywords", "aspect_ratio", "premise", "narrative_arc", "output_dir", "task_id"]:
        if field in story:
            screenplay[field] = story[field]

    # 构建角色阶段列表
    screenplay["character_phases"] = build_character_phases(story)

    # 构建语音配置
    screenplay["voice_config"] = build_voice_config(story)

    # 获取默认主角名称
    default_protagonist = None
    for char in story.get("characters", []):
        if char.get("role") == "主角":
            default_protagonist = char.get("name")
            break
    if not default_protagonist and story.get("characters"):
        default_protagonist = story["characters"][0].get("name")

    # 处理 locations
    screenplay["locations"] = []

    for loc_data in shots_data.get("locations", []):
        loc_id = loc_data.get("location_id", 0)

        # 查找故事中对应的 location
        story_location = None
        for story_loc in story.get("locations", []):
            if story_loc.get("location_id") == loc_id:
                story_location = story_loc
                break

        # 计算节奏建议
        pacing_info = None
        if story_location:
            pacing_info = get_suggested_shot_count(story, story_location)

        location = {
            "location_id": loc_id,
            "name": loc_data.get("name", story_location.get("name", "") if story_location else ""),
            "time_of_day": loc_data.get("time_of_day", story_location.get("time_of_day", "day") if story_location else "day"),
            "background_prompt": loc_data.get("background_prompt", ""),
            "background_image": None,
            "character_phase": loc_data.get("character_phase", 1),
        }

        # 添加节奏元数据
        if pacing_info:
            location["pacing"] = {
                "suggested_shot_count": pacing_info["suggested_shot_count"],
                "pacing_type": pacing_info["pacing_type"],
                "avg_intensity": pacing_info["avg_intensity"],
                "beat_types": pacing_info["beat_types"]
            }

        # 自动确定角色阶段
        if story_location and "character_phase" not in loc_data:
            beats = story_location.get("beats", [])
            if beats:
                main_char = next((c for c in story.get("characters", []) if c.get("role") == "主角"), None)
                if not main_char and story.get("characters"):
                    main_char = story["characters"][0]
                if main_char:
                    phase = get_character_phase_for_beat(story, main_char.get("name", ""), beats[0])
                    if phase:
                        location["character_phase"] = phase.get("phase_id", 1)

        # 处理镜头
        location["shots"] = []
        for i, shot in enumerate(loc_data.get("shots", [])):
            # 获取说话人（应在 AI 生成分镜时指定）
            speaker = get_speaker(shot, default_protagonist)

            shot_obj = {
                "shot_id": shot.get("shot_id", f"{loc_id}-{i + 1}"),
                "speaker": speaker,
                "composition": shot.get("composition", "medium shot"),
                "narration": normalize_chinese_punctuation(shot.get("narration", "")),
                "action": normalize_chinese_punctuation(shot.get("action", "")),
                "character_visible": shot.get("character_visible", True),
                "image_prompt": shot.get("image_prompt", ""),
                "video_prompt": shot.get("video_prompt", ""),
                "duration": shot.get("duration", DEFAULT_SHOT_DURATION),
                "image_path": None,
                "video_path": None,
            }

            # 处理 mood 字段（用于语音情绪控制）
            # 优先级：shot 直接指定 > beat 继承
            if "mood" in shot and shot["mood"]:
                shot_obj["mood"] = shot["mood"]

            if "source_beat" in shot:
                beat = get_beat_by_id(story, shot["source_beat"])
                if beat:
                    shot_obj["source_beat"] = shot["source_beat"]
                    # 如果 shot 没有明确指定 mood，从 beat 继承
                    if "mood" not in shot_obj and "mood" in beat:
                        shot_obj["mood"] = beat["mood"]

            # 处理旁白组字段（多图共享旁白）
            if "narration_group" in shot:
                shot_obj["narration_group"] = shot["narration_group"]
                shot_obj["group_position"] = shot.get("group_position", 1)
                shot_obj["group_total"] = shot.get("group_total", 1)

            # 估算配音时长（根据旁白文字长度和情绪语速）
            narration = shot_obj.get("narration", "")
            if narration:
                mood = shot_obj.get("mood", "neutral")
                rate, _ = get_mood_params(mood)
                shot_obj["estimated_duration"] = estimate_duration(narration, rate)
            else:
                # 无旁白默认 2 秒
                shot_obj["estimated_duration"] = 2.0

            # 初始化实际时长和显示时长字段（配音后填充）
            shot_obj["actual_duration"] = None
            shot_obj["display_duration"] = shot_obj["estimated_duration"]

            location["shots"].append(shot_obj)

        screenplay["locations"].append(location)

    # 计算元数据
    total_shots = sum(len(loc.get("shots", [])) for loc in screenplay["locations"])
    screenplay["total_locations"] = len(screenplay["locations"])
    screenplay["total_shots"] = total_shots
    screenplay["target_duration"] = sum(
        shot.get("duration", DEFAULT_SHOT_DURATION)
        for loc in screenplay["locations"]
        for shot in loc.get("shots", [])
    )

    return screenplay


def create_shots(data: dict) -> bool:
    """创建完整剧本文件"""
    # 加载故事大纲
    try:
        output_dir = data.get("output_dir")
        story = load_story_outline(Path(output_dir) if output_dir else None)
    except SystemExit:
        return False

    # 验证
    errors = validate_shots_data(data)
    if errors:
        print("分镜验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False

    # 合并
    screenplay = merge_story_and_shots(story, data)

    # 自动注入角色锚定特征到 image_prompt
    screenplay = inject_anchor_features_to_shots(screenplay, story)
    print("已自动注入角色锚定特征到 image_prompt")

    # 更新任务 ID
    screenplay["task_id"] = f"manga_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 保存
    output_dir = Path(screenplay.get("output_dir", "output"))
    screenplay_path = output_dir / "screenplay.json"
    with open(screenplay_path, "w", encoding="utf-8") as f:
        json.dump(screenplay, f, ensure_ascii=False, indent=2)

    project_ref = {"project_path": str(output_dir)}
    with open(SCREENPLAY_PATH, "w", encoding="utf-8") as f:
        json.dump(project_ref, f, ensure_ascii=False, indent=2)

    # 输出摘要
    print(f"\n剧本已保存: {screenplay_path}")
    print(f"\n=== 剧本摘要 ===")
    print(f"标题: {screenplay.get('title', '未命名')}")
    print(f"场景数量: {screenplay.get('total_locations', 0)}")
    print(f"镜头数量: {screenplay.get('total_shots', 0)}")
    print(f"目标时长: {screenplay.get('target_duration', 0)} 秒")

    print(f"\n=== 角色阶段 ===")
    for phase in screenplay.get("character_phases", []):
        print(f"  阶段 {phase.get('phase_id')}: {phase.get('character')} - {phase.get('name')}")

    # 输出节奏分析
    print(f"\n=== 节奏分析 ===")
    pacing_distribution = {"slow": 0, "moderate": 0, "fast": 0}
    pacing_warnings = []

    for location in screenplay.get("locations", []):
        loc_id = location.get("location_id")
        loc_name = location.get("name")
        shot_count = len(location.get("shots", []))
        pacing = location.get("pacing", {})

        if pacing:
            pacing_type = pacing.get("pacing_type", "moderate")
            avg_intensity = pacing.get("avg_intensity", 0.5)
            suggested = pacing.get("suggested_shot_count", 3)
            beat_types = ", ".join(pacing.get("beat_types", []))

            pacing_distribution[pacing_type] += 1

            # 检查实际镜头数与建议的偏差
            diff = shot_count - suggested
            status = "✓" if abs(diff) <= 1 else ("↑" if diff > 0 else "↓")

            print(f"  场景 {loc_id}: {loc_name} ({beat_types})")
            print(f"    强度: {avg_intensity:.2f}, 节奏: {pacing_type}, 建议: {suggested} 镜头, 实际: {shot_count} {status}")

            if abs(diff) > 2:
                pacing_warnings.append(
                    f"场景 {loc_id} 镜头数偏差较大: 建议 {suggested}, 实际 {shot_count}"
                )
        else:
            print(f"  场景 {loc_id}: {loc_name}")
            print(f"    (无节奏信息)")

    # 输出节奏分布
    total_scenes = sum(pacing_distribution.values())
    if total_scenes > 0:
        print(f"\n=== 节奏分布 ===")
        slow_pct = pacing_distribution["slow"] / total_scenes * 100
        moderate_pct = pacing_distribution["moderate"] / total_scenes * 100
        fast_pct = pacing_distribution["fast"] / total_scenes * 100
        print(f"  慢: {pacing_distribution['slow']} ({slow_pct:.0f}%) | "
              f"中: {pacing_distribution['moderate']} ({moderate_pct:.0f}%) | "
              f"快: {pacing_distribution['fast']} ({fast_pct:.0f}%)")

        # 检查节奏分布是否均衡
        types_with_scenes = sum(1 for count in pacing_distribution.values() if count > 0)
        if types_with_scenes >= 2:
            print(f"  ✓ 节奏分布均衡")
        else:
            print(f"  ! 节奏分布单一，建议增加变化")

        # 检查是否缺少高潮或慢节奏
        if pacing_distribution["fast"] == 0 and total_scenes > 2:
            pacing_warnings.append("缺少快节奏场景（高潮/动作），故事可能显得平淡")
        if pacing_distribution["slow"] == 0 and total_scenes > 2:
            pacing_warnings.append("缺少慢节奏场景，故事可能显得过于紧凑")

    # 输出节奏警告
    if pacing_warnings:
        print(f"\n=== 节奏提示 ===")
        for warning in pacing_warnings:
            print(f"  ! {warning}")

    # 输出语音配置
    print(f"\n=== 语音配置 ===")
    for char_name, voice_id in screenplay.get("voice_config", {}).items():
        voice_info = AVAILABLE_VOICES.get(voice_id, {})
        print(f"  {char_name}: {voice_id} ({voice_info.get('description', '')})")

    # 情绪统计
    mood_counts = {}
    for location in screenplay.get("locations", []):
        for shot in location.get("shots", []):
            mood = shot.get("mood", "未指定")
            mood_counts[mood] = mood_counts.get(mood, 0) + 1

    if mood_counts:
        print(f"\n=== 情绪分布 ===")
        for mood, count in sorted(mood_counts.items(), key=lambda x: -x[1]):
            pct = count / screenplay.get("total_shots", 1) * 100
            print(f"  {mood}: {count} ({pct:.1f}%)")

    # 估算时长统计
    print(f"\n=== 估算配音时长 ===")
    total_estimated = 0
    for location in screenplay.get("locations", []):
        loc_id = location.get("location_id")
        loc_name = location.get("name")
        loc_estimated = sum(shot.get("estimated_duration", 0) for shot in location.get("shots", []))
        total_estimated += loc_estimated
        print(f"  场景 {loc_id}: {loc_name} - 估算 {loc_estimated:.1f} 秒")
    print(f"  总计: {total_estimated:.1f} 秒 ({total_estimated/60:.1f} 分钟)")

    print(f"\n=== 场景列表 ===")
    for location in screenplay.get("locations", []):
        loc_id = location.get("location_id")
        loc_name = location.get("name")
        shot_count = len(location.get("shots", []))
        print(f"  场景 {loc_id}: {loc_name} ({shot_count} 个镜头)")
        for shot in location.get("shots", []):
            speaker = shot.get('speaker', '?')
            mood = shot.get('mood', '-')
            est_dur = shot.get('estimated_duration', 0)
            print(f"      镜头 {shot.get('shot_id')}: [{speaker}] ({mood}) {est_dur:.1f}s - {shot.get('narration', '')[:20]}...")

    return True


def main():
    if sys.stdin.isatty():
        print("用法: echo '<json>' | python manga_create_shots.py")
        print("\n输入格式:")
        print('''{
  "locations": [
    {
      "location_id": 1,
      "name": "暴风雨海面",
      "time_of_day": "night",
      "background_prompt": "anime style, stormy night sea, no characters...",
      "character_phase": 1,
      "shots": [
        {
          "shot_id": "1-1",
          "composition": "wide shot",
          "narration": "暴风雨来得那么突然……",
          "action": "游轮在风浪中摇晃",
          "character_visible": false,
          "mood": "tense",
          "image_prompt": "anime style, ...",
          "video_prompt": "[Wide shot] ..."
        }
      ]
    }
  ]
}''')
        print("\n可用 mood 值（用于语音情绪控制）:")
        print("  激动类: excited, battle, surprise, angry")
        print("  悲伤类: sad, melancholy, farewell, loss")
        print("  温柔类: tender, romantic, warm, love")
        print("  紧张类: tense, urgent, chase, danger, suspense")
        print("  平静类: calm, neutral, narration, peaceful")
        print("  欢快类: happy, joyful, playful")
        print("  其他类: mysterious, solemn, epic")
        sys.exit(1)

    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        sys.exit(1)

    success = create_shots(data)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
