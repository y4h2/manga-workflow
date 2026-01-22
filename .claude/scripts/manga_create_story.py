#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 漫剧生成 - 故事大纲创建脚本 (阶段 0)
从标准输入读取故事 JSON，验证并保存到 story_outline.json
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from manga_common import (
    SCREENPLAY_PATH,
    DEFAULT_STYLE_KEYWORDS,
    DEFAULT_ASPECT_RATIO,
    VALID_ASPECT_RATIOS,
    VALID_BEAT_TYPES,
    VALID_MOODS,
    VALID_TIME_OF_DAY,
    create_output_subdir,
    migrate_flat_locations,
)


def normalize_chinese_punctuation(text: str) -> str:
    """
    规范化中文标点符号
    将中文字符附近的英文标点转换为中文标点
    """
    if not text:
        return text

    # 英文 -> 中文标点映射
    punctuation_map = {
        ",": "\uff0c",  # 中文逗号
        ".": "\u3002",  # 中文句号
        "!": "\uff01",  # 中文感叹号
        "?": "\uff1f",  # 中文问号
        ":": "\uff1a",  # 中文冒号
        ";": "\uff1b",  # 中文分号
        "(": "\uff08",  # 中文左括号
        ")": "\uff09",  # 中文右括号
        "[": "\u3010",  # 中文左方括号
        "]": "\u3011",  # 中文右方括号
        '"': "\u201c",  # 中文左引号
    }

    result = text

    # 仅替换中文字符附近的标点
    for eng, chn in punctuation_map.items():
        # 中文字符后的英文标点 -> 中文标点
        pattern = f"([\u4e00-\u9fff]){re.escape(eng)}"
        result = re.sub(pattern, f"\\1{chn}", result)

        # 中文字符前的英文标点 -> 中文标点
        pattern = f"{re.escape(eng)}([\u4e00-\u9fff])"
        result = re.sub(pattern, f"{chn}\\1", result)

    # 处理引号配对
    quote_count = 0
    chars = list(result)
    for i, char in enumerate(chars):
        if char == '"' or char == "\u201c" or char == "\u201d":
            if quote_count % 2 == 0:
                chars[i] = "\u201c"  # 左引号
            else:
                chars[i] = "\u201d"  # 右引号
            quote_count += 1
    result = "".join(chars)

    # 处理省略号
    result = result.replace("...", "\u2026\u2026")

    # 处理破折号
    result = result.replace("--", "\u2014\u2014")

    return result


def validate_character_phase(phase: dict, char_name: str, index: int) -> list:
    """验证角色阶段定义

    Args:
        phase: 阶段数据
        char_name: 角色名称
        index: 阶段索引

    Returns:
        错误列表
    """
    errors = []
    prefix = f"角色 '{char_name}' 阶段 {index + 1}"

    # 必需字段
    required_fields = ["phase_id", "name", "beat_range", "appearance"]
    for field in required_fields:
        if field not in phase:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")
        elif field != "phase_id" and field != "beat_range" and not phase[field]:
            errors.append(f"{prefix}: 字段 '{field}' 不能为空")

    # 验证 beat_range 格式
    if "beat_range" in phase:
        beat_range = phase["beat_range"]
        if not isinstance(beat_range, list) or len(beat_range) != 2:
            errors.append(f"{prefix}: beat_range 必须是包含两个数字的数组 [start, end]")
        elif beat_range[0] > beat_range[1]:
            errors.append(f"{prefix}: beat_range 起始值不能大于结束值")

    return errors


def validate_anchor_features(anchor: dict, char_name: str) -> list:
    """验证角色锚定特征

    Args:
        anchor: anchor_features 数据
        char_name: 角色名称

    Returns:
        警告列表（锚定特征是可选的，所以只返回警告）
    """
    warnings = []
    prefix = f"角色 '{char_name}'"

    if not anchor:
        return warnings

    # 检查推荐的字段
    recommended_fields = ["face", "hair"]
    for field in recommended_fields:
        if field not in anchor or not anchor[field]:
            warnings.append(f"{prefix}: 建议添加 anchor_features.{field} 以提高角色一致性")

    # 检查特征描述是否使用英文
    for field, value in anchor.items():
        if value and any('\u4e00' <= c <= '\u9fff' for c in value):
            warnings.append(f"{prefix}: anchor_features.{field} 建议使用英文描述")

    return warnings


