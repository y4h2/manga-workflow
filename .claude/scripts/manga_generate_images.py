#!/usr/bin/env python3
"""
AI 漫剧生成 - 镜头图片生成脚本 (阶段 2)
为 screenplay.json 中的每个镜头生成图片

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 确保已运行阶段 1 和 1.5（生成角色阶段参考图和场景背景）
4. 运行脚本: python .claude/scripts/manga_generate_images.py

参考图使用策略:
- 默认启用链式参考：每个镜头参考上一个镜头的图片，保持视觉连贯性
- 场景切换时：使用场景背景图 + 角色阶段参考图
- 可通过 --no-chain 禁用链式参考
"""

import argparse
from pathlib import Path

from PIL import Image

from manga_common import (
    IMAGE_MODEL,
    setup_client,
    load_screenplay,
    save_screenplay,
    get_output_dir_from_screenplay,
    get_location_shot_path,
    print_header,
    get_style_keywords,
    get_aspect_ratio,
    build_enhanced_prompt,
)


def build_location_shot_prompt(
    original_prompt: str,
    location_name: str,
    character_visible: bool,
    character_appearance: str = "",
    action: str = ""
) -> str:
    """构建场景镜头提示词

    Args:
        original_prompt: 原始 image_prompt
        location_name: 场景名称
        character_visible: 是否包含角色
        character_appearance: 角色外观描述（当 character_visible=True 时）
        action: 角色动作描述

    Returns:
        增强后的提示词
    """
    prompt_parts = [original_prompt]

    prompt_parts.append(f"\nScene Location: {location_name}")

    if character_visible and character_appearance:
        prompt_parts.append(f"""
IMPORTANT - Character Reference:
The first attached image shows the scene background.
The second attached image shows the character reference (turnaround sheet).

You MUST:
1. Use the background image as the scene environment
2. Match the character's appearance exactly as shown in the reference:
   - Same face, hairstyle, and hair color
   - Same clothing design and colors
   - Same body proportions and style

Character details: {character_appearance}
Action: {action}""")
    elif character_visible:
        prompt_parts.append(f"\nAction: {action}")
    else:
        prompt_parts.append("""
IMPORTANT: This shot contains NO characters.
Use the attached background image as reference for the scene environment.""")

    return "\n".join(prompt_parts)


def load_reference_images(screenplay: dict, location: dict, output_dir: Path) -> tuple:
    """加载场景的参考图片

    Args:
        screenplay: 剧本数据
        location: 场景数据
        output_dir: 输出目录

    Returns:
        (background_image, character_phase_image) 元组
    """
    background_image = None
    character_phase_image = None

    # 加载背景图
    bg_path = location.get("background_image")
    if bg_path and Path(bg_path).exists():
        try:
            background_image = Image.open(bg_path)
            print(f"  已加载背景图: {bg_path}")
        except Exception as e:
            print(f"  警告: 无法加载背景图: {e}")

    # 加载角色阶段参考图
    char_phase_id = location.get("character_phase", 1)
    for phase in screenplay.get("character_phases", []):
        if phase.get("phase_id") == char_phase_id:
            ref_path = phase.get("reference_image")
            if ref_path and Path(ref_path).exists():
                try:
                    character_phase_image = Image.open(ref_path)
                    print(f"  已加载角色阶段参考图: {ref_path}")
                except Exception as e:
                    print(f"  警告: 无法加载角色阶段参考图: {e}")
            break

    return background_image, character_phase_image


def get_character_phase_appearance(screenplay: dict, phase_id: int) -> str:
    """获取角色阶段的外观描述

    Args:
        screenplay: 剧本数据
        phase_id: 阶段 ID

    Returns:
        外观描述字符串
    """
    for phase in screenplay.get("character_phases", []):
        if phase.get("phase_id") == phase_id:
            return phase.get("appearance_prompt", "")
    return ""


def generate_image_with_references(client, prompt: str, output_path: Path, reference_images: list = None):
    """调用 Gemini 图片生成 API（支持多个参考图片）

    Args:
        client: Gemini API 客户端
        prompt: 图片生成提示词
        output_path: 输出路径
        reference_images: 参考图片列表 (PIL Image 对象)

    Returns:
        生成图片的路径，失败返回 None
    """
    ref_count = len(reference_images) if reference_images else 0
    if ref_count > 0:
        print(f"  正在生成图片 (使用 {ref_count} 个参考图片)...")
    else:
        print(f"  正在生成图片...")

    try:
        # 构建 contents
        contents = []
        if reference_images:
            contents.extend(reference_images)
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
                print(f"  图片已保存: {output_path}")
                return str(output_path)

        print("  未能生成图片")
        return None

    except Exception as e:
        print(f"  图片生成失败: {e}")
        return None


