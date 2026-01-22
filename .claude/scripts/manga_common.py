#!/usr/bin/env python3
"""
AI 漫剧生成 - 共享模块
提供所有脚本共用的工具函数和常量

仅支持 locations 格式（场景化分镜）
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime

from google import genai

# 模型配置
IMAGE_MODEL = "gemini-3-pro-image-preview"
VIDEO_MODEL = "veo-3.1-generate-preview"

# 路径配置
SCREENPLAY_PATH = Path("screenplay.json")
OUTPUT_DIR = Path("output")

# 默认配置
DEFAULT_STYLE_KEYWORDS = "anime style, vibrant colors, detailed character design"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_SHOT_DURATION = 2  # 秒 (镜头时长)
DEFAULT_VIDEO_DURATION = 2  # 秒 (实际视频生成时长，2秒为宜)
DEFAULT_FPS = 24
DEFAULT_RESOLUTION = "1080p"

# 有效值
VALID_ASPECT_RATIOS = ["16:9", "9:16", "1:1"]

# 故事相关常量
STORY_OUTLINE_FILENAME = "story_outline.json"
VALID_BEAT_TYPES = ["setup", "inciting_incident", "rising_action", "climax", "resolution"]
VALID_MOODS = [
    "peaceful", "hopeful", "melancholic", "tense", "joyful", "mysterious",
    "horror", "romantic", "epic", "contemplative", "dramatic", "serene"
]

# 节奏类型定义
PACING_TYPES = {
    "slow": {
        "intensity_range": (0.0, 0.4),
        "shot_count_range": (2, 3),
        "duration_per_shot": (3, 4),
        "description": "开场、沉思、情感铺垫"
    },
    "moderate": {
        "intensity_range": (0.4, 0.7),
        "shot_count_range": (3, 4),
        "duration_per_shot": (2, 3),
        "description": "对话、发现、日常叙事"
    },
    "fast": {
        "intensity_range": (0.7, 1.0),
        "shot_count_range": (4, 6),
        "duration_per_shot": (1, 2),
        "description": "动作、追逐、高潮冲突"
    }
}

# 节拍类型到节奏类型的默认映射
BEAT_TYPE_PACING_MAP = {
    "setup": "slow",
    "inciting_incident": "moderate",
    "rising_action": "moderate",
    "climax": "fast",
    "resolution": "slow"
}

# 分层地图相关常量
WORLD_MAP_FILENAME = "world_map.png"
REGION_MAP_FILENAME_TEMPLATE = "region_{:02d}_map.png"

# 场景化分镜相关常量
VALID_TIME_OF_DAY = ["dawn", "morning", "noon", "afternoon", "dusk", "evening", "night", "midnight"]
VALID_SHOT_COMPOSITIONS = [
    "wide shot", "medium shot", "close-up", "extreme close-up",
    "POV shot", "establishing shot", "over-the-shoulder", "two-shot"
]


def setup_client():
    """初始化 genai 客户端"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("错误: 请设置环境变量 GEMINI_API_KEY")
        print("获取 API Key: https://aistudio.google.com/apikey")
        exit(1)
    return genai.Client(api_key=api_key)


