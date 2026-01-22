#!/usr/bin/env python3
"""
AI 漫剧生成 - DepthFlow 视差视频集成
使用 DepthFlow 库创建高质量 2.5D 视差动画

DepthFlow 特点:
- 像素级连续视差（非分层）
- 多种预设动画: dolly, zoom, circle, orbital, horizontal, vertical
- GPU 加速渲染
- 支持景深、暗角等后处理

安装依赖:
    pip install depthflow

使用方法:
    python solutions/depthflow_video.py --location 1 --animation dolly
    python solutions/depthflow_video.py --location 1 --animation circle --duration 5

参数:
    --location N: 场景 ID (必需)
    --animation: 动画类型 (dolly/zoom/circle/orbital/horizontal/vertical)
    --duration N: 视频时长秒数 (默认 5)
    --intensity: 动画强度 (默认 1.0)
    --output: 输出文件路径 (可选)
    --depth-model: 深度估计模型 (默认 depth-anything-v2)

动画类型说明:
    dolly      - 推拉镜头，像摄像机前后移动
    zoom       - 变焦效果，放大/缩小
    circle     - 环绕运动，围绕中心旋转
    orbital    - 轨道运动，像卫星绕地球
    horizontal - 水平平移
    vertical   - 垂直平移
"""

import argparse
import sys
from pathlib import Path

# 添加 .claude/scripts 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "scripts"))

from manga_common import (
    load_screenplay,
    get_output_dir_from_screenplay,
    print_header,
)


def check_depthflow():
    """检查 DepthFlow 是否可用"""
    try:
        from depthflow.scene import DepthScene
        return True
    except ImportError:
        return False


def get_animation_description(animation: str) -> str:
    """获取动画类型的描述"""
    descriptions = {
        "dolly": "推拉镜头 - 摄像机前后移动，产生景深变化",
        "zoom": "变焦效果 - 画面放大/缩小，焦点不变",
        "circle": "环绕运动 - 围绕画面中心旋转",
        "orbital": "轨道运动 - 像卫星绕地球，有倾斜角度",
        "horizontal": "水平平移 - 左右移动视角",
        "vertical": "垂直平移 - 上下移动视角",
    }
    return descriptions.get(animation, "未知动画")


