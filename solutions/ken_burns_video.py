#!/usr/bin/env python3
"""
AI 漫剧生成 - Ken Burns 视频效果
使用 FFmpeg zoompan 滤镜创建简单但稳定的动态视频

使用方法:
python solutions/ken_burns_video.py --location 1 --effect zoom_in
python solutions/ken_burns_video.py --location 1 --effect pan_right --duration 5

参数:
  --location N: 场景 ID (必需)
  --effect: 效果类型 (zoom_in/zoom_out/pan_left/pan_right/ken_burns)
  --duration N: 视频时长秒数 (默认 5)
  --zoom-factor: 缩放倍率 (默认 1.2)
  --output: 输出文件路径 (可选)

依赖: ffmpeg 命令行工具
  macOS: brew install ffmpeg

Ken Burns 效果说明:
这是最稳定的动态背景方案，对单张静态图应用缩放/平移动画。
虽然没有真正的视差深度感，但稳定性极高，适合快速预览和简单场景。
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
)


def check_ffmpeg():
    """检查 ffmpeg 是否可用"""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_zoompan_filter(effect: str, duration: int, zoom_factor: float, width: int = 1920, height: int = 1080, fps: int = 30) -> str:
    """生成 zoompan 滤镜表达式

    Args:
        effect: 效果类型
        duration: 时长秒数
        zoom_factor: 缩放倍率
        width: 输出宽度
        height: 输出高度
        fps: 帧率

    Returns:
        zoompan 滤镜字符串
    """
    frames = duration * fps

    # 计算每帧缩放增量
    zoom_per_frame = (zoom_factor - 1) / frames

    filters = {
        # 从中心放大
        "zoom_in": f"zoompan=z='1+{zoom_per_frame}*in':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}",

        # 从放大状态缩小到原始
        "zoom_out": f"zoompan=z='{zoom_factor}-{zoom_per_frame}*in':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}",

        # 向左平移（图像向右移动）
        "pan_left": f"zoompan=z='1.1':x='(iw*0.1)-((iw*0.1)/{frames})*in':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}",

        # 向右平移（图像向左移动）
        "pan_right": f"zoompan=z='1.1':x='((iw*0.1)/{frames})*in':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}",

        # 经典 Ken Burns（放大+平移）
        "ken_burns": f"zoompan=z='1+{zoom_per_frame*0.5}*in':x='((iw*0.1)/{frames})*in':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}",

        # 向上平移
        "pan_up": f"zoompan=z='1.1':x='iw/2-(iw/zoom/2)':y='(ih*0.1)-((ih*0.1)/{frames})*in':d={frames}:s={width}x{height}:fps={fps}",

        # 向下平移
        "pan_down": f"zoompan=z='1.1':x='iw/2-(iw/zoom/2)':y='((ih*0.1)/{frames})*in':d={frames}:s={width}x{height}:fps={fps}",
    }

    return filters.get(effect, filters["zoom_in"])


def create_ken_burns_video(
    input_image: str,
    output_path: str,
    effect: str = "zoom_in",
    duration: int = 5,
    zoom_factor: float = 1.2,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30
) -> bool:
    """创建 Ken Burns 效果视频

    Args:
        input_image: 输入图片路径
        output_path: 输出视频路径
        effect: 效果类型
        duration: 时长秒数
        zoom_factor: 缩放倍率
        width: 输出宽度
        height: 输出高度
        fps: 帧率

    Returns:
        是否成功
    """
    zoompan = get_zoompan_filter(effect, duration, zoom_factor, width, height, fps)

    # 构建 ffmpeg 命令
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", input_image,
        "-vf", zoompan,
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        output_path
    ]

    print(f"效果: {effect}")
    print(f"时长: {duration}s")
    print(f"缩放倍率: {zoom_factor}")
    print(f"输出尺寸: {width}x{height}")
    print(f"帧率: {fps}fps")
    print()

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


def main():
    parser = argparse.ArgumentParser(description="AI 漫剧 - Ken Burns 效果视频")
    parser.add_argument("--location", type=int, required=True, help="场景 ID")
    parser.add_argument("--effect", choices=["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "ken_burns"],
                       default="zoom_in", help="效果类型")
    parser.add_argument("--duration", type=int, default=5, help="视频时长 (秒)")
    parser.add_argument("--zoom-factor", type=float, default=1.2, help="缩放倍率")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    parser.add_argument("--width", type=int, default=1920, help="输出宽度")
    parser.add_argument("--height", type=int, default=1080, help="输出高度")
    parser.add_argument("--fps", type=int, default=30, help="帧率")
    args = parser.parse_args()

    print_header("AI 漫剧 - Ken Burns 效果视频")

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

    # 查找场景背景图
    bg_path = output_dir / f"loc_{args.location:02d}_bg.png"

    if not bg_path.exists():
        # 尝试从 locations 中获取
        locations = screenplay.get("locations", [])
        location = next((l for l in locations if l.get("location_id") == args.location), None)

        if location and location.get("background_image"):
            bg_path = Path(location["background_image"])
        else:
            print(f"错误: 找不到场景 {args.location} 的背景图")
            print(f"尝试路径: {output_dir / f'loc_{args.location:02d}_bg.png'}")
            return

    if not bg_path.exists():
        print(f"错误: 背景图不存在: {bg_path}")
        return

    print(f"场景 {args.location}")
    print(f"背景图: {bg_path}")
    print()

    # 输出路径
    if args.output:
        output_path = args.output
    else:
        output_path = str(output_dir / f"loc_{args.location:02d}_kenburns.mp4")

    # 生成视频
    success = create_ken_burns_video(
        str(bg_path),
        output_path,
        args.effect,
        args.duration,
        args.zoom_factor,
        args.width,
        args.height,
        args.fps
    )

    if success:
        print_header("Ken Burns 视频生成完成")
        print(f"\n播放视频: open {output_path}")
    else:
        print("\nKen Burns 视频生成失败")


if __name__ == "__main__":
    main()
