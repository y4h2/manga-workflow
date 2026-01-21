#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Manga Generation - Screenplay Creation Script
Read JSON from stdin, normalize Chinese punctuation, write to screenplay.json
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from manga_common import (
    SCREENPLAY_PATH,
    DEFAULT_STYLE_KEYWORDS,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_SCENE_DURATION,
    DEFAULT_SHOT_DURATION,
    VALID_ASPECT_RATIOS,
    VALID_COMPOSITIONS,
    is_new_format,
    create_output_subdir,
)


def normalize_chinese_punctuation(text: str) -> str:
    """
    Normalize Chinese punctuation marks.
    Convert English punctuation near Chinese characters to Chinese punctuation.
    """
    if not text:
        return text

    # English -> Chinese punctuation mapping
    punctuation_map = {
        ",": "\uff0c",  # Chinese comma
        ".": "\u3002",  # Chinese period
        "!": "\uff01",  # Chinese exclamation
        "?": "\uff1f",  # Chinese question mark
        ":": "\uff1a",  # Chinese colon
        ";": "\uff1b",  # Chinese semicolon
        "(": "\uff08",  # Chinese left paren
        ")": "\uff09",  # Chinese right paren
        "[": "\u3010",  # Chinese left bracket
        "]": "\u3011",  # Chinese right bracket
        '"': "\u201c",  # Chinese left quote
    }

    result = text

    # Only replace punctuation near Chinese characters
    for eng, chn in punctuation_map.items():
        # English punctuation after Chinese char -> Chinese punctuation
        pattern = f"([\u4e00-\u9fff]){re.escape(eng)}"
        result = re.sub(pattern, f"\\1{chn}", result)

        # English punctuation before Chinese char -> Chinese punctuation
        pattern = f"{re.escape(eng)}([\u4e00-\u9fff])"
        result = re.sub(pattern, f"{chn}\\1", result)

    # Handle quote pairing
    quote_count = 0
    chars = list(result)
    for i, char in enumerate(chars):
        if char == '"' or char == "\u201c" or char == "\u201d":
            if quote_count % 2 == 0:
                chars[i] = "\u201c"  # Left quote
            else:
                chars[i] = "\u201d"  # Right quote
            quote_count += 1
    result = "".join(chars)

    # Handle ellipsis
    result = result.replace("...", "\u2026\u2026")

    # Handle dash
    result = result.replace("--", "\u2014\u2014")

    return result


def process_scene(scene: dict) -> dict:
    """Process a single scene, normalize Chinese punctuation."""
    processed = scene.copy()

    # Process Chinese text fields
    chinese_fields = ["narration"]
    for field in chinese_fields:
        if field in processed and processed[field]:
            processed[field] = normalize_chinese_punctuation(processed[field])

    return processed


def validate_shot(shot: dict, shot_id: str) -> list:
    """Validate a single shot in the new format."""
    errors = []
    prefix = f"Shot {shot_id}"

    required_fields = ["image_prompt", "video_prompt"]
    for field in required_fields:
        if field not in shot:
            errors.append(f"{prefix}: missing field {field}")
        elif not shot[field]:
            errors.append(f"{prefix}: field {field} cannot be empty")

    # Validate duration
    if "duration" in shot:
        duration = shot["duration"]
        if not isinstance(duration, (int, float)):
            errors.append(f"{prefix}: duration must be a number")
        elif not (1 <= duration <= 10):
            errors.append(f"{prefix}: duration should be 1-10 seconds, got {duration}")

    # Validate composition
    if "composition" in shot:
        composition = shot["composition"].lower()
        valid_lower = [c.lower() for c in VALID_COMPOSITIONS]
        if composition not in valid_lower:
            errors.append(
                f"{prefix}: invalid composition '{shot['composition']}'. "
                f"Valid values: {VALID_COMPOSITIONS}"
            )

    return errors


def validate_sequence(sequence: dict, seq_num: int) -> list:
    """Validate a sequence in the new format."""
    errors = []
    prefix = f"Sequence {seq_num}"

    if "shots" not in sequence:
        errors.append(f"{prefix}: missing 'shots' array")
        return errors

    if not isinstance(sequence["shots"], list):
        errors.append(f"{prefix}: 'shots' must be an array")
        return errors

    if len(sequence["shots"]) == 0:
        errors.append(f"{prefix}: 'shots' cannot be empty")
        return errors

    for i, shot in enumerate(sequence["shots"]):
        shot_id = shot.get("shot_id", f"{seq_num}-{i+1}")
        shot_errors = validate_shot(shot, shot_id)
        errors.extend(shot_errors)

    return errors


