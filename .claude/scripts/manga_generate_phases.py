#!/usr/bin/env python3
"""
AI 漫剧生成 - 角色阶段参考图生成脚本 (阶段 1)
为角色的不同阶段生成参考图（三视图风格）

支持链式参考机制：
- 强制基础三视图依赖：生成阶段参考图前必须先有基础三视图
- 链式参考：阶段N参考阶段N-1的输出，保持角色一致性

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 确保已有 screenplay.json（使用 locations 格式）
4. 运行脚本: python .claude/scripts/manga_generate_phases.py
"""

import argparse
from pathlib import Path
from collections import defaultdict

from manga_common import (
    IMAGE_MODEL,
    setup_client,
    load_screenplay,
    save_screenplay,
    get_output_dir_from_screenplay,
    get_character_phase_path,
    get_turnaround_path,
    get_style_keywords,
    print_header,
    is_location_format,
    load_image_as_pil,
)

# 导入三视图生成模块的函数
from manga_generate_turnaround import (
    get_character_base_description,
    build_turnaround_prompt,
    generate_turnaround,
)


def ensure_turnaround_exists(client, screenplay: dict, output_dir: Path, style_keywords: str) -> str:
    """确保基础三视图存在，不存在则自动生成

    Args:
        client: Gemini API 客户端
        screenplay: 剧本数据
        output_dir: 输出目录
        style_keywords: 风格关键词

    Returns:
        三视图文件路径，失败返回 None
    """
    turnaround_path = get_turnaround_path(output_dir)

    if turnaround_path.exists():
        print(f"\n发现基础三视图: {turnaround_path}")
        return str(turnaround_path)

    print("\n未找到基础三视图，正在自动生成...")

    # 获取角色描述
    character_name, character_description = get_character_base_description(screenplay, output_dir)

    if not character_description:
        print("错误: 无法获取角色描述用于生成基础三视图")
        print("请确保 story_outline.json 中包含 characters[0].appearance")
        return None

    print(f"角色: {character_name}")
    print(f"角色描述: {character_description}")

    # 构建提示词并生成
    prompt = build_turnaround_prompt(character_description)
    path = generate_turnaround(client, prompt, output_dir)

    if path:
        # 更新剧本中的三视图路径
        screenplay["turnaround_path"] = path
        save_screenplay(screenplay)
        print(f"基础三视图已生成: {path}")

    return path


def get_previous_phase_reference(character_name: str, phase_id: int,
                                   character_phases: list, output_dir: Path):
    """获取同一角色的前一阶段参考图

    Args:
        character_name: 角色名称
        phase_id: 当前阶段 ID
        character_phases: 同一角色的所有阶段列表（已按 phase_id 排序）
        output_dir: 输出目录

    Returns:
        PIL Image 对象，未找到返回 None
    """
    # 找到 phase_id 小于当前且最接近的阶段
    previous_phase = None
    for phase in character_phases:
        pid = phase.get("phase_id", 0)
        if pid < phase_id:
            previous_phase = phase
        else:
            break  # 因为已排序，后面的都大于等于当前

    if previous_phase is None:
        return None

    # 检查前一阶段的参考图是否存在
    prev_ref_path = previous_phase.get("reference_image")
    if prev_ref_path and Path(prev_ref_path).exists():
        print(f"  发现前一阶段参考图: {prev_ref_path}")
        return load_image_as_pil(prev_ref_path)

    return None