def get_screenplay_path():
    """获取实际的剧本路径

    如果根目录的 screenplay.json 是项目引用文件（包含 project_path），
    则返回子目录中的实际剧本路径；否则返回根目录路径。
    """
    if not SCREENPLAY_PATH.exists():
        return SCREENPLAY_PATH

    with open(SCREENPLAY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 检查是否是项目引用文件
    if "project_path" in data and "locations" not in data:
        project_path = Path(data["project_path"])
        return project_path / "screenplay.json"

    return SCREENPLAY_PATH


def load_screenplay():
    """加载剧本 JSON

    支持两种模式：
    1. 根目录 screenplay.json 是完整剧本
    2. 根目录 screenplay.json 是项目引用，实际剧本在子目录中
    """
    screenplay_path = get_screenplay_path()

    if not screenplay_path.exists():
        print(f"错误: {screenplay_path} 文件不存在")
        print("请先运行 /manga 命令生成剧本")
        exit(1)

    with open(screenplay_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_screenplay(screenplay):
    """保存更新后的剧本

    根据 screenplay 中的 output_dir 字段决定保存位置。
    """
    # 如果有 output_dir，保存到子目录
    output_dir = screenplay.get("output_dir")
    if output_dir:
        screenplay_path = Path(output_dir) / "screenplay.json"
    else:
        screenplay_path = get_screenplay_path()

    with open(screenplay_path, "w", encoding="utf-8") as f:
        json.dump(screenplay, f, ensure_ascii=False, indent=2)
    print(f"剧本已更新: {screenplay_path}")


def ensure_output_dir():
    """确保输出目录存在"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR


def sanitize_folder_name(title: str) -> str:
    """将标题转换为安全的文件夹名称

    Args:
        title: 剧本标题

    Returns:
        安全的文件夹名称
    """
    # 移除或替换不安全的字符
    # 保留中文、英文、数字、下划线、连字符
    safe_name = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', title)
    # 移除连续的下划线
    safe_name = re.sub(r'_+', '_', safe_name)
    # 移除首尾的下划线
    safe_name = safe_name.strip('_')
    # 如果名称为空，使用时间戳
    if not safe_name:
        safe_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 限制长度
    if len(safe_name) > 50:
        safe_name = safe_name[:50]
    return safe_name


def create_output_subdir(title: str) -> Path:
    """根据标题创建输出子目录

    Args:
        title: 剧本标题

    Returns:
        子目录路径
    """
    folder_name = sanitize_folder_name(title)
    subdir = OUTPUT_DIR / folder_name
    subdir.mkdir(parents=True, exist_ok=True)
    return subdir


def get_output_dir_from_screenplay(screenplay: dict) -> Path:
    """从剧本中获取输出目录

    如果剧本中有 output_dir 字段，返回该路径；
    否则返回默认的 OUTPUT_DIR。

    Args:
        screenplay: 剧本数据

    Returns:
        输出目录路径
    """
    output_dir = screenplay.get("output_dir")
    if output_dir:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return ensure_output_dir()


def print_header(title: str):
    """打印标题"""
    print("=" * 60)
    print(title)
    print("=" * 60)


def get_style_keywords(screenplay: dict) -> str:
    """获取风格关键词，如果没有则返回默认值"""
    return screenplay.get("style_keywords", DEFAULT_STYLE_KEYWORDS)


def get_aspect_ratio(screenplay: dict) -> str:
    """获取画面比例"""
    return screenplay.get("aspect_ratio", DEFAULT_ASPECT_RATIO)


def build_enhanced_prompt(base_prompt: str, style_keywords: str) -> str:
    """构建增强的提示词，自动附加风格关键词

    Args:
        base_prompt: 原始提示词
        style_keywords: 风格关键词

    Returns:
        增强后的提示词
    """
    if not style_keywords:
        return base_prompt

    # 如果风格关键词已经在提示词中，不重复添加
    if style_keywords.lower() in base_prompt.lower():
        return base_prompt

    # 如果提示词已经以 "anime style" 开头且风格关键词包含 "anime style"
    # 只附加额外的风格关键词
    if base_prompt.lower().startswith("anime style") and "anime style" in style_keywords.lower():
        # 移除 style_keywords 中的 "anime style" 避免重复
        extra_keywords = style_keywords.lower().replace("anime style,", "").replace("anime style", "").strip()
        extra_keywords = extra_keywords.strip(", ")
        if extra_keywords:
            return f"{base_prompt}, {extra_keywords}"
        return base_prompt

    return f"{base_prompt}, {style_keywords}"


def get_total_duration(screenplay: dict) -> int:
    """计算总时长

    Args:
        screenplay: 剧本数据

    Returns:
        总时长（秒）
    """
    if "target_duration" in screenplay:
        return screenplay["target_duration"]

    return sum(
        shot.get("duration", DEFAULT_SHOT_DURATION)
        for loc in screenplay.get("locations", [])
        for shot in loc.get("shots", [])
    )


def is_location_format(screenplay: dict) -> bool:
    """检查是否是 locations 格式"""
    return "locations" in screenplay and len(screenplay.get("locations", [])) > 0


# ============================================================
# 故事大纲相关函数
# ============================================================


def get_story_outline_path(output_dir: Path = None) -> Path:
    """获取故事大纲路径

    Args:
        output_dir: 输出目录，如果为 None 则从 screenplay.json 获取
    """
    if output_dir:
        return Path(output_dir) / STORY_OUTLINE_FILENAME

    # 尝试从 screenplay.json 获取项目路径
    if SCREENPLAY_PATH.exists():
        with open(SCREENPLAY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "project_path" in data:
            return Path(data["project_path"]) / STORY_OUTLINE_FILENAME

    return OUTPUT_DIR / STORY_OUTLINE_FILENAME


def load_story_outline(output_dir: Path = None) -> dict:
    """加载故事大纲

    Args:
        output_dir: 输出目录，如果为 None 则自动检测

    Returns:
        故事大纲数据
    """
    story_path = get_story_outline_path(output_dir)

    if not story_path.exists():
        print(f"错误: 故事大纲文件不存在: {story_path}")
        print("请先运行阶段 0 生成故事大纲")
        exit(1)

    with open(story_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_story_outline(story: dict, output_dir: Path = None) -> Path:
    """保存故事大纲

    Args:
        story: 故事大纲数据
        output_dir: 输出目录

    Returns:
        保存路径
    """
    if output_dir is None:
        output_dir = story.get("output_dir")
        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    story_path = output_dir / STORY_OUTLINE_FILENAME
    with open(story_path, "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=2)

    print(f"故事大纲已保存: {story_path}")
    return story_path


def get_character_by_name(story: dict, name: str) -> dict:
    """根据名字获取角色信息

    Args:
        story: 故事大纲数据
        name: 角色名字

    Returns:
        角色信息字典，未找到返回空字典
    """
    for char in story.get("characters", []):
        if char.get("name") == name:
            return char
    return {}


def build_character_prompt(character: dict) -> str:
    """构建角色描述提示词

    Args:
        character: 角色信息字典

    Returns:
        用于图片生成的角色描述字符串
    """
    parts = []

    # 基本外观
    if character.get("appearance"):
        parts.append(character["appearance"])

    # 性格可以影响表情和姿态
    if character.get("personality"):
        personality = character["personality"]
        # 将性格转换为视觉描述
        personality_visual_map = {
            "勇敢": "confident posture",
            "机智": "alert expression",
            "温柔": "gentle expression",
            "冷酷": "cold gaze",
            "活泼": "energetic pose",
            "内向": "reserved demeanor",
        }
        for cn_trait, en_visual in personality_visual_map.items():
            if cn_trait in personality:
                parts.append(en_visual)
                break

    return ", ".join(parts) if parts else ""


def get_beat_by_id(story: dict, beat_id: int) -> dict:
    """根据 ID 获取故事节拍

    Args:
        story: 故事大纲数据
        beat_id: 节拍 ID

    Returns:
        节拍信息字典，未找到返回空字典
    """
    for beat in story.get("story_beats", []):
        if beat.get("beat_id") == beat_id:
            return beat
    return {}


def get_all_characters_prompt(story: dict, character_names: list = None) -> str:
    """获取所有（或指定）角色的外观提示词

    Args:
        story: 故事大纲数据
        character_names: 角色名字列表，None 表示所有角色

    Returns:
        合并的角色描述字符串
    """
    prompts = []
    for char in story.get("characters", []):
        if character_names is None or char.get("name") in character_names:
            prompt = build_character_prompt(char)
            if prompt:
                name = char.get("name", "character")
                prompts.append(f"{name}: {prompt}")

    return "; ".join(prompts) if prompts else ""


# ============================================================
# 场景化分镜相关函数
# ============================================================


def get_character_phase_path(character_name: str, phase_id: int, output_dir: Path = None) -> Path:
    """获取角色阶段参考图路径

    Args:
        character_name: 角色名称
        phase_id: 阶段 ID
        output_dir: 输出目录，如果为 None 则使用默认目录
    """
    base_dir = output_dir if output_dir else OUTPUT_DIR
    # 将中文名转换为安全文件名
    safe_name = sanitize_folder_name(character_name)
    return base_dir / f"char_{safe_name}_phase_{phase_id:02d}.png"


def get_location_background_path(location_id: int, output_dir: Path = None) -> Path:
    """获取场景背景图路径

    Args:
        location_id: 场景 ID
        output_dir: 输出目录，如果为 None 则使用默认目录
    """
    base_dir = output_dir if output_dir else OUTPUT_DIR
    return base_dir / f"loc_{location_id:02d}_bg.png"


def get_location_shot_path(location_id: int, shot_index: int, output_dir: Path = None) -> Path:
    """获取场景镜头图片路径

    Args:
        location_id: 场景 ID
        shot_index: 镜头索引（从 1 开始）
        output_dir: 输出目录，如果为 None 则使用默认目录
    """
    base_dir = output_dir if output_dir else OUTPUT_DIR
    return base_dir / f"shot_{location_id}_{shot_index}.png"


def get_location_shot_video_path(location_id: int, shot_index: int, output_dir: Path = None) -> Path:
    """获取场景镜头视频路径

    Args:
        location_id: 场景 ID
        shot_index: 镜头索引（从 1 开始）
        output_dir: 输出目录，如果为 None 则使用默认目录
    """
    base_dir = output_dir if output_dir else OUTPUT_DIR
    return base_dir / f"shot_{location_id}_{shot_index}.mp4"


def get_character_phase_for_beat(story: dict, character_name: str, beat_id: int) -> dict:
    """根据节拍 ID 获取角色对应的阶段信息

    Args:
        story: 故事大纲数据
        character_name: 角色名称
        beat_id: 节拍 ID

    Returns:
        阶段信息字典，未找到返回空字典
    """
    char = get_character_by_name(story, character_name)
    if not char:
        return {}

    phases = char.get("phases", [])
    for phase in phases:
        beat_range = phase.get("beat_range", [])
        if len(beat_range) >= 2:
            start, end = beat_range[0], beat_range[1]
            if start <= beat_id <= end:
                return phase

    # 如果没有定义 phases，返回空字典
    return {}


def get_location_for_beat(story: dict, beat_id: int) -> dict:
    """根据节拍 ID 获取对应的场景信息

    Args:
        story: 故事大纲数据
        beat_id: 节拍 ID

    Returns:
        场景信息字典，未找到返回空字典
    """
    for location in story.get("locations", []):
        if beat_id in location.get("beats", []):
            return location
    return {}


def build_phase_appearance_prompt(phase: dict, character: dict) -> str:
    """构建角色阶段外观提示词

    Args:
        phase: 阶段信息
        character: 角色信息

    Returns:
        外观描述字符串
    """
    if phase.get("appearance"):
        return phase["appearance"]

    # 如果阶段没有特定外观，使用角色基本外观
    return character.get("appearance", "")


def get_all_location_shots(screenplay: dict) -> list:
    """获取所有场景镜头的扁平列表，按顺序排列

    Args:
        screenplay: 剧本数据

    Returns:
        包含所有镜头的列表，每个镜头包含 location_id 和 shot 信息
    """
    shots = []
    for location in screenplay.get("locations", []):
        loc_id = location.get("location_id", 0)
        loc_name = location.get("name", f"Location {loc_id}")
        char_phase = location.get("character_phase", 1)

        for shot in location.get("shots", []):
            shot_copy = shot.copy()
            shot_copy["location_id"] = loc_id
            shot_copy["location_name"] = loc_name
            shot_copy["character_phase"] = char_phase
            shots.append(shot_copy)
    return shots


def get_total_shots_count(screenplay: dict) -> int:
    """计算剧本中的总镜头数

    Args:
        screenplay: 剧本数据

    Returns:
        总镜头数
    """
    return sum(
        len(loc.get("shots", []))
        for loc in screenplay.get("locations", [])
    )


def get_turnaround_path(output_dir: Path = None) -> Path:
    """获取角色基础三视图路径

    Args:
        output_dir: 输出目录，如果为 None 则使用默认目录

    Returns:
        三视图文件路径
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    return output_dir / "character_turnaround.png"


def load_image_as_pil(image_path: str):
    """加载图片为 PIL Image 对象

    Args:
        image_path: 图片路径

    Returns:
        PIL Image 对象，失败返回 None
    """
    try:
        from PIL import Image
        return Image.open(image_path)
    except Exception as e:
        print(f"  加载图片失败 {image_path}: {e}")
        return None


# ============================================================
# 角色锚定特征相关函数
# ============================================================


def build_anchor_prompt(character: dict) -> str:
    """从角色定义构建锚定特征 prompt

    Args:
        character: 角色信息字典

    Returns:
        锚定特征字符串，用于 image_prompt
    """
    anchor = character.get("anchor_features", {})
    if not anchor:
        return ""

    parts = []
    if anchor.get("face"):
        parts.append(anchor["face"])
    if anchor.get("hair"):
        parts.append(anchor["hair"])
    if anchor.get("body"):
        parts.append(anchor["body"])
    if anchor.get("distinguishing"):
        parts.append(anchor["distinguishing"])

    return ", ".join(parts)


def inject_anchor_to_prompt(image_prompt: str, character: dict, is_first: bool = False) -> str:
    """将角色锚定特征注入到 image_prompt

    Args:
        image_prompt: 原始 image_prompt
        character: 角色信息字典
        is_first: 是否是该角色的首次出场

    Returns:
        注入锚定特征后的 image_prompt
    """
    anchor = build_anchor_prompt(character)
    if not anchor:
        return image_prompt

    name = character.get("name", "character")

    # 检查是否已经以 anime style 开头
    prompt_lower = image_prompt.lower()
    has_anime_style = prompt_lower.startswith("anime style")

    if is_first:
        # 首次出场：完整特征
        if has_anime_style:
            # 在 "anime style, " 后插入锚定特征
            rest = image_prompt[len("anime style"):].lstrip(", ")
            return f"anime style, {anchor}, {rest}"
        else:
            return f"anime style, {anchor}, {image_prompt}"
    else:
        # 后续镜头：引用格式
        anchor_short = ", ".join([p.split(",")[0] for p in anchor.split(", ")[:3]])
        reference = f"the same {name} ({anchor_short})"

        if has_anime_style:
            rest = image_prompt[len("anime style"):].lstrip(", ")
            return f"anime style, {reference}, {rest}"
        else:
            return f"anime style, {reference}, {image_prompt}"


def get_suggested_duration(beat_type: str, intensity: float = 0.5) -> int:
    """根据场景类型和强度获取建议时长

    Args:
        beat_type: 节拍类型
        intensity: 情感强度 0-1

    Returns:
        建议时长（秒）
    """
    base_durations = {
        "setup": 3,
        "inciting_incident": 2,
        "rising_action": 2,
        "climax": 2,
        "resolution": 3
    }
    base = base_durations.get(beat_type, 2)

    # 高强度场景稍短，低强度场景稍长
    if intensity > 0.7:
        return max(1, base - 1)
    elif intensity < 0.3:
        return base + 1
    return base


def get_pacing_type_from_intensity(intensity: float) -> str:
    """根据强度值获取节奏类型

    Args:
        intensity: 情感强度 0-1

    Returns:
        节奏类型: "slow", "moderate", "fast"
    """
    for pacing_type, config in PACING_TYPES.items():
        min_intensity, max_intensity = config["intensity_range"]
        if min_intensity <= intensity < max_intensity:
            return pacing_type
        # 处理边界情况: intensity == 1.0 应归入 fast
        if intensity == 1.0 and pacing_type == "fast":
            return pacing_type
    return "moderate"


def get_suggested_shot_count(story: dict, location: dict) -> dict:
    """根据故事节奏获取场景的建议镜头数量

    根据场景关联的节拍类型和强度，动态计算建议的镜头数量。

    Args:
        story: 故事大纲数据（包含 story_beats）
        location: 场景/地点数据（包含 beats 列表）

    Returns:
        包含建议信息的字典:
        {
            "suggested_shot_count": int,  # 建议镜头数
            "pacing_type": str,           # 节奏类型 (slow/moderate/fast)
            "avg_intensity": float,       # 平均强度
            "duration_per_shot": tuple,   # 建议时长范围
            "beat_types": list,           # 关联的节拍类型
            "description": str            # 节奏描述
        }
    """
    beat_ids = location.get("beats", [])

    if not beat_ids:
        # 没有关联节拍，使用默认值
        return {
            "suggested_shot_count": 3,
            "pacing_type": "moderate",
            "avg_intensity": 0.5,
            "duration_per_shot": PACING_TYPES["moderate"]["duration_per_shot"],
            "beat_types": [],
            "description": PACING_TYPES["moderate"]["description"]
        }

    # 收集关联节拍的信息
    beats_info = []
    story_beats = story.get("story_beats", [])

    for beat_id in beat_ids:
        beat = get_beat_by_id(story, beat_id)
        if beat:
            beats_info.append({
                "beat_id": beat_id,
                "beat_type": beat.get("beat_type", "rising_action"),
                "intensity": beat.get("intensity", 0.5)
            })

    if not beats_info:
        # 节拍未找到，使用默认值
        return {
            "suggested_shot_count": 3,
            "pacing_type": "moderate",
            "avg_intensity": 0.5,
            "duration_per_shot": PACING_TYPES["moderate"]["duration_per_shot"],
            "beat_types": [],
            "description": PACING_TYPES["moderate"]["description"]
        }

    # 计算平均强度
    intensities = [b["intensity"] for b in beats_info]
    avg_intensity = sum(intensities) / len(intensities)

    # 收集节拍类型
    beat_types = list(set(b["beat_type"] for b in beats_info))

    # 根据强度确定节奏类型
    pacing_type = get_pacing_type_from_intensity(avg_intensity)
    pacing_config = PACING_TYPES[pacing_type]

    # 在范围内根据强度插值计算镜头数
    min_shots, max_shots = pacing_config["shot_count_range"]
    intensity_range = pacing_config["intensity_range"]

    # 在该节奏类型的强度范围内做插值
    if intensity_range[1] - intensity_range[0] > 0:
        # 计算在当前范围内的相对位置
        relative_pos = (avg_intensity - intensity_range[0]) / (intensity_range[1] - intensity_range[0])
        relative_pos = max(0, min(1, relative_pos))  # 限制在 0-1
        suggested_count = round(min_shots + relative_pos * (max_shots - min_shots))
    else:
        suggested_count = min_shots

    return {
        "suggested_shot_count": suggested_count,
        "pacing_type": pacing_type,
        "avg_intensity": round(avg_intensity, 2),
        "duration_per_shot": pacing_config["duration_per_shot"],
        "beat_types": beat_types,
        "description": pacing_config["description"]
    }


def analyze_pacing_distribution(story: dict) -> dict:
    """分析故事的节奏分布

    Args:
        story: 故事大纲数据

    Returns:
        节奏分布统计:
        {
            "locations": [{"location_id": int, "name": str, "pacing": dict}, ...],
            "distribution": {"slow": int, "moderate": int, "fast": int},
            "is_balanced": bool,
            "warnings": list
        }
    """
    locations_analysis = []
    distribution = {"slow": 0, "moderate": 0, "fast": 0}
    warnings = []

    for location in story.get("locations", []):
        pacing_info = get_suggested_shot_count(story, location)
        locations_analysis.append({
            "location_id": location.get("location_id"),
            "name": location.get("name", ""),
            "pacing": pacing_info
        })
        distribution[pacing_info["pacing_type"]] += 1

    total = len(locations_analysis)

    # 检查是否有高潮场景
    has_fast = distribution["fast"] > 0
    has_slow = distribution["slow"] > 0

    if not has_fast and total > 2:
        warnings.append("缺少快节奏场景（高潮/动作），故事可能显得平淡")

    if not has_slow and total > 2:
        warnings.append("缺少慢节奏场景，故事可能显得过于紧凑")

    # 计算分布是否均衡（至少有两种节奏类型）
    types_with_scenes = sum(1 for count in distribution.values() if count > 0)
    is_balanced = types_with_scenes >= 2

    return {
        "locations": locations_analysis,
        "distribution": distribution,
        "is_balanced": is_balanced,
        "warnings": warnings
    }


# ============================================================
# 剧本验证相关函数
# ============================================================


def validate_character_consistency(screenplay: dict) -> tuple:
    """验证角色一致性

    Args:
        screenplay: 剧本数据

    Returns:
        (errors, warnings) 元组
    """
    errors = []
    warnings = []

    # 获取角色信息
    characters = {}
    for phase in screenplay.get("character_phases", []):
        char_name = phase.get("character", "")
        if char_name and char_name not in characters:
            characters[char_name] = phase

    # 从 story_outline 中获取完整角色信息（如果有）
    story_characters = {}
    output_dir = screenplay.get("output_dir")
    if output_dir:
        try:
            story = load_story_outline(Path(output_dir))
            for char in story.get("characters", []):
                story_characters[char.get("name", "")] = char
        except SystemExit:
            pass

    # 检查每个角色是否有锚定特征
    for char_name, char_data in story_characters.items():
        anchor = build_anchor_prompt(char_data)
        if not anchor:
            warnings.append(f"角色 '{char_name}' 缺少 anchor_features 定义")
            continue

        # 检查镜头是否包含锚定特征
        for loc in screenplay.get("locations", []):
            for shot in loc.get("shots", []):
                action = shot.get("action", "")
                if char_name in action:
                    prompt = shot.get("image_prompt", "").lower()
                    anchor_parts = [p.strip() for p in anchor.lower().split(",") if p.strip()]
                    # 至少检查部分锚定特征
                    found_parts = sum(1 for p in anchor_parts if p in prompt)
                    if found_parts < len(anchor_parts) // 2:
                        warnings.append(
                            f"Shot {shot.get('shot_id')}: 可能缺少角色 '{char_name}' 的锚定特征"
                        )

    return errors, warnings


def validate_pacing(screenplay: dict) -> tuple:
    """验证叙事节奏

    Args:
        screenplay: 剧本数据

    Returns:
        (errors, warnings) 元组
    """
    errors = []
    warnings = []

    # 收集所有镜头时长和构图
    durations = []
    compositions = []
    for loc in screenplay.get("locations", []):
        for shot in loc.get("shots", []):
            durations.append(shot.get("duration", DEFAULT_SHOT_DURATION))
            compositions.append(shot.get("composition", ""))

    # 检查时长变化
    if durations and len(durations) > 3:
        if max(durations) - min(durations) < 1:
            warnings.append("所有镜头时长相同，缺少节奏变化")

    # 检查构图多样性
    if compositions and len(compositions) > 4:
        unique = set(c.lower() for c in compositions if c)
        if len(unique) < 3:
            warnings.append(f"构图类型过于单一（仅 {len(unique)} 种），建议增加多样性")

    return errors, warnings


def validate_prompts(screenplay: dict) -> tuple:
    """验证 Prompt 格式

    Args:
        screenplay: 剧本数据

    Returns:
        (errors, warnings) 元组
    """
    errors = []
    warnings = []

    for loc in screenplay.get("locations", []):
        for shot in loc.get("shots", []):
            shot_id = shot.get("shot_id", "unknown")
            image_prompt = shot.get("image_prompt", "")
            video_prompt = shot.get("video_prompt", "")

            # 检查 image_prompt 是否以 anime style 开头
            if image_prompt and not image_prompt.lower().startswith("anime style"):
                warnings.append(f"Shot {shot_id}: image_prompt 应以 'anime style' 开头")

            # 检查 video_prompt 是否包含摄影机类型
            if video_prompt and "[" not in video_prompt:
                warnings.append(f"Shot {shot_id}: video_prompt 应包含 [Camera Type] 格式")

    return errors, warnings


def validate_narration(screenplay: dict) -> tuple:
    """验证旁白质量

    Args:
        screenplay: 剧本数据

    Returns:
        (errors, warnings) 元组
    """
    errors = []
    warnings = []

    # 过于描述性的旁白模式
    descriptive_patterns = ["他走", "她走", "他站", "她站", "他看", "她看", "他跑", "她跑"]

    for loc in screenplay.get("locations", []):
        for shot in loc.get("shots", []):
            narration = shot.get("narration", "")
            if narration:
                for pattern in descriptive_patterns:
                    if narration.startswith(pattern):
                        warnings.append(
                            f"Shot {shot.get('shot_id')}: 旁白过于描述性 ('{narration[:20]}...')，建议使用内心独白或情感表达"
                        )
                        break

    return errors, warnings


def validate_screenplay(screenplay: dict) -> tuple:
    """运行所有验证检查

    Args:
        screenplay: 剧本数据

    Returns:
        (errors, warnings) 元组
    """
    all_errors = []
    all_warnings = []

    # 角色一致性
    errors, warnings = validate_character_consistency(screenplay)
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    # 节奏检查
    errors, warnings = validate_pacing(screenplay)
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    # Prompt 格式
    errors, warnings = validate_prompts(screenplay)
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    # 旁白质量
    errors, warnings = validate_narration(screenplay)
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    return all_errors, all_warnings


# ============================================================
# 分层地图相关函数
# ============================================================


def get_world_map_path(output_dir: Path = None) -> Path:
    """获取世界地图路径

    Args:
        output_dir: 输出目录，如果为 None 则使用默认目录

    Returns:
        世界地图文件路径
    """
    base_dir = output_dir if output_dir else OUTPUT_DIR
    return base_dir / WORLD_MAP_FILENAME


def get_region_map_path(region_id: int, output_dir: Path = None) -> Path:
    """获取区域地图路径

    Args:
        region_id: 区域 ID
        output_dir: 输出目录，如果为 None 则使用默认目录

    Returns:
        区域地图文件路径
    """
    base_dir = output_dir if output_dir else OUTPUT_DIR
    return base_dir / REGION_MAP_FILENAME_TEMPLATE.format(region_id)


def get_world_map(story: dict) -> dict:
    """获取世界地图信息

    Args:
        story: 故事大纲数据

    Returns:
        世界地图字典，如果不存在返回空字典
    """
    return story.get("world_map", {})


def get_region_by_id(story: dict, region_id: int) -> dict:
    """根据 ID 获取区域信息

    Args:
        story: 故事大纲数据
        region_id: 区域 ID

    Returns:
        区域信息字典，未找到返回空字典
    """
    for region in story.get("regions", []):
        if region.get("region_id") == region_id:
            return region
    return {}


def get_location_by_id(story: dict, location_id: int) -> dict:
    """根据 ID 获取场景/地点信息

    Args:
        story: 故事大纲数据
        location_id: 场景 ID

    Returns:
        场景信息字典，未找到返回空字典
    """
    for location in story.get("locations", []):
        if location.get("location_id") == location_id:
            return location
    return {}


def get_region_for_location(story: dict, location_id: int) -> dict:
    """根据场景 ID 获取所属区域

    Args:
        story: 故事大纲数据
        location_id: 场景 ID

    Returns:
        区域信息字典，未找到返回空字典
    """
    # 首先查找场景
    location = get_location_by_id(story, location_id)
    if not location:
        return {}

    # 检查场景是否有 region_id 字段
    region_id = location.get("region_id")
    if region_id is not None:
        return get_region_by_id(story, region_id)

    # 遍历所有区域，查找包含该场景的区域
    for region in story.get("regions", []):
        if location_id in region.get("locations", []):
            return region

    return {}


def get_locations_in_region(story: dict, region_id: int) -> list:
    """获取区域内的所有场景

    Args:
        story: 故事大纲数据
        region_id: 区域 ID

    Returns:
        场景列表
    """
    region = get_region_by_id(story, region_id)
    if not region:
        return []

    # 获取区域内的场景 ID 列表
    location_ids = region.get("locations", [])

    # 返回完整的场景信息
    return [
        loc for loc in story.get("locations", [])
        if loc.get("location_id") in location_ids or loc.get("region_id") == region_id
    ]


def build_inherited_style(story: dict, region_id: int = None, location_id: int = None) -> dict:
    """构建继承的风格信息

    风格继承链：World → Region → Location

    Args:
        story: 故事大纲数据
        region_id: 区域 ID（可选）
        location_id: 场景 ID（可选，如果提供会自动获取区域）

    Returns:
        合并后的风格字典
    """
    result = {}

    # 1. 从世界地图获取基础风格
    world_map = get_world_map(story)
    if world_map:
        style_base = world_map.get("style_base", {})
        result.update({
            "color_palette": style_base.get("color_palette", ""),
            "lighting_style": style_base.get("lighting_style", ""),
            "atmosphere": style_base.get("atmosphere", ""),
            "art_style": style_base.get("art_style", ""),
            "geography_anchors": world_map.get("geography_anchors", []),
        })

    # 2. 如果提供了 location_id，获取对应区域
    if location_id is not None and region_id is None:
        region = get_region_for_location(story, location_id)
        if region:
            region_id = region.get("region_id")

    # 3. 从区域获取修饰风格
    if region_id is not None:
        region = get_region_by_id(story, region_id)
        if region:
            style_modifiers = region.get("style_modifiers", {})
            # 合并区域特有的风格修饰
            if style_modifiers.get("color_accent"):
                result["color_accent"] = style_modifiers["color_accent"]
            if style_modifiers.get("unique_features"):
                result["unique_features"] = style_modifiers["unique_features"]

            # 添加区域地理特征
            geography = region.get("geography", {})
            if geography:
                result["region_geography"] = geography

    # 4. 如果提供了 location_id，添加场景特定特征
    if location_id is not None:
        location = get_location_by_id(story, location_id)
        if location:
            local_features = location.get("local_features", {})
            if local_features:
                result["local_features"] = local_features
            if location.get("time_of_day"):
                result["time_of_day"] = location["time_of_day"]

    return result


def build_style_prompt_from_inherited(inherited_style: dict) -> str:
    """从继承的风格信息构建提示词片段

    Args:
        inherited_style: 由 build_inherited_style 返回的风格字典

    Returns:
        风格提示词字符串
    """
    parts = []

    # 艺术风格
    if inherited_style.get("art_style"):
        parts.append(inherited_style["art_style"])

    # 调色板
    if inherited_style.get("color_palette"):
        parts.append(inherited_style["color_palette"])

    # 区域色彩强调
    if inherited_style.get("color_accent"):
        parts.append(inherited_style["color_accent"])

    # 光线风格
    if inherited_style.get("lighting_style"):
        parts.append(inherited_style["lighting_style"])

    # 氛围
    if inherited_style.get("atmosphere"):
        parts.append(inherited_style["atmosphere"])

    # 区域独特特征
    if inherited_style.get("unique_features"):
        parts.append(inherited_style["unique_features"])

    return ", ".join(parts) if parts else ""


def migrate_flat_locations(story: dict) -> dict:
    """向后兼容：为没有 world_map/regions 的旧剧本创建默认结构

    Args:
        story: 故事大纲数据

    Returns:
        迁移后的故事数据（原数据会被修改）
    """
    # 如果已有世界地图，不需要迁移
    if "world_map" in story and story["world_map"]:
        return story

    # 创建默认世界地图
    story["world_map"] = {
        "world_id": 1,
        "name": "默认世界",
        "description": "故事发生的世界",
        "style_base": {
            "color_palette": story.get("style_keywords", "anime style, vibrant colors"),
            "lighting_style": "natural lighting",
            "atmosphere": "cinematic",
            "art_style": "anime style"
        },
        "geography_anchors": [],
        "world_map_image": None
    }

    # 如果没有 regions，创建默认区域
    if "regions" not in story or not story["regions"]:
        # 收集所有 location_id
        location_ids = [loc.get("location_id", i + 1) for i, loc in enumerate(story.get("locations", []))]

        story["regions"] = [{
            "region_id": 1,
            "name": "默认区域",
            "description": "故事的主要发生地",
            "parent_world": 1,
            "style_modifiers": {},
            "geography": {},
            "region_map_image": None,
            "locations": location_ids
        }]

    # 为每个 location 添加 region_id（如果没有）
    for location in story.get("locations", []):
        if "region_id" not in location:
            location["region_id"] = 1

    return story


def has_layered_map_system(story: dict) -> bool:
    """检查故事是否使用了分层地图系统

    Args:
        story: 故事大纲数据

    Returns:
        是否使用了分层地图系统
    """
    world_map = story.get("world_map", {})
    regions = story.get("regions", [])

    # 检查是否有非默认的世界地图和区域
    has_world = bool(world_map and world_map.get("name") != "默认世界")
    has_regions = bool(regions and len(regions) > 0 and regions[0].get("name") != "默认区域")

    return has_world or has_regions


# ============================================================
# 分层背景相关函数
# ============================================================


def get_depth_guidance_prompt() -> str:
    """获取景深层次指导 prompt

    Returns:
        景深层次指导文本
    """
    return """
DEPTH COMPOSITION (create clear visual separation):
- FOREGROUND (bottom 15%): Close details like grass, flowers, rocks, fallen leaves
  - Slight soft focus, warm colors, high detail
- MIDGROUND (center 60%): Main scene elements
  - Sharp focus, rich details, primary visual interest
- BACKGROUND (top 25%): Distant elements (sky, mountains, horizon, buildings)
  - Atmospheric perspective, cooler tones, haze effect

DEPTH TECHNIQUES:
- Atmospheric perspective: increase haze with distance
- Color temperature shift: warm foreground → cool background
- Detail falloff: high detail near → simplified far
- Slight vignette to draw eye to midground"""


def get_layered_background_paths(loc_id: int, output_dir: Path = None) -> dict:
    """获取分层背景文件路径

    Args:
        loc_id: 场景 ID
        output_dir: 输出目录，如果为 None 则使用默认目录

    Returns:
        包含各层路径的字典
    """
    base_dir = output_dir if output_dir else OUTPUT_DIR

    return {
        "far": base_dir / f"loc_{loc_id:02d}_far.png",
        "mid": base_dir / f"loc_{loc_id:02d}_mid.png",
        "near": base_dir / f"loc_{loc_id:02d}_near.png",
        "depth": base_dir / f"loc_{loc_id:02d}_depth.png",
        "composite": base_dir / f"loc_{loc_id:02d}_bg.png",
    }


def composite_layers(far_img, mid_img, near_img):
    """合成三层背景图

    Args:
        far_img: 远景层 PIL Image (带透明通道)
        mid_img: 中景层 PIL Image (带透明通道)
        near_img: 近景层 PIL Image (带透明通道)

    Returns:
        合成后的 PIL Image (RGB)
    """
    from PIL import Image

    # 确保尺寸一致
    size = far_img.size

    # 创建画布
    result = Image.new("RGBA", size, (0, 0, 0, 0))

    # 按顺序叠加: 远景 → 中景 → 近景
    result = Image.alpha_composite(result, far_img.convert("RGBA"))
    result = Image.alpha_composite(result, mid_img.convert("RGBA"))
    result = Image.alpha_composite(result, near_img.convert("RGBA"))

    # 转为 RGB
    return result.convert("RGB")


def build_layer_prompt(location: dict, layer_type: str, style_keywords: str, inherited_style: dict = None) -> str:
    """构建单层生成提示词

    Args:
        location: 场景数据
        layer_type: 图层类型 (far/mid/near)
        style_keywords: 风格关键词
        inherited_style: 继承的风格信息

    Returns:
        生成提示词
    """
    name = location.get("name", "")
    time_of_day = location.get("time_of_day", "day")

    layer_specs = {
        "far": {
            "desc": "distant background elements only",
            "elements": "sky, clouds, distant mountains, horizon, sun/moon",
            "notes": "atmospheric perspective, hazy, cool colors, simplified forms"
        },
        "mid": {
            "desc": "middle ground scene elements",
            "elements": "main buildings, trees, terrain features, primary landscape",
            "notes": "sharp details, rich colors, main visual interest"
        },
        "near": {
            "desc": "close foreground elements",
            "elements": "grass, flowers, rocks, fallen leaves, close foliage, railings",
            "notes": "very detailed, warm colors, slight depth of field blur"
        }
    }

    spec = layer_specs.get(layer_type, layer_specs["mid"])

    # 时间光照映射
    time_lighting = {
        "dawn": "early dawn light, pink and orange sky",
        "morning": "morning sunlight, warm golden tones",
        "noon": "midday sun, bright and clear",
        "afternoon": "afternoon light, warm tones, long shadows",
        "dusk": "sunset colors, golden hour",
        "evening": "twilight, blue hour, ambient glow",
        "night": "nighttime, moonlight, dark blue tones",
        "midnight": "deep night, minimal lighting",
    }
    lighting = time_lighting.get(time_of_day.lower(), "natural lighting")

    # 构建继承的风格提示词
    inherited_style_prompt = ""
    if inherited_style:
        inherited_style_prompt = build_style_prompt_from_inherited(inherited_style)

    prompt = f"""anime style, {spec['desc']} on SOLID GREEN background (#00FF00):

SCENE CONTEXT: {name} ({time_of_day})
LIGHTING: {lighting}

INCLUDE ONLY: {spec['elements']}
LAYER STYLE: {spec['notes']}"""

    if inherited_style_prompt:
        prompt += f"""

REGION STYLE TO MAINTAIN:
{inherited_style_prompt}"""

    prompt += f"""

CRITICAL REQUIREMENTS:
- Paint elements on a SOLID BRIGHT GREEN (#00FF00) background
- NO characters, NO people
- Only include {layer_type} layer elements
- Elements should be positioned as they would appear in the scene
- {style_keywords}

The green background will be removed later for compositing."""

    return prompt


def get_parallax_video_path(loc_id: int, output_dir: Path = None) -> Path:
    """获取视差滚动视频路径

    Args:
        loc_id: 场景 ID
        output_dir: 输出目录，如果为 None 则使用默认目录

    Returns:
        视差视频文件路径
    """
    base_dir = output_dir if output_dir else OUTPUT_DIR
    return base_dir / f"loc_{loc_id:02d}_parallax.mp4"


def has_depth_layers(location: dict) -> bool:
    """检查场景是否有分层背景

    Args:
        location: 场景数据

    Returns:
        是否有分层背景
    """
    depth_layers = location.get("depth_layers", {})
    if not depth_layers:
        return False

    # 检查是否启用且存在所有必要的层
    if not depth_layers.get("enabled", False):
        return False

    required = ["far_layer", "mid_layer", "near_layer"]
    for key in required:
        path = depth_layers.get(key)
        if not path or not Path(path).exists():
            return False

    return True


# ============================================================
# 配音时长估算相关函数
# ============================================================


def remove_rhythm_markers(text: str) -> str:
    """移除节奏标记，只保留纯文字

    Args:
        text: 包含节奏标记的文本

    Returns:
        移除标记后的纯文本

    示例:
        >>> remove_rhythm_markers("[fast]快跑！[/fast]")
        "快跑！"
        >>> remove_rhythm_markers("等等[pause:500]再说")
        "等等再说"
    """
    if not text:
        return ""

    # 移除 [tag]...[/tag] 格式
    text = re.sub(r'\[/?(?:fast|slow|emphasis|pitch:[+-]?\d+)\]', '', text)
    # 移除 [pause:Nms] 或 [pause:N]
    text = re.sub(r'\[pause:\d+(?:ms)?\]', '', text)

    return text


def sum_pause_markers(text: str) -> float:
    """计算所有停顿标记的总时长（秒）

    Args:
        text: 包含节奏标记的文本

    Returns:
        停顿总时长（秒）

    示例:
        >>> sum_pause_markers("等等[pause:500]再说[pause:200]好的")
        0.7
    """
    if not text:
        return 0.0

    pauses = re.findall(r'\[pause:(\d+)(?:ms)?\]', text)
    return sum(int(p) for p in pauses) / 1000.0


def parse_rate_factor(rate: str) -> float:
    """将语速字符串转换为时长系数

    语速越快，时长越短；语速越慢，时长越长。

    Args:
        rate: 语速字符串，如 "+10%", "-10%", "+0%"

    Returns:
        时长系数

    示例:
        >>> parse_rate_factor("+10%")  # 语速快 10%
        0.909...  # 时长 = 1/1.1
        >>> parse_rate_factor("-10%")  # 语速慢 10%
        1.111...  # 时长 = 1/0.9
        >>> parse_rate_factor("+0%")
        1.0
    """
    if not rate:
        return 1.0

    match = re.match(r'([+-]?)(\d+)%', rate)
    if not match:
        return 1.0

    sign, value = match.groups()
    percent = int(value) / 100.0

    if sign == '+' or sign == '':
        # 语速加快 → 时长变短
        return 1.0 / (1.0 + percent) if percent > 0 else 1.0
    else:
        # 语速减慢 → 时长变长
        return 1.0 / (1.0 - percent) if percent < 1.0 else 1.0


def estimate_duration(text: str, rate: str = "+0%") -> float:
    """估算配音时长（秒）

    根据文字长度和语速参数估算配音时长。

    Args:
        text: 旁白文本（可包含节奏标记）
        rate: 语速参数，如 "+10%", "-10%"

    Returns:
        估算时长（秒），保留 2 位小数

    公式:
        基础时长 = 字符数 × 0.28秒/字
        实际时长 = 基础时长 × 语速系数 + 停顿时长

    示例:
        >>> estimate_duration("你好世界")  # 4字 × 0.28
        1.12
        >>> estimate_duration("[fast]快跑！[/fast]")  # 3字 × 0.28
        0.84
        >>> estimate_duration("等等[pause:500]再说")  # 4字 × 0.28 + 0.5
        1.62
    """
    if not text:
        return 0.0

    # 基础速率：每个汉字约 0.28 秒
    BASE_RATE = 0.28

    # 移除节奏标记，只计算实际文字
    clean_text = remove_rhythm_markers(text)
    char_count = len(clean_text)

    # 基础时长
    base_duration = char_count * BASE_RATE

    # 根据语速调整
    rate_factor = parse_rate_factor(rate)

    # 加上停顿时间
    pause_duration = sum_pause_markers(text)

    return round(base_duration * rate_factor + pause_duration, 2)


def get_mood_params(mood: str) -> tuple:
    """根据情绪获取语速和音调参数

    Args:
        mood: 情绪名称

    Returns:
        (rate, pitch) 元组
    """
    # 情绪-参数映射表（与 manga_generate_narration.py 同步）
    MOOD_PARAMETERS = {
        # 激动情绪 (语速稍快，音调稍高)
        "excited": ("+10%", "+5Hz"),
        "battle": ("+10%", "+5Hz"),
        "surprise": ("+8%", "+8Hz"),
        "angry": ("+8%", "+3Hz"),

        # 悲伤情绪 (语速稍慢，音调稍低)
        "sad": ("-8%", "-5Hz"),
        "melancholy": ("-8%", "-5Hz"),
        "farewell": ("-5%", "-3Hz"),
        "loss": ("-8%", "-5Hz"),

        # 温柔情绪 (语速稍慢，音调略高)
        "tender": ("-5%", "+2Hz"),
        "romantic": ("-5%", "+2Hz"),
        "warm": ("-3%", "+2Hz"),
        "love": ("-5%", "+2Hz"),

        # 紧张情绪 (语速稍快，音调稍高)
        "tense": ("+8%", "+5Hz"),
        "urgent": ("+10%", "+5Hz"),
        "chase": ("+8%", "+5Hz"),
        "danger": ("+8%", "+5Hz"),
        "suspense": ("+5%", "+3Hz"),

        # 平静情绪 (默认)
        "calm": ("+0%", "+0Hz"),
        "neutral": ("+0%", "+0Hz"),
        "narration": ("+0%", "+0Hz"),
        "peaceful": ("-3%", "+0Hz"),

        # 欢快情绪 (语速稍快，音调稍高)
        "happy": ("+5%", "+5Hz"),
        "joyful": ("+8%", "+5Hz"),
        "playful": ("+5%", "+3Hz"),

        # 神秘/庄重 (语速稍慢)
        "mysterious": ("-3%", "-2Hz"),
        "solemn": ("-5%", "-2Hz"),
        "epic": ("-3%", "+2Hz"),
    }

    if not mood:
        return ("+0%", "+0Hz")

    mood_lower = mood.lower().strip()
    if mood_lower in MOOD_PARAMETERS:
        return MOOD_PARAMETERS[mood_lower]

    return ("+0%", "+0Hz")
