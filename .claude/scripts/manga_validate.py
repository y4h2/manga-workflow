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