def build_phase_turnaround_prompt(character_name: str, appearance_prompt: str, phase_name: str, style_keywords: str, has_base_reference: bool = False, has_previous_phase: bool = False, anchor_prompt: str = None) -> str:
    """构建角色阶段三视图生成提示词

    支持双重参考：
    - 基础三视图：保持核心面部特征和身体结构
    - 前一阶段图：保持演变连续性
    - 锚定特征：文字描述角色核心特征

    Args:
        character_name: 角色名称
        appearance_prompt: 外观描述
        phase_name: 阶段名称
        style_keywords: 风格关键词
        has_base_reference: 是否有基础三视图作为参考
        has_previous_phase: 是否有前一阶段图作为参考
        anchor_prompt: 角色锚定特征（可选）

    Returns:
        生成提示词
    """
    reference_instruction = ""

    if has_base_reference and has_previous_phase:
        # 双重参考：基础 + 前一阶段
        reference_instruction = """
CRITICAL REFERENCE IMAGES:
- FIRST IMAGE: BASE DESIGN - 角色的核心三视图设计
- SECOND IMAGE: PREVIOUS PHASE - 前一阶段的角色外观

你必须保持：
1. 来自 BASE DESIGN 的核心特征（脸型、五官、身体比例、基本发型结构）
2. 来自 PREVIOUS PHASE 的演变连续性（服装风化程度、伤痕累积等渐进变化）

仅根据本阶段描述修改指定元素，确保变化是渐进的，不是突变。
"""
    elif has_base_reference:
        # 仅基础三视图参考（第一阶段）
        reference_instruction = """
CRITICAL: The attached image shows the character's BASE DESIGN (turnaround reference sheet).
You MUST maintain the character's core features from this reference:
- Same face shape, facial features, and proportions
- Same body type and build
- Same basic hair style structure (can be modified per phase description)
Only change the elements specified in the phase description (clothing condition, skin tone, hair state, etc.).
"""

    # 构建锚定特征描述
    anchor_section = ""
    if anchor_prompt:
        anchor_section = f"""
CRITICAL ANCHOR FEATURES (must be preserved in all views):
{anchor_prompt}
"""

    return f"""Character turnaround sheet with three views arranged horizontally in a single image:

LEFT SECTION: Front view (character facing directly toward viewer)
CENTER SECTION: Side view (character in profile, facing right)
RIGHT SECTION: Back view (character facing away from viewer)
{reference_instruction}{anchor_section}
Character: {character_name}
Phase: {phase_name}

Appearance Details for this phase:
{appearance_prompt}

Technical Requirements:
- Layout: Three full body shots side by side in one horizontal image
- Style: {style_keywords}
- Quality: High quality, detailed, consistent proportions across all views
- Background: Plain white or light gray background
- Pose: Neutral standing pose, arms slightly away from body for visibility
- Composition: Full body visible in each view, equal spacing between views
- Consistency: Same character design across all three views, matching the phase description

Important: Generate all three views in a single image, arranged horizontally from left to right (front, side, back).
The character's appearance MUST match the phase description while maintaining core identity from the reference."""


def generate_phase_reference(client, prompt: str, output_path: Path,
                              base_reference_image=None,
                              previous_phase_image=None) -> str:
    """生成角色阶段参考图

    支持多图参考：Gemini API 支持在 contents 中传入多个图片

    Args:
        client: Gemini API 客户端
        prompt: 生成提示词
        output_path: 输出路径
        base_reference_image: PIL Image 对象，基础三视图参考
        previous_phase_image: PIL Image 对象，前一阶段参考图

    Returns:
        生成图片的路径，失败返回 None
    """
    ref_desc = []
    if base_reference_image:
        ref_desc.append("基础三视图")
    if previous_phase_image:
        ref_desc.append("前一阶段")

    if ref_desc:
        print(f"  正在生成参考图（使用参考: {' + '.join(ref_desc)}）...")
    else:
        print(f"  正在生成参考图...")

    try:
        # 构建内容：按顺序放入参考图，最后放提示词
        # Gemini 支持多图输入
        contents = []
        if base_reference_image:
            contents.append(base_reference_image)
        if previous_phase_image:
            contents.append(previous_phase_image)
        contents.append(prompt)

        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=contents,
            config={"response_modalities": ["IMAGE"]}
        )

        # 保存图片
        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(str(output_path))
                print(f"  参考图已保存: {output_path}")
                return str(output_path)

        print("  未能生成参考图")
        return None

    except Exception as e:
        print(f"  参考图生成失败: {e}")
        return None


