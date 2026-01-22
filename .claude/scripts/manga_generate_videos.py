#!/usr/bin/env python3
"""
AI 漫剧生成 - 视频生成脚本
基于已有图片为每个场景生成视频

使用方法:
1. 设置环境变量: export GEMINI_API_KEY="your-api-key"
2. 安装依赖: pip install google-genai pillow
3. 确保已运行图片生成脚本
4. 运行脚本: python scripts/manga_generate_videos.py

参数:
  --duration: 每个视频的时长（秒），范围 2-8 (默认: 3)
  --fps: 帧率 (默认: 24)
  --resolution: 分辨率 (默认: 1080p)
  --smooth-transition: 启用平滑过渡 (使用前一帧作为参考)
"""

import argparse
import time
from pathlib import Path

from manga_common import (
    VIDEO_MODEL,
    DEFAULT_FPS,
    DEFAULT_RESOLUTION,
    DEFAULT_VIDEO_DURATION,
    setup_client,
    load_screenplay,
    save_screenplay,
    get_output_dir_from_screenplay,
    get_location_shot_video_path,
    get_all_location_shots,
    print_header,
)


def print_scene_header(shot_id, total, narration=""):
    """打印镜头标题"""
    print(f"\n{'='*50}")
    print(f"镜头 {shot_id}")
    if narration:
        print(f"旁白: {narration[:30]}...")
    print(f"{'='*50}")


def load_image_for_veo(image_path: str):
    """加载图片并转换为 Veo API 所需的格式

    Args:
        image_path: 图片文件路径

    Returns:
        适合 Veo API 的图片对象
    """
    from google.genai import types
    import base64

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # 确定 MIME 类型
    if image_path.lower().endswith(".png"):
        mime_type = "image/png"
    elif image_path.lower().endswith((".jpg", ".jpeg")):
        mime_type = "image/jpeg"
    else:
        mime_type = "image/png"

    return types.Image(
        image_bytes=image_bytes,
        mime_type=mime_type
    )


def generate_video(client, prompt: str, image_path: str, scene_id: int, duration: int = 3, smooth_transition=False, output_dir: Path = None):
    """调用 Veo 视频生成 API

    Args:
        client: Gemini API 客户端
        prompt: 视频生成提示词
        image_path: 当前场景图片路径
        scene_id: 场景 ID
        duration: 视频时长（秒），范围 2-8
        smooth_transition: 是否启用平滑过渡
        output_dir: 输出目录

    Returns:
        生成的视频路径，失败返回 None
    """
    print(f"  正在生成视频 (时长: {duration}秒)...")

    try:
        # 加载图片为 Veo API 格式
        image = load_image_for_veo(image_path)

        # 构建提示词
        final_prompt = prompt
        if smooth_transition:
            final_prompt = f"{prompt}. Smooth transition from previous scene."

        # 构建生成配置
        from google.genai import types
        config = types.GenerateVideosConfig(
            duration_seconds=duration,
        )

        # 提交视频生成任务
        operation = client.models.generate_videos(
            model=VIDEO_MODEL,
            prompt=final_prompt,
            image=image,
            config=config,
        )

        # 轮询等待视频生成完成
        max_wait = 300  # 最长等待 5 分钟
        start_time = time.time()

        while not operation.done:
            elapsed = int(time.time() - start_time)
            if elapsed > max_wait:
                print("  视频生成超时")
                return None

            print(f"  视频生成中... 已等待 {elapsed} 秒")
            time.sleep(10)
            operation = client.operations.get(operation)

        # 下载视频
        video = operation.response.generated_videos[0]
        client.files.download(file=video.video)

        # 解析 scene_id 格式 "X-Y" 为 location_id 和 shot_index
        parts = str(scene_id).split("-")
        loc_id = int(parts[0])
        shot_idx = int(parts[1]) if len(parts) > 1 else 1
        video_path = get_location_shot_video_path(loc_id, shot_idx, output_dir)
        video.video.save(str(video_path))
        print(f"  视频已保存: {video_path}")
        return str(video_path)

    except Exception as e:
        print(f"  视频生成失败: {e}")
        return None


def generate_shot_video(client, shot: dict, duration: int, output_dir: Path, smooth_transition: bool = False):
    """为单个镜头生成视频

    Args:
        client: Gemini API 客户端
        shot: 镜头数据字典
        duration: 视频时长（秒）
        output_dir: 输出目录
        smooth_transition: 是否启用平滑过渡

    Returns:
        生成的视频路径，失败返回 None
    """
    shot_id = shot.get("shot_id")
    video_prompt = shot.get("video_prompt", "")
    image_path = shot.get("image_path")

    if not image_path or not Path(image_path).exists():
        print(f"  镜头 {shot_id} 缺少图片，跳过")
        return None

    if not video_prompt:
        print(f"  镜头 {shot_id} 没有视频提示词，跳过")
        return None

    print(f"  正在生成视频 (时长: {duration}秒)...")
    print(f"  使用图片: {image_path}")

    try:
        # 加载图片为 Veo API 格式
        image = load_image_for_veo(image_path)

        # 构建提示词
        final_prompt = video_prompt
        if smooth_transition:
            final_prompt = f"{video_prompt}. Smooth transition from previous scene."

        # 构建生成配置
        from google.genai import types
        config = types.GenerateVideosConfig(
            duration_seconds=duration,
        )

        # 提交视频生成任务
        operation = client.models.generate_videos(
            model=VIDEO_MODEL,
            prompt=final_prompt,
            image=image,
            config=config,
        )

        # 轮询等待视频生成完成
        max_wait = 300  # 最长等待 5 分钟
        start_time = time.time()

        while not operation.done:
            elapsed = int(time.time() - start_time)
            if elapsed > max_wait:
                print("  视频生成超时")
                return None

            print(f"  视频生成中... 已等待 {elapsed} 秒")
            time.sleep(10)
            operation = client.operations.get(operation)

        # 下载视频
        video = operation.response.generated_videos[0]
        client.files.download(file=video.video)

        # 解析 shot_id 格式 "X-Y" 为 location_id 和 shot_index
        parts = str(shot_id).split("-")
        loc_id = int(parts[0])
        shot_idx = int(parts[1]) if len(parts) > 1 else 1
        video_path = get_location_shot_video_path(loc_id, shot_idx, output_dir)
        video.video.save(str(video_path))
        print(f"  视频已保存: {video_path}")
        return str(video_path)

    except Exception as e:
        print(f"  视频生成失败: {e}")
        return None