def validate_character(char: dict, index: int) -> list:
    """验证单个角色定义

    Args:
        char: 角色数据
        index: 角色索引

    Returns:
        错误列表
    """
    errors = []
    prefix = f"Character {index + 1}"
    char_name = char.get("name", "未知")

    # 必需字段
    required_fields = ["name", "appearance"]
    for field in required_fields:
        if field not in char:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")
        elif not char[field]:
            errors.append(f"{prefix}: 字段 '{field}' 不能为空")

    # 验证 anchor_features（可选但建议）
    if "anchor_features" in char:
        anchor_warnings = validate_anchor_features(char["anchor_features"], char_name)
        for warn in anchor_warnings:
            print(f"警告: {warn}")
    elif char.get("role") == "主角":
        print(f"警告: 主角 '{char_name}' 缺少 anchor_features，建议添加以提高角色一致性")

    # 验证 phases（可选，但如果存在需要验证）
    if "phases" in char:
        phases = char["phases"]
        if not isinstance(phases, list):
            errors.append(f"{prefix}: phases 必须是数组")
        else:
            for i, phase in enumerate(phases):
                phase_errors = validate_character_phase(phase, char_name, i)
                errors.extend(phase_errors)

    return errors


def validate_location(location: dict, index: int, total_beats: int) -> list:
    """验证场景/地点定义

    Args:
        location: 场景数据
        index: 场景索引
        total_beats: 故事节拍总数

    Returns:
        错误列表
    """
    errors = []
    loc_id = location.get("location_id", index + 1)
    prefix = f"Location {loc_id}"

    # 必需字段
    required_fields = ["location_id", "name", "description", "beats"]
    for field in required_fields:
        if field not in location:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")
        elif field != "location_id" and field != "beats" and not location[field]:
            errors.append(f"{prefix}: 字段 '{field}' 不能为空")

    # 验证 time_of_day（可选但如果存在需要有效）
    if "time_of_day" in location:
        time_of_day = location["time_of_day"].lower()
        valid_times_lower = [t.lower() for t in VALID_TIME_OF_DAY]
        if time_of_day not in valid_times_lower:
            errors.append(
                f"{prefix}: 无效的 time_of_day '{location['time_of_day']}'。"
                f"有效值: {VALID_TIME_OF_DAY}"
            )

    # 验证 beats 是有效的节拍 ID 列表
    if "beats" in location:
        beats = location["beats"]
        if not isinstance(beats, list):
            errors.append(f"{prefix}: beats 必须是数组")
        elif len(beats) == 0:
            errors.append(f"{prefix}: beats 不能为空")
        else:
            for beat_id in beats:
                if not isinstance(beat_id, int):
                    errors.append(f"{prefix}: beats 数组中的元素必须是整数")
                    break
                if beat_id < 1 or beat_id > total_beats:
                    errors.append(f"{prefix}: beat_id {beat_id} 超出有效范围 (1-{total_beats})")

    return errors


def validate_world_map(world_map: dict) -> list:
    """验证世界地图定义

    Args:
        world_map: world_map 数据

    Returns:
        错误列表
    """
    errors = []

    if not world_map:
        # world_map 是可选的，没有则跳过
        return errors

    prefix = "world_map"

    # 必需字段
    required_fields = ["world_id", "name", "description"]
    for field in required_fields:
        if field not in world_map:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")
        elif field != "world_id" and not world_map[field]:
            errors.append(f"{prefix}: 字段 '{field}' 不能为空")

    # 验证 style_base（可选但建议）
    style_base = world_map.get("style_base", {})
    if style_base:
        recommended_fields = ["color_palette", "art_style"]
        for field in recommended_fields:
            if field not in style_base or not style_base[field]:
                print(f"警告: {prefix}.style_base 建议添加 '{field}' 以确保风格一致性")

    # 验证 geography_anchors（可选）
    geo_anchors = world_map.get("geography_anchors", [])
    if geo_anchors and not isinstance(geo_anchors, list):
        errors.append(f"{prefix}: geography_anchors 必须是数组")

    return errors


