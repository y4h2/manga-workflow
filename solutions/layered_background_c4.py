#!/usr/bin/env python3
"""
AI 漫剧生成 - 方案 C4: Rembg 背景移除分层
分别生成场景元素在绿色背景上，然后用 rembg 去除背景后叠加

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow rembg onnxruntime
3. 运行脚本: python solutions/layered_background_c4.py

参数:
  --location N: 只生成指定场景
  --force: 强制重新生成所有背景图
  --no-reference: 不使用区域地图作为参考

本方案分别生成三个层次的场景元素，每层都在纯绿色背景上。
然后使用 rembg 工具移除绿色背景，最后叠加合成完整背景。
优点是可以得到真正分离的三层，支持后续的视差滚动效果。
"""

import argparse
import io
import sys
from pathlib import Path

from PIL import Image

# 添加 .claude/scripts 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "scripts"))

from manga_common import (
    IMAGE_MODEL,
    setup_client,
    load_screenplay,
    save_screenplay,
    get_output_dir_from_screenplay,
    get_style_keywords,
    print_header,
    is_location_format,
    load_story_outline,
    build_inherited_style,
    build_style_prompt_from_inherited,
    load_image_as_pil,
    has_layered_map_system,
    get_region_for_location,
    get_layered_background_paths,
    build_layer_prompt,
    composite_layers,
)


def remove_background(image: Image.Image) -> Image.Image:
    """使用 rembg 移除背景

    Args:
        image: 输入图像 (PIL Image)

    Returns:
        带透明背景的图像
    """
    try:
        from rembg import remove
    except ImportError:
        print("错误: 请安装依赖: pip install rembg onnxruntime")
        sys.exit(1)

    # 直接使用 rembg 处理 PIL Image
    result = remove(image)
    return result


def generate_layer(client, prompt: str, output_path: Path) -> Image.Image:
    """生成单个图层

    Args:
        client: Gemini 客户端
        prompt: 生成提示词
        output_path: 输出路径

    Returns:
        生成的图像 (PIL Image)，失败返回 None
    """
    print(f"  正在生成...")

    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[prompt],
            config={"response_modalities": ["IMAGE"]}
        )

        for part in response.parts:
            if part.inline_data is not None:
                # Gemini 返回的图像对象，保存到文件
                gemini_image = part.as_image()
                gemini_image.save(str(output_path))
                print(f"  原始层已保存: {output_path}")

                # 重新加载为 PIL Image 以便后续处理
                pil_image = Image.open(str(output_path))
                return pil_image

        print("  未能生成图层")
        return None

    except Exception as e:
        print(f"  生成失败: {e}")
        return None


