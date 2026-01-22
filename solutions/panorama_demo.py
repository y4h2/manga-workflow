#!/usr/bin/env python3
"""
全景背景 + 裁切 Demo

功能：
1. 生成超长全景背景图（分块生成 + 拼接）
2. 自动计算裁切区域
3. 生成镜头 pan 视频

使用示例：
    # 生成全景背景
    python solutions/panorama_demo.py \
        --prompt "anime style, cyberpunk city street at night" \
        --num-shots 4 \
        --output output/demo_panorama.png

    # 查看裁切区域预览
    python solutions/panorama_demo.py \
        --panorama output/demo_panorama.png \
        --preview-crops 4

    # 生成 pan 视频
    python solutions/panorama_demo.py \
        --panorama output/demo_panorama.png \
        --pan left_to_right \
        --duration 5 \
        --output output/demo_pan.mp4
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import Optional

from PIL import Image

# Add parent directory to path for manga_common import
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "scripts"))

try:
    from manga_common import setup_client, IMAGE_MODEL
except ImportError:
    # Fallback if manga_common is not available
    from google import genai
    IMAGE_MODEL = "gemini-3-pro-image-preview"

    def setup_client():
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("错误: 请设置环境变量 GEMINI_API_KEY")
            sys.exit(1)
        return genai.Client(api_key=api_key)


# ============================================================
# 常量配置
# ============================================================

# 单块最大尺寸 (Gemini 限制)
TILE_WIDTH = 1408
TILE_HEIGHT = 768

# 默认输出尺寸
DEFAULT_OUTPUT_HEIGHT = 1080
DEFAULT_OUTPUT_WIDTH = 1920

# 重叠比例 (用于拼接)
DEFAULT_OVERLAP = 0.25


# ============================================================
# 全景图生成
# ============================================================


def calculate_num_tiles(num_shots: int) -> int:
    """根据镜头数计算所需的 tile 数量

    Args:
        num_shots: 计划的镜头数

    Returns:
        需要的 tile 数量
    """
    if num_shots <= 3:
        return 2  # 2x 宽度
    elif num_shots <= 5:
        return 3  # 3x 宽度
    else:
        return 4  # 4x 宽度


def calculate_panorama_width(num_tiles: int, overlap: float = DEFAULT_OVERLAP) -> int:
    """计算拼接后的全景图宽度

    Args:
        num_tiles: tile 数量
        overlap: 重叠比例

    Returns:
        拼接后的总宽度（像素）
    """
    overlap_px = int(TILE_WIDTH * overlap)
    return TILE_WIDTH * num_tiles - overlap_px * (num_tiles - 1)


def generate_single_tile(
    client,
    prompt: str,
    reference_image: Optional[Image.Image] = None,
    is_first: bool = True,
    tile_position: str = "left"
) -> Image.Image:
    """生成单个 tile

    Args:
        client: Gemini client
        prompt: 基础提示词
        reference_image: 参考图（前一个 tile 的右边缘）
        is_first: 是否是第一个 tile
        tile_position: tile 位置 ("left", "middle", "right")

    Returns:
        生成的 PIL Image
    """
    # 构建增强提示词
    if is_first:
        enhanced_prompt = f"""{prompt}

CRITICAL REQUIREMENTS:
- Create a wide scene that continues seamlessly to the right
- No border or frame on the right edge
- Scene elements should extend beyond the frame edge
- Composition weighted slightly to the left
- Aspect ratio: 16:9 wide format"""
    else:
        position_hint = "middle section" if tile_position == "middle" else "right section"
        enhanced_prompt = f"""{prompt}

