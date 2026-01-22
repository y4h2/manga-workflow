#!/usr/bin/env python3
"""
AI 漫剧生成 - 视差滚动视频生成
基于分层背景创建带视差效果的视频

使用方法:
python solutions/parallax_video.py --location 1 --duration 5

参数:
  --location N: 场景 ID (必需)
  --duration N: 视频时长秒数 (默认 5)
  --direction: 滚动方向 left/right (默认 right)
  --output: 输出文件路径 (可选)

依赖: ffmpeg 命令行工具
  macOS: brew install ffmpeg
  Ubuntu: apt install ffmpeg

视差效果说明:
- 远景层滚动最慢 (20px/s)
- 中景层滚动中等 (60px/s)
- 近景层滚动最快 (120px/s)
这种速度差异创造出画面的深度感。
"""

import argparse
import subprocess
import sys
from pathlib import Path

# 添加 .claude/scripts 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "scripts"))

from manga_common import (
    load_screenplay,
    get_output_dir_from_screenplay,
    print_header,
    get_layered_background_paths,
    get_parallax_video_path,
    has_depth_layers,
)


def check_ffmpeg():
    """检查 ffmpeg 是否可用"""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def create_parallax_video(
    far_layer: str,
    mid_layer: str,
    near_layer: str,
    output_path: str,
    duration: int = 5,
    direction: str = "right"
) -> bool:
    """使用 ffmpeg 创建视差滚动视频

    Args:
        far_layer: 远景层路径
        mid_layer: 中景层路径
        near_layer: 近景层路径
        output_path: 输出视频路径
        duration: 视频时长 (秒)
        direction: 滚动方向 (left/right)

    Returns:
        是否成功
    """
    # 速度配置 (像素/秒)
    far_speed = 20
    mid_speed = 60
    near_speed = 120

    if direction == "left":
        far_speed = -far_speed
        mid_speed = -mid_speed
        near_speed = -near_speed

    # 计算所需的图片扩展宽度
    # 视频宽度 1920，滚动距离 = speed * duration
    far_total = 1920 + abs(far_speed) * duration
    mid_total = 1920 + abs(mid_speed) * duration
    near_total = 1920 + abs(near_speed) * duration

    # ffmpeg 滤镜链
    # 1. 缩放图片到足够宽以支持滚动
    # 2. 使用 crop 滤镜模拟滚动效果
    # 3. 叠加各层

    # 为了简化，使用固定的缩放比例
    scale_far = f"scale={int(far_total)}:-1"
    scale_mid = f"scale={int(mid_total)}:-1"
    scale_near = f"scale={int(near_total)}:-1"

    # 计算起始位置
    far_start = 0 if direction == "right" else abs(far_speed) * duration
    mid_start = 0 if direction == "right" else abs(mid_speed) * duration
    near_start = 0 if direction == "right" else abs(near_speed) * duration

    filter_complex = f"""
[0:v]loop=loop=-1:size=1:start=0,setpts=N/30/TB,{scale_far},format=rgba[far];
[1:v]loop=loop=-1:size=1:start=0,setpts=N/30/TB,{scale_mid},format=rgba[mid];
[2:v]loop=loop=-1:size=1:start=0,setpts=N/30/TB,{scale_near},format=rgba[near];
[far]crop=1920:1080:{far_start}+{abs(far_speed)}*t:0[far_scroll];
[mid]crop=1920:1080:{mid_start}+{abs(mid_speed)}*t:0[mid_scroll];
[near]crop=1920:1080:{near_start}+{abs(near_speed)}*t:0[near_scroll];
[far_scroll][mid_scroll]overlay=format=auto[tmp];
[tmp][near_scroll]overlay=format=auto[out]
"""

    cmd = [
        "ffmpeg", "-y",
        "-i", far_layer,
        "-i", mid_layer,
        "-i", near_layer,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        output_path
    ]

    print(f"执行 ffmpeg 命令...")
    print(f"  远景速度: {far_speed} px/s")
    print(f"  中景速度: {mid_speed} px/s")
    print(f"  近景速度: {near_speed} px/s")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"错误: {result.stderr}")
            return False

        print(f"视频已保存: {output_path}")
        return True

    except Exception as e:
        print(f"执行失败: {e}")
        return False


