#!/usr/bin/env python3
"""
Manga Sync Video - 生成音视频同步的幻灯片视频

策略改进（估算优先工作流）：
1. 优先使用 screenplay 中的 display_duration 字段（已根据实际音频时长校正）
2. 如果有 audio_manifest.json，使用清单中的精确时长
3. 支持旁白组（多图共享一段旁白）

这样确保每个镜头的显示时间与对应旁白完全同步。
"""

import json
import os
import subprocess
import sys
from collections import defaultdict

from manga_common import remove_rhythm_markers


def get_audio_duration(audio_path):
    """获取音频文件时长"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', audio_path],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def load_audio_manifest(audio_dir):
    """加载音频清单

    Args:
        audio_dir: 音频目录

    Returns:
        清单数据，如果不存在返回 None
    """
    manifest_path = os.path.join(audio_dir, "audio_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def get_shot_duration(shot: dict, manifest: dict = None, audio_dir: str = None) -> float:
    """获取镜头显示时长

    优先级：
    1. display_duration（已校正的显示时长）
    2. actual_duration（实际音频时长）
    3. estimated_duration（估算时长）
    4. 从清单中查找
    5. 从音频文件获取
    6. 默认值

    Args:
        shot: 镜头数据
        manifest: 音频清单（可选）
        audio_dir: 音频目录（可选）

    Returns:
        时长（秒）
    """
    # 1. 优先使用 display_duration
    if shot.get("display_duration"):
        return shot["display_duration"]

    # 2. 使用 actual_duration
    if shot.get("actual_duration"):
        return shot["actual_duration"]

    # 3. 使用 estimated_duration
    if shot.get("estimated_duration"):
        return shot["estimated_duration"]

    shot_id = shot["shot_id"]

    # 4. 从清单中查找
    if manifest:
        for entry in manifest.get("entries", []):
            if entry["type"] == "single" and entry["id"] == shot_id:
                return entry["duration"]
            elif entry["type"] == "group" and shot_id in entry.get("shots", []):
                return entry["per_shot_duration"]

    # 5. 从音频文件获取
    if audio_dir:
        audio_file = f"narration_{shot_id}.mp3"
        audio_path = os.path.join(audio_dir, audio_file)
        if os.path.exists(audio_path):
            return get_audio_duration(audio_path)

    # 6. 默认值
    return 3.0


def calculate_scene_durations(screenplay_path, audio_dir):
    """计算每个场景的音频时长和每镜头显示时长

    使用估算优先工作流：优先从 screenplay 获取已校正的时长
    """
    with open(screenplay_path, 'r', encoding='utf-8') as f:
        screenplay = json.load(f)

    # 尝试加载音频清单
    manifest = load_audio_manifest(audio_dir)
    if manifest:
        print(f"已加载音频清单: {manifest.get('total_duration', 0):.1f}秒 总时长")

    scenes = []
    for loc in screenplay['locations']:
        loc_id = loc['location_id']
        shots = loc['shots']
        shot_count = len(shots)

        total_audio_duration = 0
        shot_list = []

        for shot in shots:
            shot_id = shot['shot_id']

            # 使用优先级获取时长
            duration = get_shot_duration(shot, manifest, audio_dir)
            total_audio_duration += duration

            # 确定音频文件路径
            narration_group = shot.get("narration_group")
            if narration_group:
                audio_file = f"narration_group_{narration_group}.mp3"
            else:
                audio_file = f"narration_{shot_id}.mp3"
            audio_path = os.path.join(audio_dir, audio_file)

            shot_list.append({
                'shot_id': shot_id,
                'audio_path': audio_path if os.path.exists(audio_path) else None,
                'display_duration': duration,
                'narration': shot.get('narration', ''),
                'narration_group': narration_group,
                'group_position': shot.get('group_position', 1),
                'group_total': shot.get('group_total', 1)
            })

        scenes.append({
            'location_id': loc_id,
            'location_name': loc['name'],
            'shot_count': shot_count,
            'total_audio_duration': total_audio_duration,
            'shots': shot_list
        })

    return scenes, screenplay


def generate_slideshow_video(scenes, output_dir, output_filename='slideshow_synced.mp4'):
    """使用 ffmpeg 生成带可变时长的幻灯片视频

    使用每个镜头的 display_duration 精确控制显示时间。
    """

    # 创建 ffmpeg 输入文件列表
    concat_list_path = os.path.join(output_dir, 'concat_synced.txt')

    # 使用绝对路径
    abs_output_dir = os.path.abspath(output_dir)

    with open(concat_list_path, 'w', encoding='utf-8') as f:
        for scene in scenes:
            for shot in scene['shots']:
                shot_id = shot['shot_id']
                # 使用每个镜头的精确显示时长
                duration = shot.get('display_duration', 3.0)

                # 将 shot_id 格式 "1-1" 转换为文件名格式 "1_1"
                shot_file = f"shot_{shot_id.replace('-', '_')}.png"
                shot_path = os.path.join(abs_output_dir, shot_file)

                if os.path.exists(shot_path):
                    # ffmpeg concat demuxer 格式
                    f.write(f"file '{shot_path}'\n")
                    f.write(f"duration {duration:.3f}\n")
                else:
                    print(f"Warning: Shot image not found: {shot_path}")

    # 添加最后一帧（ffmpeg concat demuxer 需要）
    with open(concat_list_path, 'a', encoding='utf-8') as f:
        # 重复最后一帧
        last_scene = scenes[-1]
        last_shot = last_scene['shots'][-1]
        shot_id = last_shot['shot_id']
        shot_file = f"shot_{shot_id.replace('-', '_')}.png"
        shot_path = os.path.join(abs_output_dir, shot_file)
        f.write(f"file '{shot_path}'\n")

    output_path = os.path.join(output_dir, output_filename)

    # 使用 ffmpeg 生成视频
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_list_path,
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-r', '30',
        output_path
    ]

    print(f"Generating slideshow video: {output_path}")
    subprocess.run(cmd, check=True)

    return output_path


def merge_audio_files(scenes, output_dir, output_filename='merged_narration_synced.mp3'):
    """按顺序合并所有音频文件

    支持旁白组：组内只合并一次音频，避免重复。
    """

    # 创建音频合并列表
    audio_list_path = os.path.join(output_dir, 'audio_concat_list.txt')
    processed_groups = set()

    with open(audio_list_path, 'w', encoding='utf-8') as f:
        for scene in scenes:
            for shot in scene['shots']:
                narration_group = shot.get('narration_group')

                # 处理旁白组
                if narration_group:
                    if narration_group in processed_groups:
                        # 已处理过的组，跳过
                        continue
                    processed_groups.add(narration_group)

                audio_path = shot.get('audio_path')
                if audio_path and os.path.exists(audio_path):
                    abs_audio_path = os.path.abspath(audio_path)
                    f.write(f"file '{abs_audio_path}'\n")

    output_path = os.path.join(output_dir, output_filename)

    # 使用 ffmpeg 合并音频
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', audio_list_path,
        '-c:a', 'libmp3lame',
        '-b:a', '192k',
        output_path
    ]

    print(f"Merging audio files: {output_path}")
    subprocess.run(cmd, check=True)

    return output_path


def combine_video_audio(video_path, audio_path, output_path):
    """将视频和音频合并"""
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_path
    ]

    print(f"Combining video and audio: {output_path}")
    subprocess.run(cmd, check=True)

    return output_path


def generate_subtitles(scenes, output_dir, output_filename='subtitles_synced.srt'):
    """生成 SRT 字幕文件

    使用每个镜头的 display_duration 精确定位字幕时间。
    支持旁白组（多图共享一段旁白）。
    """
    output_path = os.path.join(output_dir, output_filename)

    current_time = 0.0
    subtitle_index = 1
    processed_groups = set()

    with open(output_path, 'w', encoding='utf-8') as f:
        for scene in scenes:
            for shot in scene['shots']:
                duration = shot.get('display_duration', 3.0)
                narration = shot.get('narration', '')
                narration_group = shot.get('narration_group')

                # 处理旁白组
                if narration_group:
                    if narration_group in processed_groups:
                        # 已处理过的组，只更新时间，不输出字幕
                        current_time += duration
                        continue

                    # 第一次遇到组，输出字幕，时长为整个组的总时长
                    group_total = shot.get('group_total', 1)
                    group_duration = duration * group_total
                    processed_groups.add(narration_group)

                    if narration:
                        start_time = current_time
                        end_time = current_time + group_duration

                        start_str = format_srt_time(start_time)
                        end_str = format_srt_time(end_time)

                        # 移除节奏标记，只保留纯文字
                        clean_narration = remove_rhythm_markers(narration)

                        f.write(f"{subtitle_index}\n")
                        f.write(f"{start_str} --> {end_str}\n")
                        f.write(f"{clean_narration}\n\n")

                        subtitle_index += 1

                    current_time += duration
                    continue

                # 独立旁白
                if narration:
                    start_time = current_time
                    end_time = current_time + duration

                    # 格式化时间为 SRT 格式
                    start_str = format_srt_time(start_time)
                    end_str = format_srt_time(end_time)

                    # 移除节奏标记，只保留纯文字
                    clean_narration = remove_rhythm_markers(narration)

                    f.write(f"{subtitle_index}\n")
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{clean_narration}\n\n")

                    subtitle_index += 1

                current_time += duration

    print(f"Generated subtitles: {output_path}")
    return output_path


def format_srt_time(seconds):
    """将秒转换为 SRT 时间格式 HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def add_subtitles(video_path, subtitle_path, output_path):
    """将字幕烧录到视频中"""
    # 使用 subtitles filter 烧录字幕
    # 需要使用绝对路径并转义特殊字符
    abs_subtitle_path = os.path.abspath(subtitle_path)
    escaped_subtitle_path = abs_subtitle_path.replace(':', r'\:').replace("'", r"\'")

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', f"subtitles='{escaped_subtitle_path}':force_style='FontSize=24,FontName=PingFang SC,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=1'",
        '-c:v', 'libx264',
        '-c:a', 'copy',
        output_path
    ]

    print(f"Adding subtitles: {output_path}")
    subprocess.run(cmd, check=True)

    return output_path


