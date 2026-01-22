#!/usr/bin/env python3
"""
Manga Sync Video - 生成音视频同步的幻灯片视频

策略：每个场景（location）共用一段旁白，场景内的镜头平均分配时长。
这样确保每个场景结束时对应旁白刚好播完。
"""

import json
import os
import subprocess
import sys
from collections import defaultdict


def get_audio_duration(audio_path):
    """获取音频文件时长"""
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', audio_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def calculate_scene_durations(screenplay_path, audio_dir):
    """计算每个场景的总音频时长和每镜头时长"""
    with open(screenplay_path, 'r', encoding='utf-8') as f:
        screenplay = json.load(f)

    scenes = []
    for loc in screenplay['locations']:
        loc_id = loc['location_id']
        shots = loc['shots']
        shot_count = len(shots)

        # 计算该场景所有镜头的音频总时长
        total_audio_duration = 0
        shot_list = []
        for shot in shots:
            shot_id = shot['shot_id']
            audio_file = f"narration_{shot_id.replace('-', '-')}.mp3"
            audio_path = os.path.join(audio_dir, audio_file)

            if os.path.exists(audio_path):
                dur = get_audio_duration(audio_path)
                total_audio_duration += dur
                shot_list.append({
                    'shot_id': shot_id,
                    'audio_path': audio_path,
                    'audio_duration': dur,
                    'narration': shot.get('narration', '')
                })
            else:
                print(f"Warning: Audio file not found: {audio_path}")

        # 每镜头时长 = 场景总音频时长 / 场景镜头数
        duration_per_shot = total_audio_duration / shot_count if shot_count > 0 else 3.0

        scenes.append({
            'location_id': loc_id,
            'location_name': loc['name'],
            'shot_count': shot_count,
            'total_audio_duration': total_audio_duration,
            'duration_per_shot': duration_per_shot,
            'shots': shot_list
        })

    return scenes, screenplay


def generate_slideshow_video(scenes, output_dir, output_filename='slideshow_synced.mp4'):
    """使用 ffmpeg 生成带可变时长的幻灯片视频"""

    # 创建 ffmpeg 输入文件列表
    concat_list_path = os.path.join(output_dir, 'concat_synced.txt')

    # 使用绝对路径
    abs_output_dir = os.path.abspath(output_dir)

    with open(concat_list_path, 'w', encoding='utf-8') as f:
        for scene in scenes:
            duration = scene['duration_per_shot']
            for shot in scene['shots']:
                shot_id = shot['shot_id']
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
    """按顺序合并所有音频文件"""

    # 创建音频合并列表
    audio_list_path = os.path.join(output_dir, 'audio_concat_list.txt')

    with open(audio_list_path, 'w', encoding='utf-8') as f:
        for scene in scenes:
            for shot in scene['shots']:
                audio_path = os.path.abspath(shot['audio_path'])
                if os.path.exists(audio_path):
                    f.write(f"file '{audio_path}'\n")

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
    """生成 SRT 字幕文件"""
    output_path = os.path.join(output_dir, output_filename)

    current_time = 0.0
    subtitle_index = 1

    with open(output_path, 'w', encoding='utf-8') as f:
        for scene in scenes:
            duration = scene['duration_per_shot']
            for shot in scene['shots']:
                narration = shot.get('narration', '')
                if narration:
                    start_time = current_time
                    end_time = current_time + duration

                    # 格式化时间为 SRT 格式
                    start_str = format_srt_time(start_time)
                    end_str = format_srt_time(end_time)

                    f.write(f"{subtitle_index}\n")
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{narration}\n\n")

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
    print("\n" + "=" * 70)
    print("场景音频分析")
    print("=" * 70)
    print(f"{'场景':<20} {'镜头数':>8} {'音频总时长':>12} {'每镜头时长':>12}")
    print("-" * 70)

    total_shots = 0
    total_duration = 0

    for scene in scenes:
        print(f"{scene['location_name']:<20} {scene['shot_count']:>8} "
              f"{scene['total_audio_duration']:>10.2f}秒 "
              f"{scene['duration_per_shot']:>10.2f}秒")
        total_shots += scene['shot_count']
        total_duration += scene['total_audio_duration']

    print("-" * 70)
    print(f"{'总计':<20} {total_shots:>8} {total_duration:>10.2f}秒")
    print("=" * 70 + "\n")


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