def validate_screenplay(data: dict) -> list:
    """Validate screenplay data structure, return list of errors."""
    errors = []

    # Required field: title
    if "title" not in data:
        errors.append("Missing required field: title")

    # Check format: new (sequences) or old (scenes)
    has_sequences = "sequences" in data and len(data.get("sequences", [])) > 0
    has_scenes = "scenes" in data and len(data.get("scenes", [])) > 0

    if not has_sequences and not has_scenes:
        errors.append("Missing required field: 'sequences' (new format) or 'scenes' (old format)")

    # Validate top-level optional fields
    if "aspect_ratio" in data:
        if data["aspect_ratio"] not in VALID_ASPECT_RATIOS:
            errors.append(
                f"Invalid aspect_ratio: {data['aspect_ratio']}. "
                f"Valid values: {VALID_ASPECT_RATIOS}"
            )

    if "target_duration" in data:
        if not isinstance(data["target_duration"], (int, float)) or data["target_duration"] <= 0:
            errors.append("target_duration must be a positive number")

    # Validate new format (sequences)
    if has_sequences:
        for i, seq in enumerate(data["sequences"]):
            seq_num = seq.get("sequence_id", i + 1)
            seq_errors = validate_sequence(seq, seq_num)
            errors.extend(seq_errors)

    # Validate old format (scenes)
    elif has_scenes:
        if not isinstance(data["scenes"], list):
            errors.append("scenes must be an array")
        elif len(data["scenes"]) == 0:
            errors.append("scenes cannot be empty")
        else:
            for i, scene in enumerate(data["scenes"]):
                scene_errors = validate_scene(scene, i + 1)
                errors.extend(scene_errors)

    return errors


def validate_scene(scene: dict, scene_num: int) -> list:
    """Validate a single scene."""
    errors = []
    prefix = f"Scene {scene_num}"

    required_fields = ["scene_id", "narration", "image_prompt", "video_prompt"]
    for field in required_fields:
        if field not in scene:
            errors.append(f"{prefix}: missing field {field}")
        elif not scene[field]:
            errors.append(f"{prefix}: field {field} cannot be empty")

    # Check if image_prompt starts with "anime style"
    if "image_prompt" in scene and scene["image_prompt"]:
        if not scene["image_prompt"].lower().startswith("anime style"):
            errors.append(f"{prefix}: image_prompt should start with 'anime style'")

    # Validate duration (optional field)
    if "duration" in scene:
        duration = scene["duration"]
        if not isinstance(duration, (int, float)):
            errors.append(f"{prefix}: duration must be a number")
        elif not (1 <= duration <= 10):
            errors.append(f"{prefix}: duration should be 1-10 seconds, got {duration}")

    # Validate composition (optional field)
    if "composition" in scene:
        composition = scene["composition"].lower()
        valid_lower = [c.lower() for c in VALID_COMPOSITIONS]
        if composition not in valid_lower:
            errors.append(
                f"{prefix}: invalid composition '{scene['composition']}'. "
                f"Valid values: {VALID_COMPOSITIONS}"
            )

    return errors


