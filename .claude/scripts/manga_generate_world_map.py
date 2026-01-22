#!/usr/bin/env python3
"""
AI 漫剧生成 - 世界地图生成脚本 (阶段 0.8)
生成鸟瞰俯视风格的世界地图，展示整体布局和区域分布

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 确保已有 story_outline.json（包含 world_map 定义）
4. 运行脚本: python .claude/scripts/manga_generate_world_map.py
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
    get_world_map,
    print_header,
    load_screenplay,
    migrate_flat_locations,
    has_layered_map_system,
)


def build_world_map_prompt(world_map: dict, regions: list) -> str:
    """构建世界地图生成提示词

    Args:
        world_map: 世界地图数据
        regions: 区域列表

    Returns:
        生成提示词
    """
    name = world_map.get("name", "World")
    description = world_map.get("description", "")
    style_base = world_map.get("style_base", {})
    geography_anchors = world_map.get("geography_anchors", [])

    # 获取风格信息
    art_style = style_base.get("art_style", "anime style")
    color_palette = style_base.get("color_palette", "muted colors")
    atmosphere = style_base.get("atmosphere", "cinematic")

    # 构建区域描述
    region_descriptions = []
    for region in regions:
        region_name = region.get("name", "Region")
        region_desc = region.get("description", "")
        geography = region.get("geography", {})
        terrain = geography.get("terrain_type", "")
        if terrain:
            region_descriptions.append(f"- {region_name}: {terrain}")
        elif region_desc:
            region_descriptions.append(f"- {region_name}: {region_desc[:50]}")

    regions_text = "\n".join(region_descriptions) if region_descriptions else "- Main region"

    # 构建地理锚点描述
    geo_anchors_text = ", ".join(geography_anchors) if geography_anchors else "varied terrain"

    prompt = f"""{art_style}, bird's eye view world map, top-down perspective, cartographic style:

World: {name}
Description: {description}

Geographic Features:
{geo_anchors_text}

Regions to show:
{regions_text}

Visual Style Requirements:
- Bird's eye view / aerial perspective / top-down map view
- {color_palette}
- {atmosphere}
- Show terrain features: mountains, forests, water bodies, plains
- Clear visual distinction between different regions
- Soft, illustrative map style (not photorealistic)
- Include subtle compass rose or scale indicator
- No text labels or annotations
- No characters or people
- Artistic map illustration style, like a fantasy world map

Important: This is a TOP-DOWN AERIAL VIEW map showing the entire world from above, similar to a fantasy map illustration. Do NOT include any ground-level perspective or characters."""

    return prompt


def generate_world_map(client, prompt: str, output_path: Path) -> str:
    """生成世界地图图片

    Args:
        client: Gemini API 客户端
        prompt: 生成提示词
        output_path: 输出路径

    Returns:
        生成图片的路径，失败返回 None
    """
    print(f"  正在生成世界地图...")
    print(f"  提示词: {prompt[:150]}...")

    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[prompt],
            config={"response_modalities": ["IMAGE"]}
        )

        # 保存图片
        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(str(output_path))
                print(f"  世界地图已保存: {output_path}")
                return str(output_path)

        print("  未能生成世界地图")
        return None

    except Exception as e:
        print(f"  世界地图生成失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI 漫剧 - 世界地图生成")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新生成世界地图"
    )
    args = parser.parse_args()

    print_header("AI 漫剧 - 世界地图生成 (阶段 0.8)")

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

    # 检查是否有世界地图定义
    world_map = get_world_map(story)
    if not world_map:
        print("\n警告: 故事大纲中没有 world_map 定义")
        print("正在创建默认世界地图结构...")

        # 使用迁移函数创建默认结构
        story = migrate_flat_locations(story)
        world_map = get_world_map(story)

        # 保存更新后的故事大纲
        save_story_outline(story, output_dir)
        print("已添加默认 world_map 和 regions 结构")

    # 检查是否已有世界地图图片
    world_map_path = get_world_map_path(output_dir)
    existing_image = world_map.get("world_map_image")

    if existing_image and Path(existing_image).exists() and not args.force:
        print(f"\n世界地图已存在: {existing_image}")
        print("如需重新生成，请使用 --force 参数")
        return

    # 获取区域列表
    regions = story.get("regions", [])
    print(f"\n区域数量: {len(regions)}")
    for region in regions:
        print(f"  - 区域 {region.get('region_id')}: {region.get('name')}")

    # 构建提示词
    prompt = build_world_map_prompt(world_map, regions)

    print(f"\n{'='*50}")
    print(f"世界: {world_map.get('name', '未命名')}")
    print("=" * 50)

    # 生成世界地图
    image_path = generate_world_map(client, prompt, world_map_path)

    if image_path:
        # 更新故事大纲中的世界地图路径
        story["world_map"]["world_map_image"] = image_path
        save_story_outline(story, output_dir)

        print_header("世界地图生成完成")
        print(f"\n已生成:")
        print(f"  - 世界地图: {image_path}")

        print("\n请检查生成的世界地图:")
        print(f"  open {output_dir}")

        if has_layered_map_system(story):
            print("\n如果满意，可以继续生成区域地图:")
            print("  python .claude/scripts/manga_generate_region_maps.py")
        else:
            print("\n如果满意，可以继续生成角色阶段参考图:")
            print("  python .claude/scripts/manga_generate_phases.py")
    else:
        print("\n世界地图生成失败，请检查错误信息后重试")


if __name__ == "__main__":
    main()