def create_depthflow_video(
    input_image: str,
    output_path: str,
    animation: str = "dolly",
    duration: float = 5.0,
    intensity: float = 1.0,
    depth_model: str = "depth-anything-v2",
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> bool:
    """使用 DepthFlow 创建视差视频

    Args:
        input_image: 输入图片路径
        output_path: 输出视频路径
        animation: 动画类型
        duration: 时长秒数
        intensity: 动画强度 (0.5-2.0)
        depth_model: 深度估计模型
        width: 输出宽度
        height: 输出高度
        fps: 帧率

    Returns:
        是否成功
    """
    try:
        from depthflow.scene import DepthScene
    except ImportError:
        print("错误: 请安装 DepthFlow: pip install depthflow")
        return False

    print(f"动画类型: {animation} ({get_animation_description(animation)})")
    print(f"时长: {duration}s")
    print(f"强度: {intensity}")
    print(f"输出尺寸: {width}x{height}")
    print(f"帧率: {fps}fps")
    print()

    try:
        # 创建场景
        scene = DepthScene()

        # 设置渲染参数（使用正确的属性名）
        scene._width = width
        scene._height = height
        scene.fps = fps
        scene.duration = duration

        # 加载图片并估计深度
        print("加载图片并估计深度...")
        scene.input(image=input_image)

        # 应用动画
        print(f"应用 {animation} 动画...")
        _apply_animation(scene, animation, intensity, duration)

        # 渲染视频
        print("渲染视频...")
        scene.main(output=output_path)

        print(f"视频已保存: {output_path}")
        return True

    except Exception as e:
        print(f"DepthFlow API 渲染失败: {e}")
        print("\n尝试使用命令行方式...")
        return create_depthflow_video_cli(
            input_image, output_path, animation, duration, intensity, width, height, fps
        )


def _apply_animation(scene, animation: str, intensity: float, duration: float):
    """应用动画到场景

    Args:
        scene: DepthScene 实例
        animation: 动画类型
        intensity: 强度
        duration: 时长
    """
    # 根据动画类型设置不同的预设
    # 强度影响动画幅度
    amplitude = 0.3 * intensity

    if animation == "dolly":
        # 推拉镜头 - 调整 dolly 参数
        scene.dolly(amplitude=amplitude, cycles=1)
    elif animation == "zoom":
        # 变焦 - 调整 zoom 参数
        scene.zoom(amplitude=amplitude * 0.5, cycles=1)
    elif animation == "circle":
        # 环绕 - 调整 center 坐标做圆形运动
        scene.circle(amplitude=amplitude, cycles=1)
    elif animation == "orbital":
        # 轨道运动
        scene.orbital(amplitude=amplitude, cycles=1)
    elif animation == "horizontal":
        # 水平平移
        scene.horizontal(amplitude=amplitude, cycles=1)
    elif animation == "vertical":
        # 垂直平移
        scene.vertical(amplitude=amplitude, cycles=1)
    elif animation == "sine":
        # 正弦波动
        scene.sine(amplitude=amplitude, cycles=2)
    else:
        # 默认 dolly
        scene.dolly(amplitude=amplitude, cycles=1)


def create_depthflow_video_cli(
    input_image: str,
    output_path: str,
    animation: str = "dolly",
    duration: float = 5.0,
    intensity: float = 1.0,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> bool:
    """使用 DepthFlow CLI 创建视差视频

    DepthFlow CLI 使用链式子命令:
    python -m depthflow input -i IMAGE [ANIMATION] main -o OUTPUT -t TIME
    """
    import subprocess

    # 构建命令 - 使用正确的子命令结构
    # depthflow input -i IMAGE [animation] main -o OUTPUT -t TIME
    cmd = [
        sys.executable, "-m", "depthflow",
        "input", "-i", input_image,
    ]

    # 添加动画子命令
    cmd.append(animation)
    cmd.extend(["-i", str(intensity)])  # intensity 参数

    # 添加 main 子命令和渲染参数
    cmd.extend([
        "main",
        "-o", output_path,
        "-t", str(duration),
        "-w", str(width),
        "-h", str(height),
        "-f", str(fps),
        "--render",  # 强制渲染模式
    ])

    print(f"执行命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print(f"错误输出: {result.stderr[:1000] if result.stderr else 'None'}")
            print(f"标准输出: {result.stdout[:500] if result.stdout else 'None'}")
            return False

        # 检查文件是否存在
        if Path(output_path).exists():
            print(f"视频已保存: {output_path}")
            return True
        else:
            # 检查默认输出目录
            default_dir = Path.home() / "Library/Application Support/BrokenSource/DepthFlow/data"
            if default_dir.exists():
                recent_files = sorted(default_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)
                if recent_files:
                    print(f"视频保存在默认位置: {recent_files[0]}")
                    # 移动到指定位置
                    import shutil
                    shutil.move(str(recent_files[0]), output_path)
                    print(f"已移动到: {output_path}")
                    return True
            print("警告: 未找到生成的视频文件")
            return False

    except subprocess.TimeoutExpired:
        print("错误: 渲染超时 (超过5分钟)")
        return False
    except FileNotFoundError:
        print("错误: depthflow 命令未找到")
        return False
    except Exception as e:
        print(f"执行失败: {e}")
        return False


def create_depthflow_video_simple(
    input_image: str,
    output_path: str,
    animation: str = "dolly",
    duration: float = 5.0,
    intensity: float = 1.0,
) -> bool:
    """简化版 DepthFlow 视频生成（使用默认参数）"""
    return create_depthflow_video_cli(
        input_image,
        output_path,
        animation,
        duration,
        intensity,
        width=1920,
        height=1080,
        fps=30
    )


def main():
    parser = argparse.ArgumentParser(description="AI 漫剧 - DepthFlow 视差视频")
    parser.add_argument("--location", type=int, required=True, help="场景 ID")
    parser.add_argument(
        "--animation",
        choices=["dolly", "zoom", "circle", "orbital", "horizontal", "vertical"],
        default="dolly",
        help="动画类型 (dolly/zoom/circle/orbital/horizontal/vertical)"
    )
    parser.add_argument("--duration", type=float, default=5.0, help="视频时长 (秒)")
    parser.add_argument("--intensity", type=float, default=1.0, help="动画强度 (0.5-2.0)")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    parser.add_argument("--width", type=int, default=1920, help="输出宽度")
    parser.add_argument("--height", type=int, default=1080, help="输出高度")
    parser.add_argument("--fps", type=int, default=30, help="帧率")
    parser.add_argument("--depth-model", type=str, default="depth-anything-v2", help="深度模型")
    args = parser.parse_args()

    print_header("AI 漫剧 - DepthFlow 视差视频")

    # 检查 DepthFlow
    if not check_depthflow():
        print("警告: DepthFlow 未安装，将尝试命令行方式")
        print("安装方法: pip install depthflow")
        print()

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
        output_path = str(output_dir / f"loc_{args.location:02d}_depthflow.mp4")

    # 生成视频
    success = False

    # 尝试方法 1: Python API
    if check_depthflow():
        success = create_depthflow_video(
            str(bg_path),
            output_path,
            args.animation,
            args.duration,
            args.intensity,
            args.depth_model,
            args.width,
            args.height,
            args.fps
        )

    # 尝试方法 2: 命令行
    if not success:
        success = create_depthflow_video_simple(
            str(bg_path),
            output_path,
            args.animation,
            args.duration,
            args.intensity
        )

    if success:
        print_header("DepthFlow 视频生成完成")
        print(f"\n播放视频: open {output_path}")
    else:
        print("\nDepthFlow 视频生成失败")
        print("\n请确保已安装 DepthFlow:")
        print("  pip install depthflow")
        print("\n或使用 Ken Burns/C2+ 替代方案:")
        print(f"  python solutions/ken_burns_video.py --location {args.location}")
        print(f"  python solutions/parallax_video_improved.py --location {args.location} --generate-layers --generate-video")


if __name__ == "__main__":
    main()
