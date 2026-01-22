#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 漫剧生成 - 剧本一致性验证脚本

验证剧本的角色一致性、叙事节奏、Prompt 格式和旁白质量。

用法:
  python .claude/scripts/manga_validate.py [screenplay_path]

如果不提供路径，将从当前目录读取 screenplay.json
"""

import sys
from pathlib import Path

from manga_common import (
    load_screenplay,
    load_story_outline,
    validate_screenplay,
    validate_character_consistency,
    validate_pacing,
    validate_prompts,
    validate_narration,
    build_anchor_prompt,
    get_suggested_shot_count,
    analyze_pacing_distribution,
    PACING_TYPES,
)


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print('=' * 50)


def validate_story_outline(story: dict) -> tuple:
    """验证故事大纲中的角色锚定特征

    Args:
        story: 故事大纲数据

    Returns:
        (errors, warnings) 元组
    """
    errors = []
    warnings = []

    characters = story.get("characters", [])
    if not characters:
        warnings.append("故事大纲中没有定义角色")
        return errors, warnings

    for char in characters:
        name = char.get("name", "未知角色")
        role = char.get("role", "")

        # 检查主角是否有锚定特征
        anchor = build_anchor_prompt(char)
        if not anchor:
            if role == "主角":
                errors.append(f"主角 '{name}' 缺少 anchor_features 定义")
            else:
                warnings.append(f"角色 '{name}' 缺少 anchor_features 定义")
        else:
            # 检查锚定特征的完整性
            anchor_features = char.get("anchor_features", {})
            if not anchor_features.get("face"):
                warnings.append(f"角色 '{name}' 缺少面部特征 (face)")
            if not anchor_features.get("hair"):
                warnings.append(f"角色 '{name}' 缺少发型特征 (hair)")

    # 检查故事节拍的 intensity 字段
    beats = story.get("story_beats", [])
    beats_with_intensity = [b for b in beats if "intensity" in b]
    if not beats_with_intensity and beats:
        warnings.append("故事节拍缺少 intensity 字段，建议添加以控制叙事节奏")
    elif beats_with_intensity:
        # 检查 intensity 范围
        for beat in beats_with_intensity:
            intensity = beat.get("intensity", 0.5)
            if not (0 <= intensity <= 1):
                errors.append(f"Beat {beat.get('beat_id')}: intensity 值 {intensity} 超出有效范围 (0-1)")

    return errors, warnings


def validate_pacing_rhythm(screenplay: dict, story: dict = None) -> tuple:
    """验证节奏分配是否合理

    检查:
    1. 实际镜头数与建议的偏差
    2. 节奏分布是否均衡
    3. 是否缺少高潮或慢节奏场景

    Args:
        screenplay: 剧本数据
        story: 故事大纲数据，如果为 None 将尝试加载

    Returns:
        (errors, warnings) 元组
    """
    errors = []
    warnings = []

    # 如果没有提供 story，尝试加载
    if story is None:
        output_dir = screenplay.get("output_dir")
        if output_dir:
            try:
                story = load_story_outline(Path(output_dir))
            except SystemExit:
                warnings.append("无法加载故事大纲，跳过节奏分析")
                return errors, warnings
        else:
            warnings.append("无 output_dir，无法进行节奏分析")
            return errors, warnings

    # 分析每个场景的节奏
    locations = screenplay.get("locations", [])
    if not locations:
        return errors, warnings

    pacing_distribution = {"slow": 0, "moderate": 0, "fast": 0}
    shot_count_deviations = []

    print("\n  节奏详情:")
    for location in locations:
        loc_id = location.get("location_id")
        loc_name = location.get("name", f"场景 {loc_id}")
        actual_shots = len(location.get("shots", []))

        # 查找故事中的对应场景
        story_location = None
        for story_loc in story.get("locations", []):
            if story_loc.get("location_id") == loc_id:
                story_location = story_loc
                break

        if story_location:
            pacing_info = get_suggested_shot_count(story, story_location)
            pacing_type = pacing_info["pacing_type"]
            suggested = pacing_info["suggested_shot_count"]
            avg_intensity = pacing_info["avg_intensity"]
            beat_types = pacing_info.get("beat_types", [])

            pacing_distribution[pacing_type] += 1

            deviation = actual_shots - suggested
            shot_count_deviations.append({
                "location_id": loc_id,
                "name": loc_name,
                "suggested": suggested,
                "actual": actual_shots,
                "deviation": deviation,
                "pacing_type": pacing_type
            })

            # 输出场景节奏信息
            beat_types_str = ", ".join(beat_types) if beat_types else "-"
            status = "✓" if abs(deviation) <= 1 else ("↑" if deviation > 0 else "↓")
            print(f"    场景 {loc_id}: {loc_name}")
            print(f"      节拍: {beat_types_str} | 强度: {avg_intensity:.2f} | 节奏: {pacing_type}")
            print(f"      建议: {suggested} 镜头 | 实际: {actual_shots} 镜头 {status}")

            # 检查偏差
            if abs(deviation) > 2:
                warnings.append(
                    f"场景 {loc_id} '{loc_name}' 镜头数偏差较大: "
                    f"建议 {suggested} (基于 {pacing_type} 节奏), 实际 {actual_shots}"
                )
        else:
            # 使用剧本中已保存的 pacing 元数据
            pacing = location.get("pacing", {})
            if pacing:
                pacing_type = pacing.get("pacing_type", "moderate")
                suggested = pacing.get("suggested_shot_count", 3)
                pacing_distribution[pacing_type] += 1

                deviation = actual_shots - suggested
                status = "✓" if abs(deviation) <= 1 else ("↑" if deviation > 0 else "↓")
                print(f"    场景 {loc_id}: {loc_name}")
                print(f"      节奏: {pacing_type} | 建议: {suggested} | 实际: {actual_shots} {status}")
            else:
                print(f"    场景 {loc_id}: {loc_name} (无节奏信息)")

    # 输出节奏分布
    total = sum(pacing_distribution.values())
    if total > 0:
        print("\n  节奏分布:")
        for pacing_type, count in pacing_distribution.items():
            pct = count / total * 100
            desc = PACING_TYPES[pacing_type]["description"]
            print(f"    {pacing_type}: {count} ({pct:.0f}%) - {desc}")

        # 检查是否均衡
        types_with_scenes = sum(1 for count in pacing_distribution.values() if count > 0)
        if types_with_scenes >= 2:
            print("    ✓ 节奏分布均衡")
        else:
            warnings.append("节奏分布过于单一，建议增加节奏变化")

        # 检查是否缺少关键节奏
        if pacing_distribution["fast"] == 0 and total > 2:
            warnings.append("缺少快节奏场景（高潮/动作），故事可能显得平淡")

        if pacing_distribution["slow"] == 0 and total > 2:
            warnings.append("缺少慢节奏场景，故事可能显得过于紧凑")

    return errors, warnings


def main():
    """主函数"""
    # 加载剧本
    try:
        screenplay = load_screenplay()
    except SystemExit:
        print("错误: 无法加载剧本文件")
        sys.exit(1)

    title = screenplay.get("title", "Unknown")
    print(f"\n{'*' * 60}")
    print(f"  验证剧本: {title}")
    print(f"{'*' * 60}")

    all_errors = []
    all_warnings = []

    # 1. 验证故事大纲
    output_dir = screenplay.get("output_dir")
    if output_dir:
        print_section("检查故事大纲")
        try:
            story = load_story_outline(Path(output_dir))
            errors, warnings = validate_story_outline(story)
            all_errors.extend(errors)
            all_warnings.extend(warnings)
            if not errors and not warnings:
                print("  ✓ 故事大纲结构完整")
            else:
                if errors:
                    for err in errors:
                        print(f"  ✗ {err}")
                if warnings:
                    for warn in warnings:
                        print(f"  ! {warn}")
        except SystemExit:
            print("  跳过：无法加载故事大纲")

    # 2. 角色一致性检查
    print_section("检查角色一致性")
    errors, warnings = validate_character_consistency(screenplay)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    if not errors and not warnings:
        print("  ✓ 角色一致性良好")
    else:
        if errors:
            for err in errors:
                print(f"  ✗ {err}")
        if warnings:
            for warn in warnings:
                print(f"  ! {warn}")

    # 3. 节奏检查
    print_section("检查叙事节奏")
    errors, warnings = validate_pacing(screenplay)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    if not errors and not warnings:
        print("  ✓ 叙事节奏良好")
    else:
        if errors:
            for err in errors:
                print(f"  ✗ {err}")
        if warnings:
            for warn in warnings:
                print(f"  ! {warn}")

    # 4. Prompt 格式检查
    print_section("检查 Prompt 格式")
    errors, warnings = validate_prompts(screenplay)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    if not errors and not warnings:
        print("  ✓ Prompt 格式正确")
    else:
        if errors:
            for err in errors:
                print(f"  ✗ {err}")
        if warnings:
            for warn in warnings:
                print(f"  ! {warn}")

    # 5. 旁白质量检查
    print_section("检查旁白质量")
    errors, warnings = validate_narration(screenplay)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    if not errors and not warnings:
        print("  ✓ 旁白质量良好")
    else:
        if errors:
            for err in errors:
                print(f"  ✗ {err}")
        if warnings:
            for warn in warnings:
                print(f"  ! {warn}")

    # 6. 节奏分配检查
    print_section("检查节奏分配")
    try:
        story = load_story_outline(Path(output_dir)) if output_dir else None
        errors, warnings = validate_pacing_rhythm(screenplay, story)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        if not errors and not warnings:
            print("  ✓ 节奏分配合理")
        else:
            if errors:
                for err in errors:
                    print(f"  ✗ {err}")
            if warnings:
                for warn in warnings:
                    print(f"  ! {warn}")
    except SystemExit:
        print("  跳过：无法加载故事大纲")

    # 汇总
    print_section("验证结果汇总")

    if not all_errors and not all_warnings:
        print("\n  ✅ 剧本验证通过！没有发现问题。\n")
        sys.exit(0)
    elif not all_errors:
        print(f"\n  ✅ 剧本基本验证通过")
        print(f"     但有 {len(all_warnings)} 个警告需要注意。")
        print("\n  建议检查以上警告，优化剧本质量。\n")
        sys.exit(0)
    else:
        print(f"\n  ❌ 剧本验证失败")
        print(f"     {len(all_errors)} 个错误，{len(all_warnings)} 个警告")
        print("\n  请修复以上错误后重新验证。\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
