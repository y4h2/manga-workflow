#!/usr/bin/env python3
"""
AI 漫剧生成 - 过渡图片生成脚本
在相邻场景之间生成过渡图片，使画面更加连续流畅

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 确保已运行图片生成脚本
4. 运行脚本: python .claude/scripts/manga_generate_transitions.py

参数:
  --count: 每对场景之间的过渡图片数量 (默认: 1)
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
    print_header,
    get_style_keywords,
    build_enhanced_prompt,
)


def get_transition_path(scene_a_id: int, scene_b_id: int, index: int, output_dir: Path) -> Path:
    """获取过渡图片路径

    Args:
        scene_a_id: 前一个场景 ID
        scene_b_id: 后一个场景 ID
        index: 过渡图片索引 (从 1 开始)
        output_dir: 输出目录

    Returns:
        过渡图片路径，格式: transition_01_02_1.png
    """
    return output_dir / f"transition_{scene_a_id:02d}_{scene_b_id:02d}_{index}.png"


def build_transition_prompt(scene_a: dict, scene_b: dict, style_keywords: str, index: int, total: int) -> str:
    """构建过渡图片的提示词

    Args:
        scene_a: 前一个场景
        scene_b: 后一个场景
        style_keywords: 风格关键词
        index: 当前过渡图片索引 (从 1 开始)
        total: 总过渡图片数量

    Returns:
        过渡提示词
    """
    # 计算过渡进度 (0.0 到 1.0)
    progress = index / (total + 1)

    # 提取场景信息
    prompt_a = scene_a.get("image_prompt", "")
    prompt_b = scene_b.get("image_prompt", "")
    narration_a = scene_a.get("narration", "")
    narration_b = scene_b.get("narration", "")
    character_desc = scene_a.get("character_description", "") or scene_b.get("character_description", "")

    # 构建过渡提示词
    transition_prompt = f"""Create a transition image that bridges two scenes.

PREVIOUS SCENE ({int((1-progress)*100)}% influence):
{prompt_a}
Context: {narration_a[:100]}

NEXT SCENE ({int(progress*100)}% influence):
{prompt_b}
Context: {narration_b[:100]}

TRANSITION REQUIREMENTS:
- This is transition frame {index} of {total} between the two scenes
- Blend visual elements from both scenes naturally
- Maintain character consistency: {character_desc}
- Create a smooth visual flow that connects the two moments
- Keep the same art style and color palette
- The composition should feel like a natural in-between moment

Style: {style_keywords}"""

    return transition_prompt


def generate_transition_image(client, prompt: str, reference_image, output_path: Path):
    """生成过渡图片

    Args:
        client: Gemini API 客户端
        prompt: 过渡提示词
        reference_image: 参考图片 (PIL Image)
        output_path: 输出路径

    Returns:
        成功返回路径字符串，失败返回 None
    """
    print(f"  正在生成过渡图片...")

    try:
        # 构建 contents，使用参考图片
        if reference_image:
            contents = [reference_image, prompt]
        else:
            contents = [prompt]

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
                print(f"  过渡图片已保存: {output_path}")
                return str(output_path)

        print("  未能生成过渡图片")
        return None

    except Exception as e:
        print(f"  过渡图片生成失败: {e}")
        return None


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="AI 漫剧 - 过渡图片生成")
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="每对场景之间的过渡图片数量 (默认: 1)"
    )
    args = parser.parse_args()

    print_header("AI 漫剧 - 过渡图片生成")

    # 初始化
    client = setup_client()
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)

    title = screenplay.get("title", "未命名")
    style_keywords = get_style_keywords(screenplay)

    # 获取场景列表
    scenes = screenplay.get("scenes", [])
    if len(scenes) < 2:
        print("错误: 需要至少 2 个场景才能生成过渡图片")
        return

    print(f"\n剧本: {title}")
    print(f"场景数: {len(scenes)}")
    print(f"每对场景过渡图片数: {args.count}")
    print(f"预计生成过渡图片: {(len(scenes) - 1) * args.count} 张")
    print(f"输出目录: {output_dir}")

    # 检查场景图片是否存在
    missing_images = []
    for scene in scenes:
        scene_id = scene.get("scene_id", 0)
        image_path = scene.get("image_path")
        if not image_path or not Path(image_path).exists():
            missing_images.append(scene_id)

    if missing_images:
        print(f"\n错误: 以下场景缺少图片: {missing_images}")
        print("请先运行: python .claude/scripts/manga_generate_images.py")
        return

    # 初始化 transitions 列表
    if "transitions" not in screenplay:
        screenplay["transitions"] = []

    # 生成过渡图片
    transitions_generated = 0

    for i in range(len(scenes) - 1):
        scene_a = scenes[i]
        scene_b = scenes[i + 1]
        scene_a_id = scene_a.get("scene_id", i + 1)
        scene_b_id = scene_b.get("scene_id", i + 2)

        print(f"\n{'='*50}")
        print(f"生成过渡: 场景 {scene_a_id} → 场景 {scene_b_id}")
        print(f"{'='*50}")

        # 加载前一个场景的图片作为参考
        image_path_a = scene_a.get("image_path")
        try:
            reference_image = Image.open(image_path_a)
            print(f"  使用参考图片: {image_path_a}")
        except Exception as e:
            print(f"  警告: 无法加载参考图片: {e}")
            reference_image = None

        # 生成指定数量的过渡图片
        for idx in range(1, args.count + 1):
            transition_path = get_transition_path(scene_a_id, scene_b_id, idx, output_dir)

            # 检查是否已存在
            existing = next(
                (t for t in screenplay["transitions"]
                 if t.get("from_scene") == scene_a_id
                 and t.get("to_scene") == scene_b_id
                 and t.get("index") == idx),
                None
            )

            if existing and existing.get("image_path") and Path(existing["image_path"]).exists():
                print(f"  过渡 {idx}/{args.count} 已存在，跳过")
                continue

            # 构建过渡提示词
            prompt = build_transition_prompt(scene_a, scene_b, style_keywords, idx, args.count)
            print(f"  生成过渡 {idx}/{args.count}...")

            # 生成图片
            result_path = generate_transition_image(client, prompt, reference_image, transition_path)

            if result_path:
                # 记录过渡信息
                transition_data = {
                    "from_scene": scene_a_id,
                    "to_scene": scene_b_id,
                    "index": idx,
                    "image_path": result_path
                }

                # 更新或添加
                if existing:
                    existing.update(transition_data)
                else:
                    screenplay["transitions"].append(transition_data)

                transitions_generated += 1

                # 更新参考图片为刚生成的过渡图片
                try:
                    reference_image = Image.open(result_path)
                except Exception:
                    pass

                # 保存进度
                save_screenplay(screenplay)

    # 输出统计
    print_header("过渡图片生成完成")
    total_transitions = (len(scenes) - 1) * args.count
    existing_transitions = len([t for t in screenplay.get("transitions", []) if t.get("image_path")])
    print(f"过渡图片: {existing_transitions}/{total_transitions}")
    print(f"本次生成: {transitions_generated} 张")
    print(f"\n下一步: 运行 python .claude/scripts/manga_generate_videos.py --duration 2 生成视频")


if __name__ == "__main__":
    main()