def print_scene_analysis(scenes):
    """打印场景分析表"""
    print("\n" + "=" * 80)
    print("场景音频分析（使用精确时长）")
    print("=" * 80)
    print(f"{'场景':<20} {'镜头数':>8} {'总时长':>12} {'时长范围':>20}")
    print("-" * 80)

    total_shots = 0
    total_duration = 0

    for scene in scenes:
        shot_durations = [s.get('display_duration', 0) for s in scene['shots']]
        min_dur = min(shot_durations) if shot_durations else 0
        max_dur = max(shot_durations) if shot_durations else 0
        duration_range = f"{min_dur:.2f}s - {max_dur:.2f}s"

        print(f"{scene['location_name']:<20} {scene['shot_count']:>8} "
              f"{scene['total_audio_duration']:>10.2f}秒 "
              f"{duration_range:>20}")
        total_shots += scene['shot_count']
        total_duration += scene['total_audio_duration']

    print("-" * 80)
    print(f"{'总计':<20} {total_shots:>8} {total_duration:>10.2f}秒")
    print(f"预计视频时长: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)")
    print("=" * 80 + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python manga_sync_video.py <output_dir>")
        print("Example: python manga_sync_video.py output/初心之雷")
        sys.exit(1)

    output_dir = sys.argv[1]
    screenplay_path = os.path.join(output_dir, 'screenplay.json')
    audio_dir = os.path.join(output_dir, 'audio')

    if not os.path.exists(screenplay_path):
        print(f"Error: Screenplay not found: {screenplay_path}")
        sys.exit(1)

    if not os.path.exists(audio_dir):
        print(f"Error: Audio directory not found: {audio_dir}")
        sys.exit(1)

    # 1. 计算场景时长
    print("Step 1: Analyzing scene durations...")
    scenes, screenplay = calculate_scene_durations(screenplay_path, audio_dir)
    print_scene_analysis(scenes)

    # 2. 生成幻灯片视频（可变时长）
    print("Step 2: Generating slideshow video with variable durations...")
    slideshow_path = generate_slideshow_video(scenes, output_dir, 'slideshow_synced.mp4')

    # 3. 合并音频文件
    print("Step 3: Merging audio files...")
    merged_audio_path = merge_audio_files(scenes, output_dir, 'merged_narration_synced.mp3')

    # 4. 合并视频和音频
    print("Step 4: Combining video and audio...")
    video_with_audio_path = os.path.join(output_dir, f"{screenplay['title']}_同步版.mp4")
    combine_video_audio(slideshow_path, merged_audio_path, video_with_audio_path)

    # 5. 生成字幕文件
    print("Step 5: Generating subtitles...")
    subtitle_path = generate_subtitles(scenes, output_dir, 'subtitles_synced_new.srt')

    # 6. 烧录字幕
    print("Step 6: Adding hardcoded subtitles...")
    final_output_path = os.path.join(output_dir, f"{screenplay['title']}_最终版.mp4")
    add_subtitles(video_with_audio_path, subtitle_path, final_output_path)

    print("\n" + "=" * 70)
    print("完成！")
    print(f"最终视频: {final_output_path}")
    print("=" * 70)

    # 获取最终视频时长
    final_duration = get_audio_duration(final_output_path)
    print(f"视频总时长: {final_duration:.2f}秒")


if __name__ == '__main__':
    main()
