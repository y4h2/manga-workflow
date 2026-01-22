#!/usr/bin/env python3
"""
AI 漫剧生成 - 区域地图生成脚本 (阶段 0.9)
生成艺术概念风格的区域地图，作为该区域所有场景的视觉风格参考

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 确保已有 story_outline.json（包含 regions 定义）
4. 运行脚本: python .claude/scripts/manga_generate_region_maps.py
"""

import argparse
from pathlib import Path

from manga_common import (
    IMAGE_MODEL,
    setup_client,
    load_story_outline,
    save_story_outline,
    get_output_dir_from_screenplay,
    get_world_map_path,
    get_region_map_path,
    get_world_map,
    get_region_by_id,
    get_locations_in_region,
    print_header,
    load_screenplay,
    migrate_flat_locations,
    load_image_as_pil,
    build_inherited_style,
    build_style_prompt_from_inherited,
)


def build_region_map_prompt(region: dict, world_map: dict, locations: list) -> str:
    """构建区域地图生成提示词

    Args:
        region: 区域数据
        world_map: 世界地图数据
        locations: 该区域包含的场景列表

    Returns:
        生成提示词
    """
    region_name = region.get("name", "Region")
    region_desc = region.get("description", "")
    style_modifiers = region.get("style_modifiers", {})
    geography = region.get("geography", {})

    # 获取世界风格作为基础
    style_base = world_map.get("style_base", {})
    art_style = style_base.get("art_style", "anime style")
    color_palette = style_base.get("color_palette", "muted colors")
    atmosphere = style_base.get("atmosphere", "cinematic")

    # 添加区域特有的风格修饰
    color_accent = style_modifiers.get("color_accent", "")
    unique_features = style_modifiers.get("unique_features", "")

    # 获取地理信息
    terrain_type = geography.get("terrain_type", "")
    vegetation = geography.get("vegetation", "")
    water_features = geography.get("water_features", "")

    # 构建场景描述
    location_descriptions = []
    for loc in locations:
        loc_name = loc.get("name", "Location")
        loc_time = loc.get("time_of_day", "day")
        local_features = loc.get("local_features", {})
        if local_features:
            features_text = ", ".join(f"{k}: {v}" for k, v in local_features.items())
            location_descriptions.append(f"- {loc_name} ({loc_time}): {features_text}")
        else:
            location_descriptions.append(f"- {loc_name} ({loc_time})")

    locations_text = "\n".join(location_descriptions) if location_descriptions else "- Main location"

    # 构建地理特征描述
    geo_features = []
    if terrain_type:
        geo_features.append(f"Terrain: {terrain_type}")
    if vegetation:
        geo_features.append(f"Vegetation: {vegetation}")
    if water_features:
        geo_features.append(f"Water: {water_features}")
    geo_text = "\n".join(geo_features) if geo_features else "Natural environment"

    # 构建完整提示词
    prompt = f"""{art_style}, artistic concept art of a region, establishing shot, environmental art:

Region: {region_name}
Description: {region_desc}

Geographic Features:
{geo_text}

Key Locations in this region:
{locations_text}

Visual Style Requirements:
- Artistic concept illustration style (NOT a map, but environmental concept art)
- {color_palette}
- {atmosphere}
- Wide establishing shot showing the region's atmosphere and feel
- Showcase the region's unique visual identity
- Environmental storytelling through composition
- Cinematic framing with depth"""

    # 添加区域特有的风格修饰
    if color_accent:
        prompt += f"\n- Color accent: {color_accent}"
    if unique_features:
        prompt += f"\n- Unique features: {unique_features}"

    prompt += """

Important: This is an ARTISTIC CONCEPT illustration of the region's atmosphere and visual identity.
It should capture the mood, color palette, and feeling of this area.
Do NOT include any characters or people.
This will be used as a STYLE REFERENCE for generating scenes in this region."""

    return prompt