def main():
    """主函数

    生成流程：
    1. 检查/自动生成基础三视图（强制依赖）
    2. 按角色分组，按 phase_id 排序
    3. 顺序生成，传递链式参考（base + previous phase）
    """
    parser = argparse.ArgumentParser(description="AI 漫剧 - 角色阶段参考图生成（支持链式参考）")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新生成所有参考图"
    )
    parser.add_argument(
        "--phase",
        type=int,
        default=None,
        help="只生成指定阶段的参考图"
    )
    parser.add_argument(
        "--no-auto-turnaround",
        action="store_true",
        help="不自动生成基础三视图（如果缺失则报错退出）"
    )
    args = parser.parse_args()

    print_header("AI 漫剧 - 角色阶段参考图生成")
    print("链式参考机制: Phase N 参考 Phase N-1，保持角色演变连续性")

    # 初始化
    client = setup_client()
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)

    title = screenplay.get("title", "未命名")
    style_keywords = get_style_keywords(screenplay)

    print(f"\n剧本: {title}")
    print(f"风格关键词: {style_keywords}")
    print(f"输出目录: {output_dir.absolute()}")

    # 检查是否使用新格式
    if not is_location_format(screenplay):
        print("\n检测到旧格式剧本，请使用 manga_generate_turnaround.py 生成角色三视图")
        return

    # 获取角色阶段列表
    character_phases = screenplay.get("character_phases", [])
    if not character_phases:
        print("\n错误: 剧本中没有角色阶段定义")
        print("请确保 screenplay.json 包含 character_phases 数组")
        return

    print(f"\n角色阶段数量: {len(character_phases)}")

    # ============================================================
    # 步骤 1: 确保基础三视图存在（强制依赖）
    # ============================================================
    base_turnaround_image = None
    turnaround_path = get_turnaround_path(output_dir)

    if args.no_auto_turnaround:
        # 不自动生成，检查是否存在
        if turnaround_path.exists():
            print(f"\n发现基础三视图: {turnaround_path}")
            base_turnaround_image = load_image_as_pil(str(turnaround_path))
            if not base_turnaround_image:
                print("错误: 无法加载基础三视图")
                return
        else:
            print(f"\n错误: 未找到基础三视图 ({turnaround_path})")
            print("请先运行以下命令生成基础三视图:")
            print("  python .claude/scripts/manga_generate_turnaround.py")
            print("\n或移除 --no-auto-turnaround 参数以自动生成")
            return
    else:
        # 自动确保基础三视图存在
        path = ensure_turnaround_exists(client, screenplay, output_dir, style_keywords)
        if path:
            base_turnaround_image = load_image_as_pil(path)
            if not base_turnaround_image:
                print("错误: 无法加载基础三视图，无法继续")
                return
        else:
            print("\n错误: 无法生成或加载基础三视图")
            print("链式参考机制需要基础三视图作为起点")
            return

    print("  将使用基础三视图作为角色外观参考，确保一致性")

    # ============================================================
    # 步骤 2: 按角色分组，按 phase_id 排序
    # ============================================================
    characters_phases_map = defaultdict(list)
    for phase in character_phases:
        char_name = phase.get("character", "未知角色")
        characters_phases_map[char_name].append(phase)

    # 对每个角色的阶段按 phase_id 排序
    for char_name in characters_phases_map:
        characters_phases_map[char_name].sort(key=lambda p: p.get("phase_id", 0))

    print(f"\n角色数量: {len(characters_phases_map)}")
    for char_name, phases in characters_phases_map.items():
        phase_ids = [p.get("phase_id", 0) for p in phases]
        print(f"  {char_name}: 阶段 {phase_ids}")

    # ============================================================
    # 步骤 3: 顺序生成，传递链式参考
    # ============================================================
    generated_count = 0
    skipped_count = 0

    for char_name, phases in characters_phases_map.items():
        print(f"\n{'='*60}")
        print(f"角色: {char_name} (共 {len(phases)} 个阶段)")
        print("=" * 60)

        # 链式参考：前一阶段的图片
        previous_phase_image = None

        for phase in phases:
            phase_id = phase.get("phase_id", 0)
            phase_name = phase.get("name", f"阶段 {phase_id}")
            appearance_prompt = phase.get("appearance_prompt", "")
            anchor_prompt = phase.get("anchor_prompt", "")

            # 如果指定了只生成某个阶段
            if args.phase is not None and phase_id != args.phase:
                # 但仍然需要加载前一阶段的参考图以保持链式
                existing_path = phase.get("reference_image")
                if existing_path and Path(existing_path).exists():
                    previous_phase_image = load_image_as_pil(existing_path)
                continue

            print(f"\n--- 阶段 {phase_id}: {phase_name} ---")
            print(f"外观: {appearance_prompt[:80]}..." if len(appearance_prompt) > 80 else f"外观: {appearance_prompt}")
            if anchor_prompt:
                print(f"锚定特征: {anchor_prompt[:60]}..." if len(anchor_prompt) > 60 else f"锚定特征: {anchor_prompt}")

            # 检查是否已存在
            existing_path = phase.get("reference_image")
            if existing_path and Path(existing_path).exists() and not args.force:
                print(f"  参考图已存在，跳过: {existing_path}")
                # 加载已存在的图片作为下一阶段的参考
                previous_phase_image = load_image_as_pil(existing_path)
                skipped_count += 1
                continue

            if not appearance_prompt:
                print("  没有外观描述，跳过")
                continue

            # 显示参考信息
            ref_info = ["基础三视图"]
            if previous_phase_image:
                ref_info.append(f"前一阶段(阶段{phase_id - 1})")
            print(f"  参考: {' + '.join(ref_info)}")

            # 构建提示词（支持双重参考 + 锚定特征）
            has_previous = previous_phase_image is not None
            prompt = build_phase_turnaround_prompt(
                char_name,
                appearance_prompt,
                phase_name,
                style_keywords,
                has_base_reference=True,
                has_previous_phase=has_previous,
                anchor_prompt=anchor_prompt
            )

            # 生成参考图（传入多图参考）
            output_path = get_character_phase_path(char_name, phase_id, output_dir)
            image_path = generate_phase_reference(
                client, prompt, output_path,
                base_reference_image=base_turnaround_image,
                previous_phase_image=previous_phase_image
            )

            if image_path:
                # 更新剧本中的参考图路径
                for p in screenplay.get("character_phases", []):
                    if p.get("phase_id") == phase_id and p.get("character") == char_name:
                        p["reference_image"] = image_path
                        break

                # 每生成一张图片就保存
                save_screenplay(screenplay)
                generated_count += 1

                # 更新链式参考：本阶段生成的图片作为下一阶段的参考
                previous_phase_image = load_image_as_pil(image_path)
                print(f"  已更新链式参考 -> 下一阶段将使用此图")
            else:
                print("  生成失败，链式参考中断")
                # 失败时不更新 previous_phase_image，下一阶段将只有基础参考

    # ============================================================
    # 输出统计
    # ============================================================
    total = len(character_phases)
    print(f"\n{'='*60}")
    print(f"生成统计:")
    print(f"  新生成: {generated_count}")
    print(f"  已跳过: {skipped_count}")
    print(f"  总阶段: {total}")

    # 完成
    print_header("角色阶段参考图生成完成")

    if generated_count > 0:
        print("\n已生成的参考图:")
        for phase in screenplay.get("character_phases", []):
            ref_img = phase.get("reference_image")
            if ref_img:
                char = phase.get("character", "")
                pid = phase.get("phase_id", 0)
                print(f"  - {char} 阶段 {pid}: {ref_img}")

    print("\n请检查生成的参考图:")
    print(f"  open {output_dir}")
    print("\n验证链式一致性:")
    print("  - 检查同一角色的不同阶段是否保持面部特征一致")
    print("  - 检查变化是否渐进（服装、护额划痕等）")
    print("\n如果满意，可以继续生成场景背景:")
    print("  python .claude/scripts/manga_generate_backgrounds.py")


if __name__ == "__main__":
    main()
