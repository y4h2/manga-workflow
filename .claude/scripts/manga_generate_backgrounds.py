#!/usr/bin/env python3
"""
AI 漫剧生成 - 场景背景生成脚本 (阶段 1.5)
为每个场景生成纯背景图（无人物）

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 确保已有 screenplay.json（使用 locations 格式）
4. 运行脚本: python .claude/scripts/manga_generate_backgrounds.py
"""

import argparse
from pathlib import Path

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
)


def build_background_prompt(location: dict, style_keywords: str) -> str:
    """构建场景背景生成提示词

    Args:
        location: 场景数据
        style_keywords: 风格关键词

    Returns:
        生成提示词
    """
    name = location.get("name", "")
    time_of_day = location.get("time_of_day", "day")
    background_prompt = location.get("background_prompt", "")

    # 如果有预定义的 background_prompt，使用它
    if background_prompt:
        # 确保以 anime style 开头
        if not background_prompt.lower().startswith("anime style"):
            background_prompt = f"anime style, {background_prompt}"

        # 确保强调无人物
        if "no character" not in background_prompt.lower() and "no people" not in background_prompt.lower():
            background_prompt += ", no characters, no people, background only"

        return build_enhanced_prompt(background_prompt, style_keywords)

    # 根据时间设置光线描述
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

    # 构建默认提示词
    prompt = f"""anime style, background scene, no characters, no people:

Location: {name}
Time: {time_of_day}
Lighting: {lighting}

Technical Requirements:
- Pure background scene with NO characters or people
- Detailed environment and atmosphere
- Consistent anime art style
- High quality, cinematic composition
- {style_keywords}

Important: This is a BACKGROUND ONLY image. Do NOT include any characters, people, or human figures."""

    return prompt


def generate_background(client, prompt: str, output_path: Path) -> str:
    """生成场景背景图

    Args:
        client: Gemini API 客户端
        prompt: 生成提示词
        output_path: 输出路径

    Returns:
        生成图片的路径，失败返回 None
    """
    print(f"  正在生成背景图...")

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
                print(f"  背景图已保存: {output_path}")
                return str(output_path)

        print("  未能生成背景图")
        return None

    except Exception as e:
        print(f"  背景图生成失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI 漫剧 - 场景背景生成")
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
    args = parser.parse_args()

    print_header("AI 漫剧 - 场景背景生成")

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
        print("\n错误: 当前剧本使用旧格式，不支持场景背景生成")
        print("请使用 locations 格式的剧本，或使用 manga_generate_images.py 直接生成图片")
        return

    # 获取场景列表
    locations = screenplay.get("locations", [])
    if not locations:
        print("\n错误: 剧本中没有场景定义")
        print("请确保 screenplay.json 包含 locations 数组")
        return

    print(f"\n场景数量: {len(locations)}")

    # 统计需要生成的场景
    locations_to_generate = []
    for location in locations:
        loc_id = location.get("location_id", 0)

        # 如果指定了只生成某个场景
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

    print(f"\n需要生成 {len(locations_to_generate)} 个场景的背景图")

    # 生成背景图
    generated_count = 0
    for location in locations_to_generate:
        loc_id = location.get("location_id", 0)
        loc_name = location.get("name", "未知场景")
        time_of_day = location.get("time_of_day", "day")

        print(f"\n{'='*50}")
        print(f"场景 {loc_id}: {loc_name}")
        print(f"时间: {time_of_day}")
        print("=" * 50)

        # 构建提示词
        prompt = build_background_prompt(location, style_keywords)
        print(f"  提示词: {prompt[:100]}...")

        # 生成背景图
        output_path = get_location_background_path(loc_id, output_dir)
        image_path = generate_background(client, prompt, output_path)

        if image_path:
            # 更新剧本中的背景图路径
            for loc in screenplay.get("locations", []):
                if loc.get("location_id") == loc_id:
                    loc["background_image"] = image_path
                    break

            # 每生成一张图片就保存
            save_screenplay(screenplay)
            generated_count += 1

    # 输出统计
    total = len(locations)
    existing = total - len(locations_to_generate) + generated_count
    print(f"\n场景背景图: {existing}/{total}")

    # 完成
    print_header("场景背景生成完成")

    if generated_count > 0:
        print("\n已生成的背景图:")
        for location in screenplay.get("locations", []):
            bg_img = location.get("background_image")
            if bg_img:
                print(f"  - 场景 {location.get('location_id')}: {bg_img}")

    print("\n请检查生成的背景图:")
    print(f"  open {output_dir}")
    print("\n如果满意，可以继续生成镜头图片:")
    print("  python .claude/scripts/manga_generate_images.py")


if __name__ == "__main__":
    main()