def validate_region(region: dict, index: int, location_ids: set, world_id: int = None) -> list:
    """验证区域定义

    Args:
        region: 区域数据
        index: 区域索引
        location_ids: 有效的场景 ID 集合
        world_id: 世界 ID（用于验证 parent_world）

    Returns:
        错误列表
    """
    errors = []
    region_id = region.get("region_id", index + 1)
    prefix = f"Region {region_id}"

    # 必需字段
    required_fields = ["region_id", "name", "description"]
    for field in required_fields:
        if field not in region:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")
        elif field != "region_id" and not region[field]:
            errors.append(f"{prefix}: 字段 '{field}' 不能为空")

    # 验证 parent_world（如果世界地图存在）
    if world_id is not None and "parent_world" in region:
        if region["parent_world"] != world_id:
            errors.append(f"{prefix}: parent_world ({region['parent_world']}) 与 world_map.world_id ({world_id}) 不匹配")

    # 验证 locations 数组
    if "locations" in region:
        region_locations = region["locations"]
        if not isinstance(region_locations, list):
            errors.append(f"{prefix}: locations 必须是数组")
        else:
            for loc_id in region_locations:
                if not isinstance(loc_id, int):
                    errors.append(f"{prefix}: locations 数组中的元素必须是整数")
                    break
                if loc_id not in location_ids:
                    errors.append(f"{prefix}: location_id {loc_id} 在 locations 中不存在")

    # 验证 style_modifiers（可选）
    style_modifiers = region.get("style_modifiers", {})
    if style_modifiers and not isinstance(style_modifiers, dict):
        errors.append(f"{prefix}: style_modifiers 必须是对象")

    # 验证 geography（可选）
    geography = region.get("geography", {})
    if geography and not isinstance(geography, dict):
        errors.append(f"{prefix}: geography 必须是对象")

    return errors


def validate_layered_map_consistency(data: dict) -> list:
    """验证分层地图系统的一致性

    检查 world_map、regions 和 locations 之间的关系是否正确

    Args:
        data: 故事大纲数据

    Returns:
        错误列表
    """
    errors = []

    world_map = data.get("world_map", {})
    regions = data.get("regions", [])
    locations = data.get("locations", [])

    # 如果没有分层地图系统，跳过验证
    if not world_map and not regions:
        return errors

    # 收集所有 location_id
    all_location_ids = set(loc.get("location_id", i + 1) for i, loc in enumerate(locations))

    # 收集所有 region_id
    all_region_ids = set(r.get("region_id", i + 1) for i, r in enumerate(regions))

    # 验证：每个 location 的 region_id 必须有效
    for loc in locations:
        region_id = loc.get("region_id")
        if region_id is not None and region_id not in all_region_ids:
            errors.append(f"Location {loc.get('location_id')}: region_id {region_id} 在 regions 中不存在")

    # 验证：每个 region 中引用的 location 必须存在
    all_locations_in_regions = set()
    for region in regions:
        region_id = region.get("region_id")
        region_locations = region.get("locations", [])
        for loc_id in region_locations:
            if loc_id not in all_location_ids:
                errors.append(f"Region {region_id}: locations 中引用的 location_id {loc_id} 不存在")
            all_locations_in_regions.add(loc_id)

    # 警告：检查是否有 location 没有被任何 region 引用
    # 同时也检查 location 的 region_id 字段
    for loc in locations:
        loc_id = loc.get("location_id")
        region_id = loc.get("region_id")
        in_region_list = loc_id in all_locations_in_regions
        has_region_id = region_id is not None

        if not in_region_list and not has_region_id and regions:
            print(f"警告: Location {loc_id} 未被任何 region 引用，也没有设置 region_id")

    return errors


def validate_narrative_arc(arc: dict) -> list:
    """验证叙事结构

    Args:
        arc: narrative_arc 数据

    Returns:
        错误列表
    """
    errors = []

    if not arc:
        errors.append("缺少 narrative_arc 字段")
        return errors

    # 五段式结构必需字段
    required_parts = ["setup", "inciting_incident", "rising_action", "climax", "resolution"]
    for part in required_parts:
        if part not in arc:
            errors.append(f"narrative_arc 缺少 '{part}' 部分")
        elif not arc[part]:
            errors.append(f"narrative_arc.{part} 不能为空")

    return errors


