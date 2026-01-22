#!/usr/bin/env python3
"""
AI 漫剧生成 - 方案 C1: 深度感知 Prompt 增强
通过增强 prompt 生成具有自然景深的单张背景图

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 确保已有 screenplay.json（使用 locations 格式）
4. 运行脚本: python solutions/layered_background_c1.py

参数:
  --force: 强制重新生成所有背景图
  --location N: 只生成指定场景的背景图
  --no-reference: 不使用区域地图作为参考

本方案是三种方案中最简单的，直接通过增强 prompt 来控制画面的景深层次。
无需额外依赖，无需后处理，生成的单张图片自然具有景深感。
"""

import argparse
import sys
from pathlib import Path

# 添加 .claude/scripts 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "scripts"))

from manga_common import (
    IMAGE_MODEL,
    setup_client,
    load_screenplay,
    save_screenplay,
    get_output_dir_from_screenplay,
    get_location_background_path,
    get_style_keywords,
    print_header,
    is_location_format,
    build_enhanced_prompt,
    load_story_outline,
    get_region_for_location,
    build_inherited_style,
    build_style_prompt_from_inherited,
    load_image_as_pil,
    has_layered_map_system,
    get_depth_guidance_prompt,
)


def build_depth_aware_background_prompt(location: dict, style_keywords: str, inherited_style: dict = None) -> str:
    """构建带景深层次的背景生成提示词

    Args:
        location: 场景数据
        style_keywords: 风格关键词
        inherited_style: 从区域/世界继承的风格信息

    Returns:
        生成提示词
    """
    name = location.get("name", "")
    time_of_day = location.get("time_of_day", "day")
    background_prompt = location.get("background_prompt", "")
    local_features = location.get("local_features", {})

    # 获取景深指导
    depth_guidance = get_depth_guidance_prompt()

    # 构建继承的风格提示词
    inherited_style_prompt = ""
    if inherited_style:
        inherited_style_prompt = build_style_prompt_from_inherited(inherited_style)

    # 时间光照映射
    time_lighting = {
        "dawn": "early dawn light, pink and orange sky, soft shadows",
        "morning": "morning sunlight, warm golden tones, fresh atmosphere",
        "noon": "midday sun, bright and clear, strong shadows",
        "afternoon": "afternoon light, warm tones, long shadows",
        "dusk": "sunset colors, golden hour, orange and purple sky",
        "evening": "twilight, blue hour, ambient glow",
        "night": "nighttime, moonlight, dark blue tones, stars",
        "midnight": "deep night, minimal lighting, dark atmosphere",
    }
    lighting = time_lighting.get(time_of_day.lower(), "natural lighting")

    # 如果有预定义的 background_prompt，增强它
    if background_prompt:
        # 确保以 anime style 开头
        if not background_prompt.lower().startswith("anime style"):
            background_prompt = f"anime style, {background_prompt}"

        enhanced = f"""{background_prompt}

{depth_guidance}

Lighting: {lighting}"""

        # 添加继承的风格
        if inherited_style_prompt:
            enhanced += f"""

Region Style to maintain:
{inherited_style_prompt}"""

        # 确保强调无人物
        enhanced += """

IMPORTANT: NO characters, NO people. Pure environment with natural depth layering."""

        return build_enhanced_prompt(enhanced, style_keywords)

    # 构建本地特征描述
    local_features_text = ""
    if local_features:
        features_parts = []
        if local_features.get("ground"):
            features_parts.append(f"Ground: {local_features['ground']}")
        if local_features.get("flora"):
            features_parts.append(f"Flora: {local_features['flora']}")
        if local_features.get("props"):
            features_parts.append(f"Props: {local_features['props']}")
        if features_parts:
            local_features_text = "\n".join(features_parts)

    # 构建默认提示词
    prompt = f"""anime style, cinematic background with distinct depth layers:

SCENE: {name}
TIME: {time_of_day}
LIGHTING: {lighting}

{depth_guidance}"""

    # 添加继承的风格
    if inherited_style_prompt:
        prompt += f"""

REGION STYLE TO MAINTAIN:
{inherited_style_prompt}"""

    # 添加本地特征
    if local_features_text:
        prompt += f"""

LOCAL FEATURES:
{local_features_text}"""

    prompt += f"""

TECHNICAL REQUIREMENTS:
- Strong sense of depth and three-dimensional space
- Atmospheric haze increasing with distance
- Color temperature shift: warm foreground → cool background
- Sharp midground with softer fore/background
- {style_keywords}
- NO characters, NO people, pure environment

This background should have natural visual depth that makes the scene feel immersive.
Maintain visual consistency with the region's established style and color palette."""

    return prompt


