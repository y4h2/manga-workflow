#!/usr/bin/env python3
"""
AI 漫剧生成 - 视频封面生成脚本
为视频生成电影海报风格的封面图片

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 运行脚本: python .claude/scripts/manga_generate_cover.py --title "标题" --output output/项目名/cover.png

可选参数:
--reference: 参考图片路径 (风格参考)
--character: 角色参考图路径
--style: 风格关键词
--description: 故事简介
--protagonist: 主角描述
"""

import argparse
import os
from pathlib import Path

from PIL import Image
from google import genai


# 模型配置
IMAGE_MODEL = "gemini-3-pro-image-preview"


def setup_client():
    """初始化 genai 客户端"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("错误: 请设置环境变量 GEMINI_API_KEY")
        print("获取 API Key: https://aistudio.google.com/apikey")
        exit(1)
    return genai.Client(api_key=api_key)


def load_image(image_path: str):
    """加载图片为 PIL Image 对象"""
    try:
        return Image.open(image_path)
    except Exception as e:
        print(f"警告: 无法加载图片 {image_path}: {e}")
        return None


def build_cover_prompt(
    title: str,
    description: str = "",
    protagonist: str = "",
    style: str = ""
) -> str:
    """构建封面生成提示词

    Args:
        title: 视频标题
        description: 故事简介
        protagonist: 主角描述
        style: 风格关键词

    Returns:
        封面生成提示词
    """
    prompt_parts = [
        f'Create a movie poster / video cover image for "{title}".',
        "",
        "Design elements:",
        f'- Title "{title}" prominently displayed in stylized Chinese calligraphy/brush stroke font at the top',
    ]

    if protagonist:
        prompt_parts.append(f"- {protagonist}")

    if description:
        prompt_parts.append(f"- Scene setting: {description}")

    prompt_parts.extend([
        "",
        "Visual style:",
    ])

    if style:
        prompt_parts.append(f"- {style}")
    else:
        prompt_parts.append("- Cinematic lighting, dramatic composition")

    prompt_parts.extend([
        "- Professional movie poster composition",
        "- Film grain texture",
        "- Atmospheric, emotional",
        "",
        "Aspect ratio: 16:9",
    ])

    return "\n".join(prompt_parts)


def generate_cover(
    client,
    prompt: str,
    output_path: Path,
    reference_images: list = None
):
    """生成封面图片

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
        print(f"正在生成封面 (使用 {ref_count} 个参考图片)...")
    else:
        print("正在生成封面...")

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
                # 确保输出目录存在
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(str(output_path))
                print(f"封面已保存: {output_path}")
                return str(output_path)

        print("未能生成封面图片")
        return None

    except Exception as e:
        print(f"封面生成失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI 漫剧 - 视频封面生成")
    parser.add_argument(
        "--title",
        required=True,
        help="视频标题 (将显示在封面上)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="输出路径 (如: output/项目名/cover.png)"
    )
    parser.add_argument(
        "--reference",
        default=None,
        help="风格参考图片路径"
    )
    parser.add_argument(
        "--character",
        default=None,
        help="角色参考图片路径"
    )
    parser.add_argument(
        "--style",
        default="Anime style, cinematic lighting, teal and orange color grading",
        help="风格关键词"
    )
    parser.add_argument(
        "--description",
        default="",
        help="故事简介/场景描述"
    )
    parser.add_argument(
        "--protagonist",
        default="",
        help="主角描述"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("AI 漫剧 - 视频封面生成")
    print("=" * 60)

    # 初始化
    client = setup_client()

    print(f"\n标题: {args.title}")
    print(f"风格: {args.style}")
    print(f"输出: {args.output}")

    # 加载参考图片
    reference_images = []

    if args.reference:
        ref_img = load_image(args.reference)
        if ref_img:
            reference_images.append(ref_img)
            print(f"已加载风格参考图: {args.reference}")

    if args.character:
        char_img = load_image(args.character)
        if char_img:
            reference_images.append(char_img)
            print(f"已加载角色参考图: {args.character}")

    # 构建提示词
    prompt = build_cover_prompt(
        title=args.title,
        description=args.description,
        protagonist=args.protagonist,
        style=args.style
    )

    print(f"\n生成提示词:\n{prompt}\n")

    # 生成封面
    output_path = Path(args.output)
    result = generate_cover(
        client,
        prompt,
        output_path,
        reference_images=reference_images if reference_images else None
    )

    if result:
        print("\n" + "=" * 60)
        print("封面生成完成!")
        print("=" * 60)
        print(f"\n查看封面: open {result}")
    else:
        print("\n封面生成失败，请重试")
        exit(1)


if __name__ == "__main__":
    main()