def process_shots_videos(client, screenplay: dict, duration: int, output_dir: Path, smooth_transition: bool = False):
    """处理新格式的镜头视频生成

    Args:
        client: Gemini API 客户端
        screenplay: 剧本数据
        duration: 视频时长（秒）
        output_dir: 输出目录
        smooth_transition: 是否启用平滑过渡
    """
    shots = get_all_location_shots(screenplay)
    total_shots = len(shots)

    # 统计需要生成的镜头
    shots_to_generate = []
    shots_missing_image = []

    for shot in shots:
        shot_id = shot.get("shot_id")
        image_path = shot.get("image_path")
        video_path = shot.get("video_path")

        # 检查是否已有视频
        if video_path and Path(video_path).exists():
            print(f"  镜头 {shot_id} 视频已存在，跳过")
            continue

        # 检查是否有图片
        if not image_path or not Path(image_path).exists():
            shots_missing_image.append(shot_id)
            continue

        shots_to_generate.append(shot)

    if shots_missing_image:
        print(f"\n警告: 以下镜头缺少图片，无法生成视频: {shots_missing_image}")
        print("请先运行: python .claude/scripts/manga_generate_images.py")

    if not shots_to_generate:
        if shots_missing_image:
            print("\n没有可以生成视频的镜头（需要先生成图片）")
        else:
            print("\n所有镜头视频已存在，无需生成")
        return

    print(f"\n需要生成 {len(shots_to_generate)} 个镜头的视频")

    # 生成视频
    for shot in shots_to_generate:
        shot_id = shot.get("shot_id")
        seq_name = shot.get("sequence_name", "")
        narration = shot.get("narration", "")

        print(f"\n{'='*50}")
        print(f"镜头 {shot_id} [{seq_name}]")
        if narration:
            print(f"旁白: {narration[:50]}...")
        print("=" * 50)

        video_path = generate_shot_video(
            client,
            shot,
            duration,
            output_dir,
            smooth_transition=smooth_transition
        )

        if video_path:
            # 更新 screenplay 中的数据
            for seq in screenplay.get("sequences", []):
                for s in seq.get("shots", []):
                    if s.get("shot_id") == shot_id:
                        s["video_path"] = video_path
                        break

            # 每生成一个视频就保存
            save_screenplay(screenplay)

    # 输出统计
    videos_done = sum(
        1 for seq in screenplay.get("sequences", [])
        for s in seq.get("shots", [])
        if s.get("video_path")
    )
    print(f"\n视频: {videos_done}/{total_shots}")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="AI 漫剧 - 视频生成")
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        help=f"帧率 (默认: {DEFAULT_FPS})"
    )
    parser.add_argument(
        "--resolution",
        default=DEFAULT_RESOLUTION,
        help=f"分辨率 (默认: {DEFAULT_RESOLUTION})"
    )
    parser.add_argument(
        "--smooth-transition",
        action="store_true",
        help="启用平滑过渡 (使用前一帧作为参考)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_VIDEO_DURATION,
        help=f"每个视频的时长（秒），范围 2-8 (默认: {DEFAULT_VIDEO_DURATION})"
    )
    args = parser.parse_args()

    # 验证时长参数
    if args.duration < 2 or args.duration > 8:
        print(f"警告: 时长 {args.duration} 秒超出范围 (2-8)，已调整为 {max(2, min(8, args.duration))} 秒")
        args.duration = max(2, min(8, args.duration))

    print_header("AI 漫剧 - 视频生成")

    # 初始化
    client = setup_client()
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)

    title = screenplay.get("title", "未命名")

    # 获取所有镜头
    all_shots = get_all_location_shots(screenplay)
    total_shots = len(all_shots)

    print(f"\n剧本: {title}")
    print(f"视频时长: {args.duration} 秒/镜头")
    print(f"帧率: {args.fps} FPS")
    print(f"分辨率: {args.resolution}")
    print(f"平滑过渡: {'启用' if args.smooth_transition else '禁用'}")
    print(f"输出目录: {output_dir.absolute()}")
    print(f"总镜头数: {total_shots}")

    # 处理所有镜头的视频生成
    process_shots_videos(
        client,
        screenplay,
        args.duration,
        output_dir,
        smooth_transition=args.smooth_transition
    )

    # 输出统计
    print_header("视频生成完成")
    videos_done = sum(
        1 for loc in screenplay.get("locations", [])
        for s in loc.get("shots", [])
        if s.get("video_path")
    )
    print(f"视频: {videos_done}/{total_shots}")

    print(f"\n下一步: 运行 python .claude/scripts/manga_concat.py 合并视频")


if __name__ == "__main__":
    main()