CRITICAL REQUIREMENTS:
- This is the {position_hint} of a continuous panorama
- The scene MUST seamlessly continue from the reference image (left edge)
- Match the exact style, colors, lighting, and horizon line
- Scene elements should naturally flow from the reference
- {"Extend beyond the right edge, scene continues" if tile_position != "right" else "Natural scene ending on the right"}
- Aspect ratio: 16:9 wide format"""

    print(f"  生成 tile ({tile_position})...")

    try:
        # 准备生成参数
        from google.genai import types

        contents = [enhanced_prompt]
        if reference_image and not is_first:
            contents.insert(0, reference_image)

        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        # 提取图像
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                import io
                image_bytes = part.inline_data.data
                return Image.open(io.BytesIO(image_bytes))

        print(f"  警告: 未能生成 tile")
        return None

    except Exception as e:
        print(f"  错误: 生成 tile 失败 - {e}")
        return None


def extract_edge(image: Image.Image, edge: str = "right", width: int = 100) -> Image.Image:
    """提取图像边缘作为参考

    Args:
        image: 源图像
        edge: 边缘位置 ("left" 或 "right")
        width: 边缘宽度

    Returns:
        边缘图像
    """
    if edge == "right":
        return image.crop((image.width - width, 0, image.width, image.height))
    else:
        return image.crop((0, 0, width, image.height))


def generate_tiles(client, prompt: str, num_tiles: int) -> list:
    """生成多个 tiles

    Args:
        client: Gemini client
        prompt: 基础提示词
        num_tiles: tile 数量

    Returns:
        tile 图像列表
    """
    tiles = []

    for i in range(num_tiles):
        is_first = (i == 0)
        if i == num_tiles - 1:
            position = "right"
        elif i == 0:
            position = "left"
        else:
            position = "middle"

        # 使用前一个 tile 的边缘作为参考
        reference = None
        if not is_first and tiles:
            reference = extract_edge(tiles[-1], "right", width=200)

        tile = generate_single_tile(
            client,
            prompt,
            reference_image=reference,
            is_first=is_first,
            tile_position=position
        )

        if tile:
            tiles.append(tile)
            print(f"  Tile {i + 1}/{num_tiles} 完成 ({tile.width}x{tile.height})")
        else:
            print(f"  错误: Tile {i + 1} 生成失败")
            break

    return tiles


def stitch_tiles_with_blend(tiles: list, overlap: float = DEFAULT_OVERLAP) -> Image.Image:
    """使用渐变混合拼接 tiles

    Args:
        tiles: tile 图像列表
        overlap: 重叠比例 (0-1)

    Returns:
        拼接后的全景图
    """
    if not tiles:
        return None

    if len(tiles) == 1:
        return tiles[0]

    # 确保所有 tile 高度一致
    target_height = tiles[0].height
    resized_tiles = []
    for tile in tiles:
        if tile.height != target_height:
            ratio = target_height / tile.height
            new_width = int(tile.width * ratio)
            tile = tile.resize((new_width, target_height), Image.Resampling.LANCZOS)
        resized_tiles.append(tile)

    tile_width = resized_tiles[0].width
    overlap_px = int(tile_width * overlap)

    # 计算总宽度
    total_width = tile_width * len(resized_tiles) - overlap_px * (len(resized_tiles) - 1)
    result = Image.new('RGB', (total_width, target_height))

    x_offset = 0
    for i, tile in enumerate(resized_tiles):
        if i == 0:
            # 第一个 tile 直接粘贴
            result.paste(tile, (0, 0))
            x_offset = tile_width - overlap_px
        else:
            # 创建水平渐变 mask
            gradient = create_horizontal_gradient(overlap_px, tile.height)

            # 获取重叠区域
            overlap_left = result.crop((x_offset, 0, x_offset + overlap_px, tile.height))
            overlap_right = tile.crop((0, 0, overlap_px, tile.height))

            # 混合重叠区域
            blended = Image.composite(overlap_right, overlap_left, gradient)

            # 粘贴混合区域
            result.paste(blended, (x_offset, 0))

            # 粘贴非重叠部分
            result.paste(
                tile.crop((overlap_px, 0, tile.width, tile.height)),
                (x_offset + overlap_px, 0)
            )

            x_offset += tile.width - overlap_px

    return result


def create_horizontal_gradient(width: int, height: int) -> Image.Image:
    """创建水平渐变 mask（从左到右，黑到白）

    Args:
        width: 宽度
        height: 高度

    Returns:
        灰度渐变图像
    """
    gradient = Image.new('L', (width, height))
    for x in range(width):
        value = int(255 * x / (width - 1)) if width > 1 else 255
        for y in range(height):
            gradient.putpixel((x, y), value)
    return gradient


def generate_panorama(
    client,
    prompt: str,
    num_shots: int,
    output_path: str,
    target_height: int = DEFAULT_OUTPUT_HEIGHT
) -> Optional[str]:
    """生成全景图

    Args:
        client: Gemini client
        prompt: 场景描述
        num_shots: 计划的镜头数
        output_path: 输出路径
        target_height: 目标高度

    Returns:
        输出文件路径，失败返回 None
    """
    print(f"开始生成全景图...")
    print(f"  场景描述: {prompt[:50]}...")
    print(f"  计划镜头数: {num_shots}")

    # 计算 tile 数量
    num_tiles = calculate_num_tiles(num_shots)
    estimated_width = calculate_panorama_width(num_tiles)
    print(f"  计算 tile 数: {num_tiles} ({estimated_width}px 预估宽度)")

    # 生成 tiles
    tiles = generate_tiles(client, prompt, num_tiles)
    if not tiles:
        print("错误: 未能生成任何 tile")
        return None

    print(f"成功生成 {len(tiles)} 个 tiles")

    # 拼接
    print("拼接 tiles...")
    panorama = stitch_tiles_with_blend(tiles)
    if not panorama:
        print("错误: 拼接失败")
        return None

    print(f"  拼接完成: {panorama.width}x{panorama.height}")

    # 缩放到目标高度
    if panorama.height != target_height:
        ratio = target_height / panorama.height
        new_width = int(panorama.width * ratio)
        panorama = panorama.resize((new_width, target_height), Image.Resampling.LANCZOS)
        print(f"  缩放完成: {panorama.width}x{panorama.height}")

    # 保存
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    panorama.save(output_path)
    print(f"全景图已保存: {output_path}")

    return str(output_path)


# ============================================================
# 裁切区域计算
# ============================================================


def auto_calculate_crop_regions(
    panorama_width: int,
    output_width: int,
    num_shots: int
) -> list:
    """自动计算均匀分布的裁切区域

    Args:
        panorama_width: 全景图宽度
        output_width: 输出宽度（每个镜头）
        num_shots: 镜头数

    Returns:
        裁切区域列表 [{"x": int, "y": 0, "width": int, "height": int}, ...]
    """
    if num_shots <= 1:
        # 单镜头，居中
        x = max(0, (panorama_width - output_width) // 2)
        return [{"x": x, "y": 0, "width": output_width, "height": None}]

    # 可平移范围
    pan_range = panorama_width - output_width
    if pan_range <= 0:
        # 全景图不够宽，所有镜头使用相同区域
        return [{"x": 0, "y": 0, "width": output_width, "height": None}] * num_shots

    # 均匀分布
    step = pan_range / (num_shots - 1)
    regions = []
    for i in range(num_shots):
        x = int(i * step)
        regions.append({
            "x": x,
            "y": 0,
            "width": output_width,
            "height": None  # 使用全高度
        })

    return regions


def preview_crop_regions(
    panorama_path: str,
    num_shots: int,
    output_width: int = DEFAULT_OUTPUT_WIDTH,
    output_path: Optional[str] = None
) -> str:
    """预览裁切区域

    Args:
        panorama_path: 全景图路径
        num_shots: 镜头数
        output_width: 输出宽度
        output_path: 预览图保存路径（可选）

    Returns:
        预览图路径
    """
    panorama = Image.open(panorama_path)
    print(f"全景图尺寸: {panorama.width}x{panorama.height}")

    # 计算裁切区域
    regions = auto_calculate_crop_regions(panorama.width, output_width, num_shots)

    # 创建预览图（在全景图上绘制裁切区域）
    from PIL import ImageDraw, ImageFont

    preview = panorama.copy()
    draw = ImageDraw.Draw(preview)

    colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF"]

    for i, region in enumerate(regions):
        color = colors[i % len(colors)]
        x, y, w = region["x"], region["y"], region["width"]
        h = panorama.height

        # 绘制矩形边框
        draw.rectangle([x, y, x + w, h], outline=color, width=5)

        # 绘制编号
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        except:
            font = ImageFont.load_default()

        label = f"Shot {i + 1}"
        draw.text((x + 20, y + 20), label, fill=color, font=font)

        print(f"  Shot {i + 1}: x={x}, width={w}")

    # 保存预览图
    if output_path is None:
        output_path = str(Path(panorama_path).with_suffix('.preview.png'))

    preview.save(output_path)
    print(f"预览图已保存: {output_path}")

    return output_path


def crop_shot_from_panorama(
    panorama_path: str,
    crop_region: dict,
    output_path: str
) -> str:
    """从全景图裁切单个镜头

    Args:
        panorama_path: 全景图路径
        crop_region: 裁切区域 {"x", "y", "width", "height"}
        output_path: 输出路径

    Returns:
        输出文件路径
    """
    panorama = Image.open(panorama_path)

    x = crop_region["x"]
    y = crop_region.get("y", 0)
    w = crop_region["width"]
    h = crop_region.get("height") or panorama.height

    # 裁切
    cropped = panorama.crop((x, y, x + w, y + h))

    # 保存
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(output_path)

    return str(output_path)


# ============================================================
# FFmpeg Pan 视频生成
# ============================================================


def generate_pan_video(
    panorama_path: str,
    start_x: int,
    end_x: int,
    duration: float,
    output_path: str,
    output_width: int = DEFAULT_OUTPUT_WIDTH,
    output_height: int = DEFAULT_OUTPUT_HEIGHT,
    fps: int = 30
) -> Optional[str]:
    """生成 pan 视频

    Args:
        panorama_path: 全景图路径
        start_x: 起始 x 坐标
        end_x: 结束 x 坐标
        duration: 持续时间（秒）
        output_path: 输出路径
        output_width: 输出宽度
        output_height: 输出高度
        fps: 帧率

    Returns:
        输出文件路径，失败返回 None
    """
    delta_x = end_x - start_x

    # 构建 FFmpeg 命令
    # crop=w:h:x:y，其中 x 使用表达式实现动画
    crop_expr = f"crop={output_width}:{output_height}:{start_x}+{delta_x}*t/{duration}:0"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", panorama_path,
        "-vf", crop_expr,
        "-t", str(duration),
        "-r", str(fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_path
    ]

    print(f"生成 pan 视频...")
    print(f"  从 x={start_x} 到 x={end_x}")
    print(f"  持续时间: {duration}s")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg 错误: {result.stderr}")
            return None

        print(f"视频已保存: {output_path}")
        return output_path

    except FileNotFoundError:
        print("错误: 未找到 ffmpeg，请先安装: brew install ffmpeg")
        return None
    except Exception as e:
        print(f"错误: {e}")
        return None


def generate_pan_video_from_direction(
    panorama_path: str,
    direction: str,
    duration: float,
    output_path: str,
    output_width: int = DEFAULT_OUTPUT_WIDTH,
    output_height: int = DEFAULT_OUTPUT_HEIGHT
) -> Optional[str]:
    """根据方向生成 pan 视频

    Args:
        panorama_path: 全景图路径
        direction: 方向 ("left_to_right", "right_to_left")
        duration: 持续时间
        output_path: 输出路径
        output_width: 输出宽度
        output_height: 输出高度

    Returns:
        输出文件路径
    """
    panorama = Image.open(panorama_path)
    pan_range = panorama.width - output_width

    if pan_range <= 0:
        print("警告: 全景图宽度不足以进行 pan")
        # 生成静态视频
        start_x = 0
        end_x = 0
    elif direction == "left_to_right":
        start_x = 0
        end_x = pan_range
    elif direction == "right_to_left":
        start_x = pan_range
        end_x = 0
    else:
        print(f"未知方向: {direction}，使用 left_to_right")
        start_x = 0
        end_x = pan_range

    return generate_pan_video(
        panorama_path,
        start_x,
        end_x,
        duration,
        output_path,
        output_width,
        output_height
    )


def generate_static_video(
    panorama_path: str,
    crop_region: dict,
    duration: float,
    output_path: str,
    fps: int = 30
) -> Optional[str]:
    """生成静态视频（固定裁切区域）

    Args:
        panorama_path: 全景图路径
        crop_region: 裁切区域
        duration: 持续时间
        output_path: 输出路径
        fps: 帧率

    Returns:
        输出文件路径
    """
    x = crop_region["x"]
    y = crop_region.get("y", 0)
    w = crop_region["width"]
    h = crop_region.get("height", DEFAULT_OUTPUT_HEIGHT)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", panorama_path,
        "-vf", f"crop={w}:{h}:{x}:{y}",
        "-t", str(duration),
        "-r", str(fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_path
    ]

    print(f"生成静态视频...")
    print(f"  裁切区域: x={x}, y={y}, w={w}, h={h}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg 错误: {result.stderr}")
            return None

        print(f"视频已保存: {output_path}")
        return output_path

    except FileNotFoundError:
        print("错误: 未找到 ffmpeg")
        return None


# ============================================================
# CLI
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="全景背景 + 裁切 Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 生成全景背景
  python solutions/panorama_demo.py \\
      --prompt "anime style, peaceful village with mountains" \\
      --num-shots 4 \\
      --output output/test_panorama.png

  # 预览裁切区域
  python solutions/panorama_demo.py \\
      --panorama output/test_panorama.png \\
      --preview-crops 4

  # 生成 pan 视频
  python solutions/panorama_demo.py \\
      --panorama output/test_panorama.png \\
      --pan left_to_right \\
      --duration 5 \\
      --output output/test_pan.mp4

  # 裁切单个镜头
  python solutions/panorama_demo.py \\
      --panorama output/test_panorama.png \\
      --crop "0,0,1920,1080" \\
      --output output/shot_1.png
"""
    )

    # 全景图生成选项
    parser.add_argument("--prompt", type=str, help="场景描述（生成全景图时使用）")
    parser.add_argument("--num-shots", type=int, default=4, help="计划的镜头数（决定全景图宽度）")

    # 全景图输入选项
    parser.add_argument("--panorama", type=str, help="已有的全景图路径（用于裁切/视频生成）")

    # 裁切预览选项
    parser.add_argument("--preview-crops", type=int, help="预览裁切区域（指定镜头数）")

    # 裁切选项
    parser.add_argument("--crop", type=str, help="裁切区域 (x,y,w,h)")

    # 视频生成选项
    parser.add_argument("--pan", type=str, choices=["left_to_right", "right_to_left"],
                       help="生成 pan 视频的方向")
    parser.add_argument("--duration", type=float, default=5.0, help="视频持续时间（秒）")

    # 通用选项
    parser.add_argument("--output", "-o", type=str, help="输出文件路径")
    parser.add_argument("--output-width", type=int, default=DEFAULT_OUTPUT_WIDTH,
                       help=f"输出宽度（默认 {DEFAULT_OUTPUT_WIDTH}）")
    parser.add_argument("--output-height", type=int, default=DEFAULT_OUTPUT_HEIGHT,
                       help=f"输出高度（默认 {DEFAULT_OUTPUT_HEIGHT}）")

    args = parser.parse_args()

    # 根据参数决定操作
    if args.prompt:
        # 模式 1: 生成全景图
        if not args.output:
            args.output = "output/panorama.png"

        client = setup_client()
        generate_panorama(
            client,
            args.prompt,
            args.num_shots,
            args.output,
            target_height=args.output_height
        )

    elif args.panorama and args.preview_crops:
        # 模式 2: 预览裁切区域
        preview_crop_regions(
            args.panorama,
            args.preview_crops,
            args.output_width,
            args.output
        )

    elif args.panorama and args.crop:
        # 模式 3: 裁切单个镜头
        if not args.output:
            args.output = "output/cropped.png"

        parts = [int(x) for x in args.crop.split(",")]
        crop_region = {
            "x": parts[0],
            "y": parts[1] if len(parts) > 1 else 0,
            "width": parts[2] if len(parts) > 2 else args.output_width,
            "height": parts[3] if len(parts) > 3 else args.output_height
        }

        crop_shot_from_panorama(args.panorama, crop_region, args.output)

    elif args.panorama and args.pan:
        # 模式 4: 生成 pan 视频
        if not args.output:
            args.output = "output/pan_video.mp4"

        generate_pan_video_from_direction(
            args.panorama,
            args.pan,
            args.duration,
            args.output,
            args.output_width,
            args.output_height
        )

    else:
        parser.print_help()
        print("\n请指定操作模式：")
        print("  --prompt: 生成全景图")
        print("  --panorama + --preview-crops: 预览裁切区域")
        print("  --panorama + --crop: 裁切单个镜头")
        print("  --panorama + --pan: 生成 pan 视频")


if __name__ == "__main__":
    main()