def process_location_shots(client, screenplay, style_keywords, output_dir, use_chain_reference=True):
    """处理 locations 格式的镜头生成

    Args:
        client: Gemini API 客户端
        screenplay: 剧本数据
        style_keywords: 风格关键词
        output_dir: 输出目录
        use_chain_reference: 是否使用链式参考 (上一帧作为参考)
    """
    locations = screenplay.get("locations", [])
    total_shots = sum(len(loc.get("shots", [])) for loc in locations)

    # 统计需要生成的镜头
    shots_to_generate = []
    for location in locations:
        loc_id = location.get("location_id", 0)
        for i, shot in enumerate(location.get("shots", [])):
            shot_id = shot.get("shot_id", f"{loc_id}-{i + 1}")
            image_path = shot.get("image_path")
            if not image_path or not Path(image_path).exists():
                shots_to_generate.append({
                    "location": location,
                    "shot": shot,
                    "loc_id": loc_id,
                    "shot_index": i
                })
            else:
                print(f"  镜头 {shot_id} 图片已存在，跳过")

    if not shots_to_generate:
        print("\n所有镜头图片已存在，无需生成")
        return

    print(f"\n需要生成 {len(shots_to_generate)} 个镜头的图片")
    if use_chain_reference:
        print("启用链式参考：每个镜头将参考前一个镜头的图片")

    # 按场景分组处理，以便利用场景背景和角色阶段参考图
    current_loc_id = None
    background_image = None
    character_phase_image = None
    prev_generated_image = None

    for item in shots_to_generate:
        location = item["location"]
        shot = item["shot"]
        loc_id = item["loc_id"]
        shot_index = item["shot_index"]

        shot_id = shot.get("shot_id", f"{loc_id}-{shot_index + 1}")
        loc_name = location.get("name", "")
        narration = shot.get("narration", "")
        image_prompt = shot.get("image_prompt", "")
        action = shot.get("action", "")
        character_visible = shot.get("character_visible", True)

        print(f"\n{'='*50}")
        print(f"镜头 {shot_id} [场景: {loc_name}]")
        if narration:
            print(f"旁白: {narration[:50]}...")
        print("=" * 50)

        if not image_prompt:
            print("  没有图片提示词，跳过")
            continue

        # 如果切换到新场景，重新加载参考图片
        if loc_id != current_loc_id:
            current_loc_id = loc_id
            background_image, character_phase_image = load_reference_images(
                screenplay, location, output_dir
            )
            # 切换场景时重置链式参考
            prev_generated_image = None

        # 获取角色阶段外观描述
        char_phase_id = location.get("character_phase", 1)
        character_appearance = get_character_phase_appearance(screenplay, char_phase_id)

        # 自动附加风格关键词
        enhanced_prompt = build_enhanced_prompt(image_prompt, style_keywords)

        # 构建最终提示词
        final_prompt = build_location_shot_prompt(
            enhanced_prompt,
            loc_name,
            character_visible,
            character_appearance if character_visible else "",
            action
        )

        # 确定参考图片
        # 策略：始终包含背景图以保持场景一致性，加上角色参考或上一帧
        reference_images = []

        # 始终添加背景图作为场景参考（如果有）
        if background_image:
            reference_images.append(background_image)
            print(f"  使用场景背景图作为参考")

        # 添加角色阶段参考图（如果角色可见且有参考图）
        if character_visible and character_phase_image:
            reference_images.append(character_phase_image)
            print(f"  使用角色阶段参考图")

        # 链式参考：额外添加上一帧（保持动作连贯性）
        if use_chain_reference and prev_generated_image:
            reference_images.append(prev_generated_image)
            print(f"  使用上一镜头作为链式参考")

        print(f"  提示词: {final_prompt[:100]}...")

        # 生成图片
        shot_image_path = get_location_shot_path(loc_id, shot_index + 1, output_dir)
        image_path = generate_image_with_references(
            client,
            final_prompt,
            shot_image_path,
            reference_images=reference_images if reference_images else None
        )

        if image_path:
            # 更新镜头数据
            shot["image_path"] = image_path

            # 加载生成的图片作为下一个镜头的参考
            try:
                prev_generated_image = Image.open(image_path)
            except Exception as e:
                print(f"  警告: 无法加载生成的图片用于链式参考: {e}")
                prev_generated_image = None

            # 更新 screenplay 中的数据
            for loc in screenplay.get("locations", []):
                if loc.get("location_id") == loc_id:
                    for s in loc.get("shots", []):
                        if s.get("shot_id") == shot_id:
                            s["image_path"] = image_path
                            break
                    break

            # 每生成一张图片就保存
            save_screenplay(screenplay)

    # 输出统计
    images_done = sum(
        1 for loc in screenplay.get("locations", [])
        for s in loc.get("shots", [])
        if s.get("image_path")
    )
    print(f"\n图片: {images_done}/{total_shots}")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="AI 漫剧 - 镜头图片生成")
    parser.add_argument(
        "--no-chain",
        action="store_true",
        help="禁用链式参考 (不使用上一帧作为参考)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新生成所有图片"
    )
    parser.add_argument(
        "--location",
        type=int,
        default=None,
        help="只生成指定场景的镜头图片"
    )
    parser.add_argument(
        "--aspect-ratio",
        default=None,
        help="覆盖画面比例 (如: 16:9, 9:16, 1:1)"
    )
    parser.add_argument(
        "--style",
        default=None,
        help="覆盖风格关键词"
    )
    args = parser.parse_args()

    print_header("AI 漫剧 - 镜头图片生成")

    # 初始化
    client = setup_client()
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)

    title = screenplay.get("title", "未命名")

    # 检查是否使用 locations 格式
    if "locations" not in screenplay or not screenplay.get("locations"):
        print("\n错误: 当前剧本不是 locations 格式")
        print("请确保 screenplay.json 包含 locations 数组")
        print("\n如果是旧格式剧本，请先使用 manga_create_shots.py 转换")
        return

    # 获取风格关键词（命令行参数优先）
    style_keywords = args.style if args.style else get_style_keywords(screenplay)
    aspect_ratio = args.aspect_ratio if args.aspect_ratio else get_aspect_ratio(screenplay)

    print(f"\n剧本: {title}")
    print(f"风格关键词: {style_keywords}")
    print(f"画面比例: {aspect_ratio}")
    print(f"输出目录: {output_dir.absolute()}")

    # 统计信息
    total_locations = screenplay.get("total_locations", len(screenplay.get("locations", [])))
    total_shots = screenplay.get("total_shots", sum(
        len(loc.get("shots", [])) for loc in screenplay.get("locations", [])
    ))

    print(f"总场景数: {total_locations}")
    print(f"总镜头数: {total_shots}")
    print(f"链式参考: {'禁用' if args.no_chain else '启用'}")

    # 检查是否有背景图和角色阶段参考图
    has_backgrounds = any(
        loc.get("background_image") and Path(loc["background_image"]).exists()
        for loc in screenplay.get("locations", [])
    )
    has_phase_refs = any(
        phase.get("reference_image") and Path(phase["reference_image"]).exists()
        for phase in screenplay.get("character_phases", [])
    )

    if not has_backgrounds:
        print("\n警告: 没有找到场景背景图")
        print("建议先运行: python .claude/scripts/manga_generate_backgrounds.py")

    if not has_phase_refs:
        print("\n警告: 没有找到角色阶段参考图")
        print("建议先运行: python .claude/scripts/manga_generate_phases.py")

    # 如果指定了 --force，清除所有已有的图片路径
    if args.force:
        print("\n强制模式: 将重新生成所有镜头图片")
        for loc in screenplay.get("locations", []):
            for shot in loc.get("shots", []):
                shot["image_path"] = None

    # 如果指定了场景，创建临时剧本副本只处理该场景
    # 注意：不要修改原始 screenplay，否则保存时会丢失其他场景
    working_screenplay = screenplay
    if args.location is not None:
        locations = [
            loc for loc in screenplay.get("locations", [])
            if loc.get("location_id") == args.location
        ]
        if not locations:
            print(f"\n错误: 未找到场景 {args.location}")
            return
        # 创建副本，只在处理时使用过滤后的场景
        import copy
        working_screenplay = copy.deepcopy(screenplay)
        working_screenplay["locations"] = locations
        print(f"\n只处理场景 {args.location}")

    # 处理镜头生成
    # 注意：始终传入原始 screenplay 以确保保存时不丢失数据
    # working_screenplay 仅用于过滤要处理的场景
    process_location_shots(
        client,
        screenplay,
        style_keywords,
        output_dir,
        use_chain_reference=not args.no_chain
    )

    # 完成
    print_header("镜头图片生成完成")

    print("\n已生成的镜头图片:")
    for loc in screenplay.get("locations", []):
        loc_id = loc.get("location_id")
        loc_name = loc.get("name", "")
        for shot in loc.get("shots", []):
            img_path = shot.get("image_path")
            if img_path:
                print(f"  - 镜头 {shot.get('shot_id')}: {img_path}")

    print("\n请检查生成的图片:")
    print(f"  open {output_dir}")
    print("\n如果满意，可以继续生成视频:")
    print("  python .claude/scripts/manga_generate_videos.py")


if __name__ == "__main__":
    main()