def set_defaults(data: dict) -> dict:
    """
    Set default values for optional fields.

    Args:
        data: Screenplay data dictionary

    Returns:
        Updated screenplay data with defaults
    """
    # Top-level defaults
    if "style_keywords" not in data:
        data["style_keywords"] = DEFAULT_STYLE_KEYWORDS

    if "aspect_ratio" not in data:
        data["aspect_ratio"] = DEFAULT_ASPECT_RATIO

    # Check if new format (sequences) or old format (scenes)
    if "sequences" in data and len(data.get("sequences", [])) > 0:
        # New format: sequences with shots
        total_shots = 0
        for seq_idx, seq in enumerate(data["sequences"]):
            # Ensure sequence_id
            if "sequence_id" not in seq:
                seq["sequence_id"] = seq_idx + 1

            # Process shots
            for shot_idx, shot in enumerate(seq.get("shots", [])):
                # Ensure shot_id
                if "shot_id" not in shot:
                    shot["shot_id"] = f"{seq['sequence_id']}-{shot_idx + 1}"

                # Default duration
                if "duration" not in shot:
                    shot["duration"] = DEFAULT_SHOT_DURATION

                total_shots += 1

        # Calculate total_shots
        if "total_shots" not in data:
            data["total_shots"] = total_shots

        # Calculate target_duration
        if "target_duration" not in data:
            data["target_duration"] = sum(
                shot.get("duration", DEFAULT_SHOT_DURATION)
                for seq in data.get("sequences", [])
                for shot in seq.get("shots", [])
            )

    else:
        # Old format: scenes
        for scene in data.get("scenes", []):
            if "duration" not in scene:
                scene["duration"] = DEFAULT_SCENE_DURATION

        # Calculate target_duration if not specified
        if "target_duration" not in data:
            data["target_duration"] = sum(
                s.get("duration", DEFAULT_SCENE_DURATION)
                for s in data.get("scenes", [])
            )

    return data


def create_screenplay(data: dict, output_path: Path = None) -> bool:
    """
    Create screenplay JSON file.

    Args:
        data: Screenplay data dictionary
        output_path: Output path, defaults to screenplay.json

    Returns:
        Success status
    """
    if output_path is None:
        output_path = SCREENPLAY_PATH

    # Validate data
    errors = validate_screenplay(data)
    if errors:
        print("Screenplay validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False

    # Set default values for optional fields
    data = set_defaults(data)

    # Create output subfolder based on title
    title = data.get("title", "untitled")
    output_dir = create_output_subdir(title)
    data["output_dir"] = str(output_dir)
    print(f"Output directory: {output_dir}")

    # Add metadata
    if "task_id" not in data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data["task_id"] = f"manga_{timestamp}"

    # Handle total_scenes for old format
    if "scenes" in data and "total_scenes" not in data:
        data["total_scenes"] = len(data["scenes"])

    # Process Chinese punctuation
    if "sequences" in data and len(data.get("sequences", [])) > 0:
        # New format: process shots in sequences
        for seq in data["sequences"]:
            for shot in seq.get("shots", []):
                if "narration" in shot and shot["narration"]:
                    shot["narration"] = normalize_chinese_punctuation(shot["narration"])
    elif "scenes" in data:
        # Old format: process scenes
        data["scenes"] = [process_scene(scene) for scene in data["scenes"]]

    # Write screenplay JSON to output subdirectory
    # ensure_ascii=False to preserve Chinese characters
    # indent=2 for formatted output
    screenplay_path = output_dir / "screenplay.json"
    with open(screenplay_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Create project reference file at root
    project_ref = {"project_path": str(output_dir)}
    with open(SCREENPLAY_PATH, "w", encoding="utf-8") as f:
        json.dump(project_ref, f, ensure_ascii=False, indent=2)

    print(f"Screenplay saved: {screenplay_path}")
    print(f"Project reference: {SCREENPLAY_PATH}")
    print(f"Title: {data.get('title', 'Untitled')}")
    print(f"Output directory: {data.get('output_dir', 'output/')}")

    # Show format-specific info
    if "sequences" in data and len(data.get("sequences", [])) > 0:
        print(f"Format: sequences (细粒度分镜)")
        print(f"Sequences: {len(data['sequences'])}")
        print(f"Total shots: {data.get('total_shots', 'N/A')}")
    else:
        print(f"Format: scenes (传统格式)")
        print(f"Scenes: {len(data.get('scenes', []))}")

    print(f"Style: {data.get('style_keywords', 'N/A')}")
    print(f"Aspect ratio: {data.get('aspect_ratio', 'N/A')}")
    print(f"Target duration: {data.get('target_duration', 'N/A')} seconds")

    return True


def main():
    """Read JSON from stdin and create screenplay."""
    # Check if there's pipe input
    if sys.stdin.isatty():
        print("Usage: echo '<json>' | python manga_create_screenplay.py")
        print("Or: cat screenplay_data.json | python manga_create_screenplay.py")
        sys.exit(1)

    # Read stdin
    try:
        input_data = sys.stdin.read()
        data = json.loads(input_data)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        sys.exit(1)

    # Create screenplay
    success = create_screenplay(data)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