def generate_depth_aware_background(client, prompt: str, output_path: Path, reference_images: list = None) -> str:
    """生成具有景深的场景背景图

    Args:
        client: Gemini API 客户端
        prompt: 生成提示词
        output_path: 输出路径
        reference_images: 参考图片列表（区域地图、同区域前一场景等）

    Returns:
        生成图片的路径，失败返回 None
    """
    print(f"  正在生成深度感知背景图...")

    try:
        # 构建内容列表
        contents = [prompt]

        # 如果有参考图片，添加到内容中
        if reference_images and any(img is not None for img in reference_images):
            valid_refs = [img for img in reference_images if img is not None]
            if valid_refs:
                contents = [
                    "Use these images as style references for color palette, atmosphere, and visual consistency:\n"
                ]
                for i, ref_img in enumerate(valid_refs):
                    contents.append(f"\nReference {i + 1}:\n")
                    contents.append(ref_img)
                contents.append("\n\nNow generate the background scene with the following specifications:\n")
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
                print(f"  深度感知背景图已保存: {output_path}")
                return str(output_path)

        print("  未能生成背景图")
        return None

    except Exception as e:
        print(f"  背景图生成失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI 漫剧 - 深度感知背景生成 (方案 C1)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新生成所有背景图"
    )
    parser.add_argument(
        "--location",
        type=int,
        default=None,
        help="只生成指定场景的背景图"
    )
    parser.add_argument(
        "--no-reference",
        action="store_true",
        help="不使用区域地图作为参考"
    )
    args = parser.parse_args()

    print_header("AI 漫剧 - 深度感知背景生成 (方案 C1)")

    # 初始化
    client = setup_client()
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)

    title = screenplay.get("title", "未命名")
    style_keywords = get_style_keywords(screenplay)

    print(f"\n剧本: {title}")
    print(f"风格关键词: {style_keywords}")
    print(f"输出目录: {output_dir.absolute()}")
    print("\n方案 C1: 通过增强 prompt 生成具有自然景深的背景图")

    # 检查是否使用新格式
    if not is_location_format(screenplay):
        print("\n错误: 当前剧本使用旧格式，不支持场景背景生成")
        return

    # 尝试加载故事大纲以获取分层地图信息
    story = None
    use_layered_map = False
    region_map_cache = {}

    try:
        story = load_story_outline(output_dir)
        use_layered_map = has_layered_map_system(story) and not args.no_reference
        if use_layered_map:
            print("\n检测到分层地图系统，将使用区域地图作为风格参考")
    except SystemExit:
        print("\n注意: 未找到 story_outline.json，将独立生成背景")

    # 获取场景列表
    locations = screenplay.get("locations", [])
    if not locations:
        print("\n错误: 剧本中没有场景定义")
        return

    print(f"\n场景数量: {len(locations)}")

    # 统计需要生成的场景
    locations_to_generate = []
    for location in locations:
        loc_id = location.get("location_id", 0)

        if args.location is not None and loc_id != args.location:
            continue

        existing_path = location.get("background_image")

        if existing_path and Path(existing_path).exists() and not args.force:
            print(f"  场景 {loc_id} 背景图已存在，跳过")
        else:
            locations_to_generate.append(location)

    if not locations_to_generate:
        print("\n所有场景背景图已存在，无需生成")
        print("如需重新生成，请使用 --force 参数")
        return

    print(f"\n需要生成 {len(locations_to_generate)} 个场景的深度感知背景图")

    # 跟踪同区域已生成的场景背景
    region_prev_backgrounds = {}

    # 生成背景图
    generated_count = 0
    for location in locations_to_generate:
        loc_id = location.get("location_id", 0)
        loc_name = location.get("name", "未知场景")
        time_of_day = location.get("time_of_day", "day")
        region_id = location.get("region_id")

        print(f"\n{'='*50}")
        print(f"场景 {loc_id}: {loc_name}")
        print(f"时间: {time_of_day}")
        if region_id:
            print(f"区域: {region_id}")
        print("=" * 50)

        # 获取继承的风格信息
        inherited_style = None
        if story and use_layered_map:
            inherited_style = build_inherited_style(story, location_id=loc_id)
            if inherited_style:
                print(f"  继承风格: {build_style_prompt_from_inherited(inherited_style)[:80]}...")

        # 构建深度感知提示词
        prompt = build_depth_aware_background_prompt(location, style_keywords, inherited_style)
        print(f"  提示词: {prompt[:100]}...")

        # 收集参考图片
        reference_images = []

        if use_layered_map and story and region_id:
            # 获取区域地图作为参考
            if region_id not in region_map_cache:
                region = get_region_for_location(story, loc_id)
                region_map_path = region.get("region_map_image") if region else None
                if region_map_path and Path(region_map_path).exists():
                    region_map_cache[region_id] = load_image_as_pil(region_map_path)
                    print(f"  使用区域地图参考: {region_map_path}")
                else:
                    region_map_cache[region_id] = None

            if region_map_cache.get(region_id):
                reference_images.append(region_map_cache[region_id])

            # 获取同区域前一个场景的背景图作为参考
            if region_id in region_prev_backgrounds:
                prev_bg_path = region_prev_backgrounds[region_id]
                if Path(prev_bg_path).exists():
                    prev_bg_img = load_image_as_pil(prev_bg_path)
                    if prev_bg_img:
                        reference_images.append(prev_bg_img)
                        print(f"  使用同区域前一场景参考: {prev_bg_path}")

        # 生成背景图
        output_path = get_location_background_path(loc_id, output_dir)
        image_path = generate_depth_aware_background(
            client, prompt, output_path,
            reference_images if reference_images else None
        )

        if image_path:
            # 更新剧本中的背景图路径
            for loc in screenplay.get("locations", []):
                if loc.get("location_id") == loc_id:
                    loc["background_image"] = image_path
                    loc["depth_enhanced"] = True  # 标记为深度增强
                    break

            # 记录已生成的背景图
            if region_id:
                region_prev_backgrounds[region_id] = image_path

            save_screenplay(screenplay)
            generated_count += 1

    # 输出统计
    total = len(locations)
    existing = total - len(locations_to_generate) + generated_count
    print(f"\n场景背景图: {existing}/{total}")

    print_header("深度感知背景生成完成 (方案 C1)")

    if generated_count > 0:
        print("\n已生成的深度感知背景图:")
        for location in screenplay.get("locations", []):
            bg_img = location.get("background_image")
            if bg_img and location.get("depth_enhanced"):
                region_id = location.get("region_id", "?")
                print(f"  - 场景 {location.get('location_id')} [区域 {region_id}]: {bg_img}")

    print(f"\n请检查生成的背景图: open {output_dir}")


if __name__ == "__main__":
    main()