def generate_region_map(client, prompt: str, output_path: Path, reference_image=None) -> str:
    """生成区域地图图片

    Args:
        client: Gemini API 客户端
        prompt: 生成提示词
        output_path: 输出路径
        reference_image: 参考图片（世界地图）用于风格一致性

    Returns:
        生成图片的路径，失败返回 None
    """
    print(f"  正在生成区域地图...")

    try:
        # 构建内容列表
        contents = [prompt]

        # 如果有参考图片，添加到内容中
        if reference_image is not None:
            contents = [
                "Use this world map as a style reference for color palette and atmosphere:\n",
                reference_image,
                "\n\nNow generate the region concept art with the following specifications:\n",
                prompt
            ]

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
                print(f"  区域地图已保存: {output_path}")
                return str(output_path)

        print("  未能生成区域地图")
        return None

    except Exception as e:
        print(f"  区域地图生成失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI 漫剧 - 区域地图生成")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新生成所有区域地图"
    )
    parser.add_argument(
        "--region",
        type=int,
        default=None,
        help="只生成指定区域的地图"
    )
    args = parser.parse_args()

    print_header("AI 漫剧 - 区域地图生成 (阶段 0.9)")

    # 初始化
    client = setup_client()

    # 加载剧本以获取输出目录
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)

    # 加载故事大纲
    story = load_story_outline(output_dir)

    title = story.get("title", "未命名")
    print(f"\n剧本: {title}")
    print(f"输出目录: {output_dir.absolute()}")

    # 检查是否有区域定义
    regions = story.get("regions", [])
    if not regions:
        print("\n警告: 故事大纲中没有 regions 定义")
        print("正在创建默认区域结构...")

        # 使用迁移函数创建默认结构
        story = migrate_flat_locations(story)
        regions = story.get("regions", [])

        # 保存更新后的故事大纲
        save_story_outline(story, output_dir)
        print("已添加默认 regions 结构")

    # 获取世界地图信息和参考图片
    world_map = get_world_map(story)
    world_map_image = None
    world_map_image_path = world_map.get("world_map_image") if world_map else None

    if world_map_image_path and Path(world_map_image_path).exists():
        print(f"\n使用世界地图作为风格参考: {world_map_image_path}")
        world_map_image = load_image_as_pil(world_map_image_path)
    else:
        print("\n注意: 未找到世界地图参考图，将独立生成区域地图")
        print("建议先运行阶段 0.8 生成世界地图以确保风格一致性")

    print(f"\n区域数量: {len(regions)}")

    # 统计需要生成的区域
    regions_to_generate = []
    for region in regions:
        region_id = region.get("region_id", 0)

        # 如果指定了只生成某个区域
        if args.region is not None and region_id != args.region:
            continue

        existing_path = region.get("region_map_image")

        if existing_path and Path(existing_path).exists() and not args.force:
            print(f"  区域 {region_id} 地图已存在，跳过")
        else:
            regions_to_generate.append(region)

    if not regions_to_generate:
        print("\n所有区域地图已存在，无需生成")
        print("如需重新生成，请使用 --force 参数")
        return

    print(f"\n需要生成 {len(regions_to_generate)} 个区域的地图")

    # 生成区域地图
    generated_count = 0
    for region in regions_to_generate:
        region_id = region.get("region_id", 0)
        region_name = region.get("name", "未知区域")

        print(f"\n{'='*50}")
        print(f"区域 {region_id}: {region_name}")
        print("=" * 50)

        # 获取该区域的场景列表
        locations = get_locations_in_region(story, region_id)
        print(f"  包含场景: {len(locations)} 个")
        for loc in locations:
            print(f"    - {loc.get('name', '?')}")

        # 构建提示词
        prompt = build_region_map_prompt(region, world_map, locations)
        print(f"  提示词: {prompt[:100]}...")

        # 生成区域地图
        output_path = get_region_map_path(region_id, output_dir)
        image_path = generate_region_map(client, prompt, output_path, world_map_image)

        if image_path:
            # 更新故事大纲中的区域地图路径
            for r in story.get("regions", []):
                if r.get("region_id") == region_id:
                    r["region_map_image"] = image_path
                    break

            # 每生成一张图片就保存
            save_story_outline(story, output_dir)
            generated_count += 1

    # 输出统计
    total = len(regions)
    existing = total - len(regions_to_generate) + generated_count
    print(f"\n区域地图: {existing}/{total}")

    # 完成
    print_header("区域地图生成完成")

    if generated_count > 0:
        print("\n已生成的区域地图:")
        for region in story.get("regions", []):
            region_img = region.get("region_map_image")
            if region_img:
                print(f"  - 区域 {region.get('region_id')}: {region_img}")

    print("\n请检查生成的区域地图:")
    print(f"  open {output_dir}")
    print("\n如果满意，可以继续生成角色阶段参考图:")
    print("  python .claude/scripts/manga_generate_phases.py")


if __name__ == "__main__":
    main()
