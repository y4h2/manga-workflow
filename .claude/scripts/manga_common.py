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