def validate_story_beat(beat: dict, index: int) -> list:
    """验证单个故事节拍

    Args:
        beat: 节拍数据
        index: 节拍索引

    Returns:
        错误列表
    """
    errors = []
    beat_id = beat.get("beat_id", index + 1)
    prefix = f"Beat {beat_id}"

    # 必需字段
    required_fields = ["beat_id", "narration", "description", "mood"]
    for field in required_fields:
        if field not in beat:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")
        elif field != "beat_id" and not beat[field]:
            errors.append(f"{prefix}: 字段 '{field}' 不能为空")

    # 验证 beat_type (可选但如果存在需要有效)
    if "beat_type" in beat:
        if beat["beat_type"] not in VALID_BEAT_TYPES:
            errors.append(
                f"{prefix}: 无效的 beat_type '{beat['beat_type']}'。"
                f"有效值: {VALID_BEAT_TYPES}"
            )

    # 验证 intensity（可选但如果存在需要在有效范围内）
    if "intensity" in beat:
        intensity = beat["intensity"]
        if not isinstance(intensity, (int, float)):
            errors.append(f"{prefix}: intensity 必须是数字")
        elif intensity < 0 or intensity > 1:
            errors.append(f"{prefix}: intensity 值 {intensity} 超出有效范围 (0-1)")

    # 验证 suggested_duration（可选但如果存在需要在有效范围内）
    if "suggested_duration" in beat:
        duration = beat["suggested_duration"]
        if not isinstance(duration, (int, float)):
            errors.append(f"{prefix}: suggested_duration 必须是数字")
        elif duration < 1 or duration > 10:
            errors.append(f"{prefix}: suggested_duration 值 {duration} 超出有效范围 (1-10秒)")

    # 验证 mood
    if "mood" in beat and beat["mood"]:
        mood = beat["mood"].lower()
        valid_moods_lower = [m.lower() for m in VALID_MOODS]
        if mood not in valid_moods_lower:
            # 只是警告，不是错误，因为情绪可以自定义
            print(f"警告: {prefix} 使用了非标准 mood '{beat['mood']}'")

    return errors


def validate_story(data: dict) -> list:
    """验证故事大纲结构

    Args:
        data: 故事大纲数据

    Returns:
        错误列表
    """
    errors = []

    # 必需的顶层字段
    required_top_fields = ["title", "premise", "characters", "narrative_arc", "story_beats"]
    for field in required_top_fields:
        if field not in data:
            errors.append(f"缺少必需字段: {field}")

    # 如果缺少关键字段，提前返回
    if errors:
        return errors

    # 验证 title 和 premise
    if not data.get("title"):
        errors.append("title 不能为空")
    if not data.get("premise"):
        errors.append("premise 不能为空")

    # 验证 characters
    if not isinstance(data.get("characters"), list):
        errors.append("characters 必须是数组")
    elif len(data["characters"]) == 0:
        errors.append("characters 不能为空")
    else:
        for i, char in enumerate(data["characters"]):
            char_errors = validate_character(char, i)
            errors.extend(char_errors)

    # 验证 narrative_arc
    arc_errors = validate_narrative_arc(data.get("narrative_arc", {}))
    errors.extend(arc_errors)

    # 验证 story_beats
    if not isinstance(data.get("story_beats"), list):
        errors.append("story_beats 必须是数组")
    elif len(data["story_beats"]) == 0:
        errors.append("story_beats 不能为空")
    else:
        for i, beat in enumerate(data["story_beats"]):
            beat_errors = validate_story_beat(beat, i)
            errors.extend(beat_errors)

    # 验证 locations（可选，但如果存在需要验证）
    total_beats = len(data.get("story_beats", []))
    if "locations" in data:
        locations = data["locations"]
        if not isinstance(locations, list):
            errors.append("locations 必须是数组")
        else:
            for i, location in enumerate(locations):
                loc_errors = validate_location(location, i, total_beats)
                errors.extend(loc_errors)

            # 检查所有节拍是否都被 location 覆盖
            all_beats_in_locations = set()
            for loc in locations:
                all_beats_in_locations.update(loc.get("beats", []))

            all_beat_ids = set(beat.get("beat_id", i + 1) for i, beat in enumerate(data["story_beats"]))
            uncovered_beats = all_beat_ids - all_beats_in_locations
            if uncovered_beats:
                print(f"警告: 以下节拍未被任何 location 覆盖: {sorted(uncovered_beats)}")

    # 验证可选的 aspect_ratio
    if "aspect_ratio" in data:
        if data["aspect_ratio"] not in VALID_ASPECT_RATIOS:
            errors.append(
                f"无效的 aspect_ratio: {data['aspect_ratio']}。"
                f"有效值: {VALID_ASPECT_RATIOS}"
            )

    # 验证 world_map（可选）
    if "world_map" in data:
        world_map_errors = validate_world_map(data["world_map"])
        errors.extend(world_map_errors)

    # 验证 regions（可选）
    if "regions" in data:
        regions = data["regions"]
        if not isinstance(regions, list):
            errors.append("regions 必须是数组")
        else:
            # 收集 location_id 用于验证
            all_location_ids = set(
                loc.get("location_id", i + 1)
                for i, loc in enumerate(data.get("locations", []))
            )
            world_id = data.get("world_map", {}).get("world_id")

            for i, region in enumerate(regions):
                region_errors = validate_region(region, i, all_location_ids, world_id)
                errors.extend(region_errors)

    # 验证分层地图一致性
    consistency_errors = validate_layered_map_consistency(data)
    errors.extend(consistency_errors)

    return errors