def create_simple_parallax_video(
    far_layer: str,
    mid_layer: str,
    near_layer: str,
    output_path: str,
    duration: int = 5,
    direction: str = "right"
) -> bool:
    """创建简化版视差视频（使用更简单的滤镜）

    当复杂滤镜失败时使用此版本。
    """
    # 使用更简单的方法：先合成静态图，然后添加简单的缩放动画
    # 这不是真正的视差，但可以作为备选方案

    print("使用简化版视差效果...")

    # 先合成静态背景
    from PIL import Image
    from manga_common import composite_layers

    far = Image.open(far_layer)
    mid = Image.open(mid_layer)
    near = Image.open(near_layer)

    composite = composite_layers(far, mid, near)

    # 保存临时合成图
    temp_path = output_path.replace(".mp4", "_temp.png")
    composite.save(temp_path)

    # 使用简单的缩放动画模拟视差
    zoom_speed = 0.002  # 每帧放大比例

    filter_complex = f"""
[0:v]loop=loop=-1:size=1:start=0,setpts=N/30/TB,
scale=1920:1080,
zoompan=z='1+{zoom_speed}*in':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={duration*30}:s=1920x1080:fps=30
[out]
"""

    cmd = [
        "ffmpeg", "-y",
        "-i", temp_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        # 删除临时文件
        Path(temp_path).unlink(missing_ok=True)

        if result.returncode != 0:
            print(f"错误: {result.stderr}")
            return False

        print(f"视频已保存: {output_path}")
        return True

    except Exception as e:
        print(f"执行失败: {e}")
        Path(temp_path).unlink(missing_ok=True)
        return False


def main():
    parser = argparse.ArgumentParser(description="AI 漫剧 - 视差滚动视频")
    parser.add_argument("--location", type=int, required=True, help="场景 ID")
    parser.add_argument("--duration", type=int, default=5, help="视频时长 (秒)")
    parser.add_argument("--direction", choices=["left", "right"], default="right", help="滚动方向")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    parser.add_argument("--simple", action="store_true", help="使用简化版视差效果")
    args = parser.parse_args()

    print_header("AI 漫剧 - 视差滚动视频")

    # 检查 ffmpeg
    if not check_ffmpeg():
        print("错误: 未找到 ffmpeg")
        print("请安装 ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu: apt install ffmpeg")
        return

    # 加载剧本
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)

    # 查找场景
    locations = screenplay.get("locations", [])
    location = next((l for l in locations if l.get("location_id") == args.location), None)

    if not location:
        print(f"错误: 找不到场景 {args.location}")
        return

    # 检查分层文件
    if not has_depth_layers(location):
        # 尝试从默认路径查找
        paths = get_layered_background_paths(args.location, output_dir)
        if not all(p.exists() for p in [paths["far"], paths["mid"], paths["near"]]):
            print(f"错误: 场景 {args.location} 没有分层背景")
            print("请先运行 layered_background_c2.py 或 layered_background_c4.py 生成分层")
            return
        far = str(paths["far"])
        mid = str(paths["mid"])
        near = str(paths["near"])
    else:
        layers = location["depth_layers"]
        far = layers["far_layer"]
        mid = layers["mid_layer"]
        near = layers["near_layer"]

    print(f"\n场景 {args.location}: {location.get('name', '未知')}")
    print(f"远景层: {far}")
    print(f"中景层: {mid}")
    print(f"近景层: {near}")
    print(f"时长: {args.duration}s")
    print(f"方向: {args.direction}")

    # 输出路径
    if args.output:
        output_path = args.output
    else:
        output_path = str(get_parallax_video_path(args.location, output_dir))

    # 生成视差视频
    if args.simple:
        success = create_simple_parallax_video(far, mid, near, output_path, args.duration, args.direction)
    else:
        success = create_parallax_video(far, mid, near, output_path, args.duration, args.direction)

    if success:
        print_header("视差视频生成完成")
        print(f"\n播放视频: open {output_path}")
    else:
        print("\n视差视频生成失败")
        if not args.simple:
            print("尝试使用 --simple 参数运行简化版本")


if __name__ == "__main__":
    main()
