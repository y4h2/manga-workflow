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
    load_story_outline,
    get_beat_by_id,
    get_character_phase_for_beat,
    build_phase_appearance_prompt,
    build_anchor_prompt,
    inject_anchor_to_prompt,
)


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

        location = {
            "location_id": loc_id,
            "name": loc_data.get("name", story_location.get("name", "") if story_location else ""),
            "time_of_day": loc_data.get("time_of_day", story_location.get("time_of_day", "day") if story_location else "day"),
            "background_prompt": loc_data.get("background_prompt", ""),
            "background_image": None,
            "character_phase": loc_data.get("character_phase", 1),
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
            shot_obj = {
                "shot_id": shot.get("shot_id", f"{loc_id}-{i + 1}"),
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

            if "source_beat" in shot:
                beat = get_beat_by_id(story, shot["source_beat"])
                if beat:
                    shot_obj["source_beat"] = shot["source_beat"]
                    if "mood" in beat:
                        shot_obj["mood"] = beat["mood"]

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

    print(f"\n=== 场景列表 ===")
    for location in screenplay.get("locations", []):
        loc_id = location.get("location_id")
        loc_name = location.get("name")
        shot_count = len(location.get("shots", []))
        print(f"  场景 {loc_id}: {loc_name} ({shot_count} 个镜头)")
        for shot in location.get("shots", []):
            print(f"      镜头 {shot.get('shot_id')}: [{shot.get('composition')}] {shot.get('narration', '')[:30]}...")

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
          "image_prompt": "anime style, ...",
          "video_prompt": "[Wide shot] ..."
        }
      ]
    }
  ]
}''')
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
