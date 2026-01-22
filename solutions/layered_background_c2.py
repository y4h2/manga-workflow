#!/usr/bin/env python3
"""
AI 漫剧生成 - 方案 C2: 深度估计自动分层
使用 MiDaS 深度估计模型将单张背景图分割为多个深度层

使用方法:
1. 安装依赖: pip install torch transformers pillow numpy scipy
2. 确保已有背景图 (阶段 1.5 生成)
3. 运行脚本: python solutions/layered_background_c2.py

参数:
  --location N: 只处理指定场景
  --num-layers N: 分层数量 (默认 3: far/mid/near)
  --force: 强制重新处理所有场景

本方案使用深度估计模型自动分析背景图的深度信息，
然后根据深度将图片分割为多个层次，支持后续的视差滚动效果。
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# 添加 .claude/scripts 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "scripts"))

from manga_common import (
    load_screenplay,
    save_screenplay,
    get_output_dir_from_screenplay,
    print_header,
    is_location_format,
    get_layered_background_paths,
)


def load_depth_model():
    """加载 MiDaS 深度估计模型

    Returns:
        (processor, model, device) 元组
    """
    try:
        import torch
        from transformers import DPTForDepthEstimation, DPTImageProcessor
    except ImportError:
        print("错误: 请安装依赖: pip install torch transformers")
        sys.exit(1)

    print("正在加载深度估计模型...")
    model_name = "Intel/dpt-large"
    processor = DPTImageProcessor.from_pretrained(model_name)
    model = DPTForDepthEstimation.from_pretrained(model_name)

    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    model = model.to(device)
    model.eval()

    print(f"模型已加载，使用设备: {device}")
    return processor, model, device


def estimate_depth(image: Image.Image, processor, model, device) -> np.ndarray:
    """估计图像深度

    Args:
        image: PIL 图像
        processor: DPT 处理器
        model: DPT 模型
        device: 计算设备

    Returns:
        深度图 (numpy array, 0-1 范围, 1=最近)
    """
    import torch

    # 预处理
    inputs = processor(images=image, return_tensors="pt").to(device)

    # 推理
    with torch.no_grad():
        outputs = model(**inputs)
        predicted_depth = outputs.predicted_depth

    # 后处理
    depth = predicted_depth.squeeze().cpu().numpy()

    # 归一化到 0-1
    depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)

    # 调整尺寸匹配原图
    depth_img = Image.fromarray((depth * 255).astype(np.uint8))
    depth_img = depth_img.resize(image.size, Image.BILINEAR)
    depth = np.array(depth_img) / 255.0

    return depth


def split_by_depth(image: Image.Image, depth: np.ndarray, num_layers: int = 3) -> list:
    """根据深度图分割图像为多层

    Args:
        image: 原始图像
        depth: 深度图 (0-1)
        num_layers: 分层数量

    Returns:
        [(layer_name, layer_image), ...] 从远到近
    """
    try:
        from scipy.ndimage import gaussian_filter
    except ImportError:
        print("错误: 请安装依赖: pip install scipy")
        sys.exit(1)

    img_array = np.array(image.convert("RGBA"))

    # 计算深度阈值
    thresholds = np.linspace(0, 1, num_layers + 1)

    layers = []
    layer_names = ["far", "mid", "near"] if num_layers == 3 else [f"layer_{i}" for i in range(num_layers)]

    for i in range(num_layers):
        low, high = thresholds[i], thresholds[i + 1]

        # 创建该深度范围的 mask
        mask = ((depth >= low) & (depth < high)).astype(np.float32)

        # 边缘羽化
        mask = gaussian_filter(mask, sigma=3)

        # 应用 mask (保留该深度范围的像素)
        layer = img_array.copy()
        layer[:, :, 3] = (mask * 255).astype(np.uint8)

        # 转为 PIL Image
        layer_img = Image.fromarray(layer, "RGBA")
        layers.append((layer_names[i], layer_img))

    return layers


def process_location(location: dict, output_dir: Path, processor, model, device, num_layers: int = 3, force: bool = False):
    """处理单个场景的背景图分层

    Args:
        location: 场景数据
        output_dir: 输出目录
        processor: DPT 处理器
        model: DPT 模型
        device: 计算设备
        num_layers: 分层数量
        force: 是否强制重新处理

    Returns:
        分层结果字典，失败返回 None
    """
    loc_id = location.get("location_id", 0)
    bg_path = location.get("background_image")

    if not bg_path or not Path(bg_path).exists():
        print(f"  场景 {loc_id} 没有背景图，跳过")
        return None

    # 检查是否已处理
    paths = get_layered_background_paths(loc_id, output_dir)
    if not force and all(p.exists() for p in [paths["far"], paths["mid"], paths["near"]]):
        print(f"  场景 {loc_id} 分层已存在，跳过")
        return None

    print(f"\n处理场景 {loc_id}...")

    # 加载背景图
    image = Image.open(bg_path).convert("RGB")
    print(f"  加载背景图: {bg_path}")

    # 估计深度
    print("  估计深度...")
    depth = estimate_depth(image, processor, model, device)

    # 保存深度图
    depth_path = paths["depth"]
    depth_img = Image.fromarray((depth * 255).astype(np.uint8))
    depth_img.save(depth_path)
    print(f"  深度图已保存: {depth_path}")

    # 分割为多层
    print(f"  分割为 {num_layers} 层...")
    layers = split_by_depth(image, depth, num_layers)

    # 保存各层
    layer_paths = {"depth_image": str(depth_path)}
    for layer_name, layer_img in layers:
        layer_path = paths.get(layer_name, output_dir / f"loc_{loc_id:02d}_{layer_name}.png")
        layer_img.save(str(layer_path))
        layer_paths[f"{layer_name}_layer"] = str(layer_path)
        print(f"  {layer_name} 层已保存: {layer_path}")

    return {
        "enabled": True,
        **layer_paths
    }


def main():
    parser = argparse.ArgumentParser(description="AI 漫剧 - 深度分层提取 (方案 C2)")
    parser.add_argument("--location", type=int, default=None, help="只处理指定场景")
    parser.add_argument("--num-layers", type=int, default=3, help="分层数量 (默认 3)")
    parser.add_argument("--force", action="store_true", help="强制重新处理所有场景")
    args = parser.parse_args()

    print_header("AI 漫剧 - 深度分层提取 (方案 C2)")

    # 加载剧本
    screenplay = load_screenplay()
    output_dir = get_output_dir_from_screenplay(screenplay)

    if not is_location_format(screenplay):
        print("错误: 当前剧本不是 locations 格式")
        return

    # 加载模型
    processor, model, device = load_depth_model()

    # 处理场景
    locations = screenplay.get("locations", [])
    processed_count = 0

    for location in locations:
        loc_id = location.get("location_id", 0)

        if args.location is not None and loc_id != args.location:
            continue

        result = process_location(location, output_dir, processor, model, device, args.num_layers, args.force)

        if result:
            location["depth_layers"] = result
            save_screenplay(screenplay)
            processed_count += 1

    print_header("深度分层提取完成 (方案 C2)")
    print(f"\n处理了 {processed_count} 个场景")

    if processed_count > 0:
        print("\n分层文件说明:")
        print("  - loc_XX_depth.png: 深度图（灰度）")
        print("  - loc_XX_far.png: 远景层（带透明）")
        print("  - loc_XX_mid.png: 中景层（带透明）")
        print("  - loc_XX_near.png: 近景层（带透明）")
        print("\n可以使用 parallax_video.py 生成视差滚动视频")


if __name__ == "__main__":
    main()
