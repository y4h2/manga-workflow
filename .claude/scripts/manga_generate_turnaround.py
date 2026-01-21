#!/usr/bin/env python3
"""
AI 漫剧生成 - 角色三视图生成脚本
生成角色的正面、侧面、背面三视图，用于保持角色一致性

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 确保已有 screenplay.json
4. 运行脚本: python .claude/scripts/manga_generate_turnaround.py
"""

from pathlib import Path

from manga_common import (
    IMAGE_MODEL,
    setup_client,
    load_screenplay,
    save_screenplay,
    get_output_dir_from_screenplay,
    get_turnaround_path,
    print_header,
)


def build_turnaround_prompt(character_description: str) -> str:
    """构建三视图生成提示词"""
    return f"""Character turnaround sheet with three views arranged horizontally in a single image:

LEFT SECTION: Front view (character facing directly toward viewer)
CENTER SECTION: Side view (character in profile, facing right)
RIGHT SECTION: Back view (character facing away from viewer)

Character Details:
{character_description}

Technical Requirements:
- Layout: Three full body shots side by side in one horizontal image
- Style: Anime/manga art style, clean line art, vibrant colors
- Quality: High quality, detailed, consistent proportions across all views
- Background: Plain white or light gray background
- Pose: Neutral standing pose, arms slightly away from body for visibility
- Composition: Full body visible in each view, equal spacing between views
- Consistency: Same character design, clothing, and colors in all three views

Important: Generate all three views in a single image, arranged horizontally from left to right (front, side, back)."""


def generate_turnaround(client, prompt: str, output_dir):
    """调用 Gemini 图片生成 API 生成三视图

    Args:
        client: Gemini API 客户端
        prompt: 生成提示词
        output_dir: 输出目录
    """
    print("  正在生成角色三视图...")

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
                image_path = get_turnaround_path(output_dir)
                image.save(str(image_path))
                print(f"  三视图已保存: {image_path}")
                return str(image_path)

        print("  未能生成三视图")
        return None

    except Exception as e:
        print(f"  三视图生成失败: {e}")
        return None


def get_character_base_description(screenplay: dict, output_dir: Path) -> tuple:
    """从剧本获取角色基本描述

    支持多种格式：
    1. 新格式 (locations): 从 story_outline.json 的 characters[0].appearance 获取
    2. 旧格式 (scenes): 从第一个场景的 character_description 获取
    3. 旧格式 (sequences): 从第一个 shot 的 character_description 获取

    Returns:
        (character_name, character_description) 或 (None, None)
    """
    import json

    # 新格式：尝试从 story_outline.json 获取
    story_outline_path = output_dir / "story_outline.json"
    if story_outline_path.exists():
        try:
            with open(story_outline_path, "r", encoding="utf-8") as f:
                story = json.load(f)
            characters = story.get("characters", [])
            if characters:
                char = characters[0]
                char_name = char.get("name", "角色")
                char_appearance = char.get("appearance", "")
                if char_appearance:
                    return char_name, char_appearance
        except Exception:
            pass

    # 旧格式：从 scenes 获取
    scenes = screenplay.get("scenes", [])
    if scenes:
        first_scene = scenes[0]
        desc = first_scene.get("character_description", "")
        if desc:
            return "角色", desc

    # 旧格式：从 sequences 获取
    sequences = screenplay.get("sequences", [])
    for seq in sequences:
        for shot in seq.get("shots", []):
            desc = shot.get("character_description", "")
            if desc:
                return "角色", desc

    return None, None


def main():
    """主函数"""
    print_header("AI 漫剧 - 角色三视图生成")

    # 初始化
    client = setup_client()
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)

    title = screenplay.get("title", "未命名")

    print(f"\n剧本: {title}")
    print(f"输出目录: {output_dir.absolute()}")

    # 检查是否已有三视图
    turnaround_path = get_turnaround_path(output_dir)
    existing_path = screenplay.get("turnaround_path")

    if existing_path and Path(existing_path).exists():
        print(f"\n三视图已存在: {existing_path}")
        print("如需重新生成，请删除该文件后重新运行此脚本")
        return

    # 获取角色描述
    character_name, character_description = get_character_base_description(screenplay, output_dir)

    if not character_description:
        print("\n错误: 无法获取角色描述")
        print("请确保 story_outline.json 中包含 characters[0].appearance")
        print("或剧本中包含 character_description 字段")
        return

    print(f"\n角色: {character_name}")
    print(f"角色描述: {character_description}")

    # 构建提示词并生成
    prompt = build_turnaround_prompt(character_description)
    print("\n生成提示词:")
    print("-" * 40)
    print(prompt[:200] + "..." if len(prompt) > 200 else prompt)
    print("-" * 40)

    turnaround_path = generate_turnaround(client, prompt, output_dir)

    if turnaround_path:
        # 更新剧本
        screenplay["turnaround_path"] = turnaround_path
        save_screenplay(screenplay)

        print_header("三视图生成完成")
        print(f"三视图路径: {turnaround_path}")
        print("\n请检查生成的三视图:")
        print(f"  open {turnaround_path}")
        print("\n如果满意，可以继续生成分镜图片:")
        print("  python .claude/scripts/manga_generate_images.py")
    else:
        print("\n三视图生成失败，请检查错误信息后重试")


if __name__ == "__main__":
    main()