def set_story_defaults(data: dict) -> dict:
    """设置故事大纲的默认值

    Args:
        data: 故事大纲数据

    Returns:
        补充默认值后的数据
    """
    # 顶层默认值
    if "style_keywords" not in data:
        data["style_keywords"] = DEFAULT_STYLE_KEYWORDS

    if "aspect_ratio" not in data:
        data["aspect_ratio"] = DEFAULT_ASPECT_RATIO

    # 确保每个 beat 有 beat_id
    for i, beat in enumerate(data.get("story_beats", [])):
        if "beat_id" not in beat:
            beat["beat_id"] = i + 1

    # 添加元数据
    if "total_beats" not in data:
        data["total_beats"] = len(data.get("story_beats", []))

    # 确保每个 location 有 location_id
    for i, location in enumerate(data.get("locations", [])):
        if "location_id" not in location:
            location["location_id"] = i + 1

    # 确保每个角色的 phase 有 phase_id
    for char in data.get("characters", []):
        for i, phase in enumerate(char.get("phases", [])):
            if "phase_id" not in phase:
                phase["phase_id"] = i + 1

    # 添加 locations 和 phases 元数据
    if "locations" in data:
        data["total_locations"] = len(data["locations"])

    # 统计角色阶段数
    total_phases = 0
    for char in data.get("characters", []):
        total_phases += len(char.get("phases", []))
    if total_phases > 0:
        data["total_character_phases"] = total_phases

    # 确保每个 region 有 region_id
    for i, region in enumerate(data.get("regions", [])):
        if "region_id" not in region:
            region["region_id"] = i + 1

    # 添加 regions 元数据
    if "regions" in data:
        data["total_regions"] = len(data["regions"])

    # 确保 world_map 有 world_id
    if "world_map" in data and data["world_map"]:
        if "world_id" not in data["world_map"]:
            data["world_map"]["world_id"] = 1

    return data


def process_chinese_text(data: dict) -> dict:
    """处理故事中的中文文本，规范化标点

    Args:
        data: 故事大纲数据

    Returns:
        处理后的数据
    """
    # 处理顶层中文字段
    chinese_fields = ["title", "premise"]
    for field in chinese_fields:
        if field in data and data[field]:
            data[field] = normalize_chinese_punctuation(data[field])

    # 处理 narrative_arc 中的中文
    if "narrative_arc" in data:
        for key, value in data["narrative_arc"].items():
            if value:
                data["narrative_arc"][key] = normalize_chinese_punctuation(value)

    # 处理 characters 中的中文
    for char in data.get("characters", []):
        for field in ["name", "role", "personality"]:
            if field in char and char[field]:
                char[field] = normalize_chinese_punctuation(char[field])

        # 处理角色的 phases
        for phase in char.get("phases", []):
            for field in ["name", "appearance"]:
                if field in phase and phase[field]:
                    phase[field] = normalize_chinese_punctuation(phase[field])

    # 处理 story_beats 中的中文
    for beat in data.get("story_beats", []):
        chinese_beat_fields = ["narration", "description", "location"]
        for field in chinese_beat_fields:
            if field in beat and beat[field]:
                beat[field] = normalize_chinese_punctuation(beat[field])

    # 处理 locations 中的中文
    for location in data.get("locations", []):
        for field in ["name", "description"]:
            if field in location and location[field]:
                location[field] = normalize_chinese_punctuation(location[field])

    # 处理 world_map 中的中文
    if "world_map" in data and data["world_map"]:
        for field in ["name", "description"]:
            if field in data["world_map"] and data["world_map"][field]:
                data["world_map"][field] = normalize_chinese_punctuation(data["world_map"][field])

    # 处理 regions 中的中文
    for region in data.get("regions", []):
        for field in ["name", "description"]:
            if field in region and region[field]:
                region[field] = normalize_chinese_punctuation(region[field])

    return data


