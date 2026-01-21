#!/usr/bin/env python3
"""
AI 漫剧生成 - 幻灯片视频生成脚本
将镜头图片拼接成幻灯片视频

使用方法:
1. 确保已安装 ffmpeg
2. 确保已有 screenplay.json 和镜头图片
3. 运行脚本: python .claude/scripts/manga_slideshow.py [选项]

选项:
  --duration N          每张图片显示时长（秒），默认 3
  --transition TYPE     转场效果: none/fade/crossfade，默认 none
  --transition-duration 转场时长（秒），默认 0.5
  --output FILENAME     输出文件名，默认自动生成
  --fps N               帧率，默认 24
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from manga_common import (
    load_screenplay,
    get_output_dir_from_screenplay,
    get_all_location_shots,
    print_header,
)


def check_ffmpeg():
    """检查 ffmpeg 是否安装"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_shot_images(screenplay: dict, output_dir: Path) -> list:
    """获取所有镜头图片路径（按顺序）

    Args:
        screenplay: 剧本数据
        output_dir: 输出目录

    Returns:
        图片路径列表
    """
    images = []

    for location in screenplay.get("locations", []):
        loc_id = location.get("location_id", 0)
        shots = location.get("shots", [])

        for i, shot in enumerate(shots):
            # 检查是否有已生成的图片路径
            image_path = shot.get("image_path")
            if image_path and Path(image_path).exists():
                images.append(image_path)
            else:
                # 尝试默认路径
                default_path = output_dir / f"shot_{loc_id}_{i+1}.png"
                if default_path.exists():
                    images.append(str(default_path))

    return images


def create_image_list(images: list, duration: float, output_dir: Path) -> Path:
    """创建 ffmpeg concat 格式的图片列表文件

    Args:
        images: 图片路径列表
        duration: 每张图片显示时长
        output_dir: 输出目录

    Returns:
        列表文件路径
    """
    list_path = output_dir / "slideshow_list.txt"

    with open(list_path, "w", encoding="utf-8") as f:
        for img in images:
            # 只使用文件名（因为我们会在 output_dir 中执行 ffmpeg）
            img_path = Path(img)
            filename = img_path.name
            f.write(f"file '{filename}'\n")
            f.write(f"duration {duration}\n")

        # 最后一张图片需要重复一次（ffmpeg concat 的要求）
        if images:
            last_img = Path(images[-1])
            f.write(f"file '{last_img.name}'\n")

    return list_path


def generate_slideshow_simple(
    images: list,
    output_path: Path,
    output_dir: Path,
    duration: float = 3,
    fps: int = 24
) -> bool:
    """生成简单幻灯片（无转场）

    Args:
        images: 图片路径列表
        output_path: 输出视频路径
        output_dir: 输出目录
        duration: 每张图片显示时长
        fps: 帧率

    Returns:
        是否成功
    """
    # 创建图片列表
    list_path = create_image_list(images, duration, output_dir)

    # 使用文件名（因为我们在 output_dir 中执行）
    list_filename = list_path.name
    output_filename = output_path.name

    # 构建 ffmpeg 命令
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_filename,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        output_filename
    ]

    print(f"  执行命令: ffmpeg -f concat ...")

    try:
        # 在输出目录中执行
        result = subprocess.run(
            cmd,
            cwd=str(output_dir.absolute()),
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"  ffmpeg 错误: {result.stderr[-500:]}")
            return False

        return True

    except Exception as e:
        print(f"  执行失败: {e}")
        return False