def process_location(client, location: dict, output_dir: Path, style_keywords: str,
                     story: dict = None, use_layered_map: bool = False, region_map_cache: dict = None,
                     force: bool = False):
    """处理单个场景的分层背景生成

    Args:
        client: Gemini 客户端
        location: 场景数据
        output_dir: 输出目录
        style_keywords: 风格关键词
        story: 故事大纲（可选）
        use_layered_map: 是否使用分层地图
        region_map_cache: 区域地图缓存
        force: 是否强制重新生成

    Returns:
        分层结果字典，失败返回 None
    """
    loc_id = location.get("location_id", 0)
    loc_name = location.get("name", "未知场景")
    region_id = location.get("region_id")

    # 检查是否已存在
    paths = get_layered_background_paths(loc_id, output_dir)
    if not force and all(p.exists() for p in [paths["far"], paths["mid"], paths["near"], paths["composite"]]):
        print(f"  场景 {loc_id} 分层已存在，跳过")
        return None

    print(f"\n{'='*50}")
    print(f"场景 {loc_id}: {loc_name}")
    print("=" * 50)

    # 获取继承的风格
    inherited_style = None
    if story and use_layered_map:
        inherited_style = build_inherited_style(story, location_id=loc_id)
        if inherited_style:
            print(f"  继承风格: {build_style_prompt_from_inherited(inherited_style)[:60]}...")

    layer_images = {}

    # 生成三层
    for layer_type in ["far", "mid", "near"]:
        print(f"\n生成 {layer_type} 层...")

        # 生成在绿色背景上的图像
        raw_path = output_dir / f"loc_{loc_id:02d}_{layer_type}_raw.png"
        prompt = build_layer_prompt(location, layer_type, style_keywords, inherited_style)
        raw_img = generate_layer(client, prompt, raw_path)

        if raw_img is None:
            print(f"  {layer_type} 层生成失败")
            continue

        # 移除绿色背景
        print(f"  移除背景...")
        transparent_img = remove_background(raw_img)

        transparent_path = paths[layer_type]
        transparent_img.save(str(transparent_path))
        print(f"  透明层已保存: {transparent_path}")

        layer_images[layer_type] = transparent_img

        # 删除原始文件（可选）
        # raw_path.unlink()

    # 合成完整背景
    if all(k in layer_images for k in ["far", "mid", "near"]):
        print("\n合成完整背景...")

        composite = composite_layers(
            layer_images["far"],
            layer_images["mid"],
            layer_images["near"]
        )

        composite_path = paths["composite"]
        composite.save(str(composite_path))
        print(f"合成背景已保存: {composite_path}")

        return {
            "enabled": True,
            "far_layer": str(paths["far"]),
            "mid_layer": str(paths["mid"]),
            "near_layer": str(paths["near"]),
        }

    return None


def main():
    parser = argparse.ArgumentParser(description="AI 漫剧 - 分层背景生成 (方案 C4)")
    parser.add_argument("--location", type=int, default=None, help="只生成指定场景")
    parser.add_argument("--force", action="store_true", help="强制重新生成")
    parser.add_argument("--no-reference", action="store_true", help="不使用区域地图作为参考")
    args = parser.parse_args()

    print_header("AI 漫剧 - 分层背景生成 (方案 C4)")

    # 初始化
    client = setup_client()
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)
    style_keywords = get_style_keywords(screenplay)

    title = screenplay.get("title", "未命名")
    print(f"\n剧本: {title}")
    print(f"输出目录: {output_dir.absolute()}")
    print("\n方案 C4: 分别生成三层，用 rembg 去除背景后合成")

    if not is_location_format(screenplay):
        print("错误: 当前剧本不是 locations 格式")
        return

    # 尝试加载故事大纲
    story = None
    use_layered_map = False
    region_map_cache = {}

    try:
        story = load_story_outline(output_dir)
        use_layered_map = has_layered_map_system(story) and not args.no_reference
        if use_layered_map:
            print("\n检测到分层地图系统，将继承区域风格")
    except SystemExit:
        print("\n注意: 未找到 story_outline.json")

    # 处理场景
    locations = screenplay.get("locations", [])
    processed_count = 0

    for location in locations:
        loc_id = location.get("location_id", 0)

        if args.location is not None and loc_id != args.location:
            continue

        result = process_location(
            client, location, output_dir, style_keywords,
            story, use_layered_map, region_map_cache, args.force
        )

        if result:
            # 更新剧本
            location["depth_layers"] = result
            location["background_image"] = str(get_layered_background_paths(loc_id, output_dir)["composite"])
            save_screenplay(screenplay)
            processed_count += 1

    print_header("分层背景生成完成 (方案 C4)")
    print(f"\n处理了 {processed_count} 个场景")

    if processed_count > 0:
        print("\n生成的文件:")
        print("  - loc_XX_far.png: 远景层（透明背景）")
        print("  - loc_XX_mid.png: 中景层（透明背景）")
        print("  - loc_XX_near.png: 近景层（透明背景）")
        print("  - loc_XX_bg.png: 合成后完整背景")
        print("\n可以使用 parallax_video.py 生成视差滚动视频")


if __name__ == "__main__":
    main()