def create_story(data: dict) -> bool:
    """创建故事大纲文件

    Args:
        data: 故事大纲数据

    Returns:
        是否成功
    """
    # 验证数据
    errors = validate_story(data)
    if errors:
        print("故事大纲验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False

    # 设置默认值
    data = set_story_defaults(data)

    # 创建输出目录
    title = data.get("title", "untitled")
    output_dir = create_output_subdir(title)
    data["output_dir"] = str(output_dir)
    print(f"输出目录: {output_dir}")

    # 添加任务 ID
    if "task_id" not in data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data["task_id"] = f"story_{timestamp}"

    # 处理中文标点
    data = process_chinese_text(data)

    # 写入故事大纲文件
    story_path = output_dir / "story_outline.json"
    with open(story_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 创建项目引用文件
    project_ref = {"project_path": str(output_dir)}
    with open(SCREENPLAY_PATH, "w", encoding="utf-8") as f:
        json.dump(project_ref, f, ensure_ascii=False, indent=2)

    # 输出摘要
    print(f"\n故事大纲已保存: {story_path}")
    print(f"项目引用: {SCREENPLAY_PATH}")
    print(f"\n=== 故事摘要 ===")
    print(f"标题: {data.get('title', '未命名')}")
    print(f"类型: {data.get('genre', '未指定')}")
    print(f"前提: {data.get('premise', '无')}")
    print(f"\n角色数量: {len(data.get('characters', []))}")
    for char in data.get("characters", []):
        phases = char.get("phases", [])
        if phases:
            print(f"  - {char.get('name', '?')}: {char.get('role', '?')} ({len(phases)} 个阶段)")
            for phase in phases:
                beat_range = phase.get("beat_range", [])
                print(f"      阶段 {phase.get('phase_id', '?')}: {phase.get('name', '?')} (节拍 {beat_range})")
        else:
            print(f"  - {char.get('name', '?')}: {char.get('role', '?')}")
    print(f"\n故事节拍: {data.get('total_beats', 0)} 个")

    # 显示世界地图信息
    world_map = data.get("world_map", {})
    if world_map:
        print(f"\n=== 世界地图 ===")
        print(f"  名称: {world_map.get('name', '?')}")
        print(f"  描述: {world_map.get('description', '?')[:50]}...")
        style_base = world_map.get("style_base", {})
        if style_base:
            print(f"  色调: {style_base.get('color_palette', '?')}")
            print(f"  风格: {style_base.get('art_style', '?')}")

    # 显示区域信息
    regions = data.get("regions", [])
    if regions:
        print(f"\n=== 区域 ({len(regions)} 个) ===")
        for region in regions:
            region_id = region.get("region_id", "?")
            name = region.get("name", "?")
            location_ids = region.get("locations", [])
            print(f"  区域 {region_id}: {name} (包含场景: {location_ids})")

    # 显示场景/地点信息
    locations = data.get("locations", [])
    if locations:
        print(f"\n=== 场景/地点 ({len(locations)} 个) ===")
        for loc in locations:
            loc_id = loc.get("location_id", "?")
            name = loc.get("name", "?")
            time_of_day = loc.get("time_of_day", "?")
            beats = loc.get("beats", [])
            region_id = loc.get("region_id", "?")
            region_info = f" [区域 {region_id}]" if region_id != "?" else ""
            print(f"  场景 {loc_id}: {name} [{time_of_day}]{region_info} (节拍: {beats})")

    # 显示叙事结构
    arc = data.get("narrative_arc", {})
    print(f"\n=== 叙事结构 ===")
    print(f"开场 (setup): {arc.get('setup', '?')[:50]}...")
    print(f"触发 (inciting_incident): {arc.get('inciting_incident', '?')[:50]}...")
    print(f"上升 (rising_action): {arc.get('rising_action', '?')[:50]}...")
    print(f"高潮 (climax): {arc.get('climax', '?')[:50]}...")
    print(f"结局 (resolution): {arc.get('resolution', '?')[:50]}...")

    return True


def main():
    """从标准输入读取 JSON 并创建故事大纲"""
    # 检查是否有管道输入
    if sys.stdin.isatty():
        print("用法: echo '<json>' | python manga_create_story.py")
        print("或者: cat story_data.json | python manga_create_story.py")
        sys.exit(1)

    # 读取标准输入
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data)
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        sys.exit(1)

    # 创建故事大纲
    success = create_story(data)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