def generate_slideshow_with_fade(
    images: list,
    output_path: Path,
    output_dir: Path,
    duration: float = 3,
    fade_duration: float = 0.5,
    fps: int = 24
) -> bool:
    """生成带淡入淡出转场的幻灯片

    Args:
        images: 图片路径列表
        output_path: 输出视频路径
        output_dir: 输出目录
        duration: 每张图片显示时长
        fade_duration: 淡入淡出时长
        fps: 帧率

    Returns:
        是否成功
    """
    if not images:
        return False

    # 转换为绝对路径
    abs_images = [str(Path(img).absolute()) for img in images]

    # 构建复杂的 filter_complex
    # 每张图片: 缩放 -> 设置时长 -> 淡入淡出
    filter_parts = []
    concat_inputs = []

    for i, img in enumerate(abs_images):
        # 输入
        filter_parts.append(
            f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
            f"setpts=PTS-STARTPTS,"
            f"fps={fps},"
            f"trim=duration={duration},"
            f"fade=t=in:st=0:d={fade_duration},"
            f"fade=t=out:st={duration - fade_duration}:d={fade_duration}"
            f"[v{i}]"
        )
        concat_inputs.append(f"[v{i}]")

    # 拼接
    filter_parts.append(
        f"{''.join(concat_inputs)}concat=n={len(abs_images)}:v=1:a=0[outv]"
    )

    filter_complex = ";".join(filter_parts)

    # 构建输入参数（使用绝对路径）
    input_args = []
    for img in abs_images:
        input_args.extend(["-loop", "1", "-t", str(duration), "-i", img])

    # 构建完整命令
    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output_path.absolute())
    ]

    print(f"  执行命令: ffmpeg -filter_complex (fade) ...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"  ffmpeg 错误: {result.stderr[-500:]}")
            return False

        return True

    except Exception as e:
        print(f"  执行失败: {e}")
        return False


def generate_slideshow_with_crossfade(
    images: list,
    output_path: Path,
    output_dir: Path,
    duration: float = 3,
    crossfade_duration: float = 0.5,
    fps: int = 24
) -> bool:
    """生成带交叉淡化转场的幻灯片

    Args:
        images: 图片路径列表
        output_path: 输出视频路径
        output_dir: 输出目录
        duration: 每张图片显示时长
        crossfade_duration: 交叉淡化时长
        fps: 帧率

    Returns:
        是否成功
    """
    if not images:
        return False

    if len(images) == 1:
        # 只有一张图片，使用简单方式
        return generate_slideshow_simple(images, output_path, output_dir, duration, fps)

    # 转换为绝对路径
    abs_images = [str(Path(img).absolute()) for img in images]

    # 构建 xfade 滤镜链
    # 每对相邻图片之间添加 xfade
    filter_parts = []

    # 首先缩放所有输入
    for i in range(len(abs_images)):
        filter_parts.append(
            f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
            f"setpts=PTS-STARTPTS,"
            f"fps={fps},"
            f"trim=duration={duration},"
            f"setpts=PTS-STARTPTS[v{i}]"
        )

    # 构建 xfade 链
    # 第一对: [v0][v1]xfade -> [xf0]
    # 第二对: [xf0][v2]xfade -> [xf1]
    # ...
    effective_duration = duration - crossfade_duration
    offset = effective_duration

    if len(abs_images) == 2:
        filter_parts.append(
            f"[v0][v1]xfade=transition=fade:duration={crossfade_duration}:offset={offset}[outv]"
        )
    else:
        # 第一个 xfade
        filter_parts.append(
            f"[v0][v1]xfade=transition=fade:duration={crossfade_duration}:offset={offset}[xf0]"
        )

        # 中间的 xfade
        for i in range(2, len(abs_images) - 1):
            prev_offset = offset
            offset = prev_offset + effective_duration
            filter_parts.append(
                f"[xf{i-2}][v{i}]xfade=transition=fade:duration={crossfade_duration}:offset={offset}[xf{i-1}]"
            )

        # 最后一个 xfade
        if len(abs_images) > 2:
            prev_offset = offset
            offset = prev_offset + effective_duration
            filter_parts.append(
                f"[xf{len(abs_images)-3}][v{len(abs_images)-1}]xfade=transition=fade:duration={crossfade_duration}:offset={offset}[outv]"
            )

    filter_complex = ";".join(filter_parts)

    # 构建输入参数（使用绝对路径）
    input_args = []
    for img in abs_images:
        input_args.extend(["-loop", "1", "-t", str(duration), "-i", img])

    # 构建完整命令
    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output_path.absolute())
    ]

    print(f"  执行命令: ffmpeg -filter_complex (crossfade) ...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"  ffmpeg 错误: {result.stderr[-500:]}")
            return False

        return True

    except Exception as e:
        print(f"  执行失败: {e}")
        return False


def get_video_info(video_path: Path) -> dict:
    """获取视频信息

    Args:
        video_path: 视频路径

    Returns:
        视频信息字典
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_format", "-show_streams",
                str(video_path)
            ],
            capture_output=True,
            text=True
        )

        info = {}
        for line in result.stdout.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                if key in ["duration", "width", "height", "size", "bit_rate"]:
                    info[key] = value

        return info

    except Exception:
        return {}


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI 漫剧 - 幻灯片视频生成")
    parser.add_argument(
        "--duration",
        type=float,
        default=3,
        help="每张图片显示时长（秒），默认 3"
    )
    parser.add_argument(
        "--transition",
        choices=["none", "fade", "crossfade"],
        default="none",
        help="转场效果: none/fade/crossfade，默认 none"
    )
    parser.add_argument(
        "--transition-duration",
        type=float,
        default=0.5,
        help="转场时长（秒），默认 0.5"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出文件名，默认自动生成"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=24,
        help="帧率，默认 24"
    )
    args = parser.parse_args()

    print_header("AI 漫剧 - 幻灯片视频生成")

    # 检查 ffmpeg
    if not check_ffmpeg():
        print("\n错误: ffmpeg 未安装")
        print("\n请先安装 ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: apt install ffmpeg")
        print("  Windows: https://ffmpeg.org/download.html")
        sys.exit(1)

    print("  ffmpeg 已安装 ✓")

    # 加载剧本
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)
    title = screenplay.get("title", "未命名")

    print(f"\n剧本: {title}")
    print(f"输出目录: {output_dir.absolute()}")

    # 获取镜头图片
    images = get_shot_images(screenplay, output_dir)

    if not images:
        print("\n错误: 没有找到镜头图片")
        print("请先运行图片生成脚本:")
        print("  python .claude/scripts/manga_generate_images.py")
        sys.exit(1)

    print(f"\n找到 {len(images)} 张镜头图片")

    # 生成输出文件名
    if args.output:
        output_filename = args.output
        if not output_filename.endswith(".mp4"):
            output_filename += ".mp4"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transition_suffix = f"_{args.transition}" if args.transition != "none" else ""
        output_filename = f"{title}_幻灯片{transition_suffix}_{timestamp}.mp4"

    output_path = output_dir / output_filename

    print(f"\n生成参数:")
    print(f"  每张图片时长: {args.duration} 秒")
    print(f"  转场效果: {args.transition}")
    if args.transition != "none":
        print(f"  转场时长: {args.transition_duration} 秒")
    print(f"  帧率: {args.fps} fps")
    print(f"  输出文件: {output_path}")

    # 生成视频
    print("\n正在生成视频...")

    if args.transition == "none":
        success = generate_slideshow_simple(
            images, output_path, output_dir,
            duration=args.duration,
            fps=args.fps
        )
    elif args.transition == "fade":
        success = generate_slideshow_with_fade(
            images, output_path, output_dir,
            duration=args.duration,
            fade_duration=args.transition_duration,
            fps=args.fps
        )
    elif args.transition == "crossfade":
        success = generate_slideshow_with_crossfade(
            images, output_path, output_dir,
            duration=args.duration,
            crossfade_duration=args.transition_duration,
            fps=args.fps
        )
    else:
        success = False

    if not success:
        print("\n视频生成失败")
        sys.exit(1)

    # 获取视频信息
    info = get_video_info(output_path)

    print_header("幻灯片视频生成完成")

    print(f"\n输出文件: {output_path}")
    if info:
        if "width" in info and "height" in info:
            print(f"分辨率: {info['width']} x {info['height']}")
        if "duration" in info:
            duration_sec = float(info["duration"])
            minutes = int(duration_sec // 60)
            seconds = duration_sec % 60
            print(f"时长: {minutes}:{seconds:05.2f}")
        if "size" in info:
            size_mb = int(info["size"]) / (1024 * 1024)
            print(f"文件大小: {size_mb:.1f} MB")

    print(f"\n播放视频:")
    print(f"  open \"{output_path}\"")


if __name__ == "__main__":
    main()
