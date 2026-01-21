#!/usr/bin/env python3
"""
AI 漫剧生成 - 视频合并脚本
使用 ffmpeg 将所有场景视频合并成完整漫剧

使用方法:
1. 确保已安装 ffmpeg: brew install ffmpeg (macOS) 或 apt install ffmpeg (Linux)
2. 确保已运行视频生成脚本
3. 运行脚本: python .claude/scripts/manga_concat.py

参数:
  --transition: 转场效果 (none/crossfade/fade)，默认 crossfade
  --transition-duration: 转场时长（秒），默认 0.5
"""

import argparse
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

from manga_common import (
    load_screenplay,
    get_output_dir_from_screenplay,
    get_all_shots,
    is_new_format,
    print_header,
)

# 转场效果类型
TRANSITION_TYPES = ["none", "crossfade", "fade"]
DEFAULT_TRANSITION = "crossfade"
DEFAULT_TRANSITION_DURATION = 0.5


def check_ffmpeg():
    """检查 ffmpeg 是否可用"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            capture_output=True,
            text=True
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def concat_videos_simple(video_paths: list, output_path: str):
    """使用 ffmpeg 直接合并视频（无转场）"""
    print(f"  正在合并 {len(video_paths)} 个视频（无转场）...")

    # 创建临时文件列表
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in video_paths:
            # ffmpeg concat 需要特殊格式
            f.write(f"file '{Path(path).absolute()}'\n")
        list_file = f.name

    try:
        # 使用 ffmpeg concat demuxer 合并视频
        cmd = [
            "ffmpeg",
            "-y",  # 覆盖输出文件
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",  # 直接复制流，不重新编码
            output_path
        ]

        print(f"  执行命令: {' '.join(cmd[:6])}...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"  ffmpeg 错误: {result.stderr}")
            return False

        return True

    finally:
        # 清理临时文件
        Path(list_file).unlink(missing_ok=True)


def concat_videos_with_crossfade(video_paths: list, output_path: str, transition_duration: float = 0.5):
    """使用 ffmpeg xfade 滤镜合并视频（交叉淡入淡出）"""
    print(f"  正在合并 {len(video_paths)} 个视频（crossfade 转场，{transition_duration}秒）...")

    if len(video_paths) < 2:
        return concat_videos_simple(video_paths, output_path)

    # 获取每个视频的时长
    durations = []
    for path in video_paths:
        duration = get_video_duration(path)
        durations.append(duration)
        print(f"    {Path(path).name}: {duration:.2f}s")

    # 构建 ffmpeg 复杂滤镜
    # 输入
    inputs = []
    for path in video_paths:
        inputs.extend(["-i", str(Path(path).absolute())])

    # 构建 xfade 滤镜链
    filter_parts = []
    n = len(video_paths)

    # 计算每个转场的偏移时间
    # offset = 前面所有视频时长之和 - 前面转场时长之和 - 当前转场时长
    current_offset = 0

    for i in range(n - 1):
        if i == 0:
            # 第一个转场: [0:v][1:v]xfade
            input_a = "[0:v]"
            input_b = "[1:v]"
        else:
            # 后续转场: [vN][i+1:v]xfade
            input_a = f"[v{i}]"
            input_b = f"[{i+1}:v]"

        # 计算偏移量
        offset = current_offset + durations[i] - transition_duration

        if i < n - 2:
            output = f"[v{i+1}]"
        else:
            output = "[vout]"

        filter_parts.append(
            f"{input_a}{input_b}xfade=transition=fade:duration={transition_duration}:offset={offset:.3f}{output}"
        )

        current_offset = offset

    # 音频处理：使用 acrossfade
    audio_parts = []
    for i in range(n - 1):
        if i == 0:
            input_a = "[0:a]"
            input_b = "[1:a]"
        else:
            input_a = f"[a{i}]"
            input_b = f"[{i+1}:a]"

        if i < n - 2:
            output = f"[a{i+1}]"
        else:
            output = "[aout]"

        audio_parts.append(
            f"{input_a}{input_b}acrossfade=d={transition_duration}:c1=tri:c2=tri{output}"
        )

    # 组合滤镜
    filter_complex = ";".join(filter_parts + audio_parts)

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path
    ]

    print(f"  执行 ffmpeg（xfade 滤镜）...")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"  ffmpeg 错误: {result.stderr[:500]}")
        # 回退到简单合并
        print("  回退到无转场合并...")
        return concat_videos_simple(video_paths, output_path)

    return True


def concat_videos_with_fade(video_paths: list, output_path: str, transition_duration: float = 0.5, output_dir: Path = None):
    """使用 ffmpeg 合并视频，每个视频之间淡入淡出到黑色"""
    print(f"  正在合并 {len(video_paths)} 个视频（fade 转场，{transition_duration}秒）...")

    if len(video_paths) < 2:
        return concat_videos_simple(video_paths, output_path)

    # 为每个视频添加淡入淡出效果
    temp_files = []
    half_duration = transition_duration / 2

    # 使用传入的输出目录或输出路径所在目录
    temp_dir = output_dir if output_dir else Path(output_path).parent

    for i, path in enumerate(video_paths):
        duration = get_video_duration(path)
        temp_file = temp_dir / f"_temp_fade_{i:02d}.mp4"
        temp_files.append(str(temp_file))

        # 淡入淡出滤镜
        fade_in = f"fade=t=in:st=0:d={half_duration}"
        fade_out = f"fade=t=out:st={duration - half_duration}:d={half_duration}"
        afade_in = f"afade=t=in:st=0:d={half_duration}"
        afade_out = f"afade=t=out:st={duration - half_duration}:d={half_duration}"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(Path(path).absolute()),
            "-vf", f"{fade_in},{fade_out}",
            "-af", f"{afade_in},{afade_out}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            str(temp_file)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  处理 {path} 失败: {result.stderr[:200]}")
            # 清理临时文件
            for tf in temp_files:
                Path(tf).unlink(missing_ok=True)
            return concat_videos_simple(video_paths, output_path)

    # 合并处理后的视频
    success = concat_videos_simple(temp_files, output_path)

    # 清理临时文件
    for tf in temp_files:
        Path(tf).unlink(missing_ok=True)

    return success


def concat_videos(video_paths: list, output_path: str, transition: str = "crossfade", transition_duration: float = 0.5, output_dir: Path = None):
    """合并视频，支持多种转场效果"""
    if transition == "none":
        return concat_videos_simple(video_paths, output_path)
    elif transition == "crossfade":
        return concat_videos_with_crossfade(video_paths, output_path, transition_duration)
    elif transition == "fade":
        return concat_videos_with_fade(video_paths, output_path, transition_duration, output_dir)
    else:
        print(f"  未知转场类型: {transition}，使用 crossfade")
        return concat_videos_with_crossfade(video_paths, output_path, transition_duration)


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="AI 漫剧 - 视频合并")
    parser.add_argument(
        "--transition",
        choices=TRANSITION_TYPES,
        default=DEFAULT_TRANSITION,
        help=f"转场效果类型 (默认: {DEFAULT_TRANSITION})"
    )
    parser.add_argument(
        "--transition-duration",
        type=float,
        default=DEFAULT_TRANSITION_DURATION,
        help=f"转场时长（秒）(默认: {DEFAULT_TRANSITION_DURATION})"
    )
    args = parser.parse_args()

    print_header("AI 漫剧 - 视频合并")

    # 检查 ffmpeg
    if not check_ffmpeg():
        print("错误: 未找到 ffmpeg")
        print("请安装 ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: apt install ffmpeg")
        print("  Windows: https://ffmpeg.org/download.html")
        exit(1)

    print("ffmpeg 已就绪")
    print(f"转场效果: {args.transition}")
    print(f"转场时长: {args.transition_duration} 秒")

    # 加载剧本
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)
    title = screenplay.get("title", "未命名")

    print(f"\n剧本: {title}")
    print(f"输出目录: {output_dir}")

    # 收集已生成的视频（支持新旧两种格式）
    video_paths = []
    missing_videos = []

    if is_new_format(screenplay):
        # 新格式: sequences with shots
        shots = get_all_shots(screenplay)
        total_count = len(shots)
        print(f"格式: sequences (细粒度分镜)")
        print(f"总镜头数: {total_count}")

        for shot in shots:
            shot_id = shot.get("shot_id", "?")
            video_path = shot.get("video_path")

            if video_path and Path(video_path).exists():
                video_paths.append(video_path)
                duration = get_video_duration(video_path)
                print(f"  镜头 {shot_id}: {video_path} ({duration:.1f}s)")
            else:
                missing_videos.append(shot_id)
    else:
        # 旧格式: scenes
        scenes = screenplay.get("scenes", [])
        total_count = len(scenes)
        print(f"格式: scenes (传统格式)")
        print(f"场景数: {total_count}")

        for scene in scenes:
            scene_id = scene.get("scene_id", 0)
            video_path = scene.get("video_path")

            if video_path and Path(video_path).exists():
                video_paths.append(video_path)
                duration = get_video_duration(video_path)
                print(f"  场景 {scene_id}: {video_path} ({duration:.1f}s)")
            else:
                missing_videos.append(scene_id)

    if missing_videos:
        print(f"\n警告: 以下场景/镜头缺少视频: {missing_videos}")
        print("请先运行: python .claude/scripts/manga_generate_videos.py")

    if not video_paths:
        print("\n错误: 没有可用的视频文件")
        exit(1)

    if len(video_paths) < total_count:
        print(f"\n将合并 {len(video_paths)}/{total_count} 个视频")
        response = input("是否继续? (y/n): ")
        if response.lower() != "y":
            print("已取消")
            exit(0)

    # 生成输出文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
    safe_title = safe_title.replace(" ", "_")[:30]
    output_filename = f"{safe_title}_{timestamp}.mp4"
    output_path = output_dir / output_filename

    print(f"\n输出文件: {output_path}")

    # 合并视频
    if concat_videos(video_paths, str(output_path), args.transition, args.transition_duration, output_dir):
        print_header("合并完成")
        total_duration = get_video_duration(str(output_path))
        print(f"输出文件: {output_path}")
        print(f"总时长: {total_duration:.1f} 秒")
        print(f"包含场景: {len(video_paths)} 个")
        print(f"转场效果: {args.transition}")
    else:
        print("\n视频合并失败")
        exit(1)


if __name__ == "__main__":
    main()
