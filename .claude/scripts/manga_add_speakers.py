#!/usr/bin/env python3
"""
为剧本添加说话人信息

根据旁白内容自动推断说话人，并添加语音配置。
"""

import json
import sys
import os


def add_speakers_to_screenplay(screenplay_path: str):
    """为剧本的每个镜头添加 speaker 字段"""

    with open(screenplay_path, 'r', encoding='utf-8') as f:
        screenplay = json.load(f)

    # 定义角色语音配置
    voice_config = {
        "小智": "yunxi",       # 阳光少年声
        "皮卡丘": "yunxia",    # 可爱声音
        "旁白": "xiaoxiao",    # 温暖女声旁白
        "大木博士": "yunyang", # 成熟男声
    }

    # 定义具体镜头的说话人（手动精确分配）
    shot_speakers = {
        # 场景1: 小智卧室 - 全是小智的内心独白
        "1-1": "小智",  # 成为宝可梦大师……
        "1-2": "小智",  # 这是我从小的梦想。
        "1-3": "小智",  # 什么？！已经这么晚了？！

        # 场景2: 大木研究所
        "2-1": "小智",      # 糟了！我睡过头了！
        "2-2": "小智",      # 博士！我来领我的宝可梦了！
        "2-3": "大木博士",   # 这只皮卡丘……有点特别。
        "2-4": "大木博士",   # 它不喜欢进精灵球。
        "2-5": "小智",      # 你好啊皮卡丘！请多指教！

        # 场景3: 森林小路 - 全是小智
        "3-1": "小智",  # 来吧皮卡丘，我们是伙伴了！
        "3-2": "小智",  # 我们一起努力，一定能成为最棒的搭档！
        "3-3": "小智",  # 为什么你就是不愿意相信我呢……
        "3-4": "小智",  # 我到底该怎么做才好呢……

        # 场景4: 烈雀群巢穴 - 紧张战斗
        "4-1": "小智",      # 那是……烈雀群？！
        "4-2": "小智",      # 它们看起来很生气……
        "4-3": "小智",      # 快跑！皮卡丘！
        "4-4": "小智",      # 不要放弃！继续跑！
        "4-5": "小智",      # 皮卡丘！你受伤了！
        "4-6": "小智",      # 皮卡丘……坚持住……
        "4-7": "小智",      # 我是你的训练师……我会保护你的！
        "4-8": "小智",      # 就算受伤也没关系！
        "4-9": "皮卡丘",    # 皮卡……丘！！！ (皮卡丘的吼叫)
        "4-10": "小智",     # 十万伏特！！！

        # 场景5: 森林溪边 - 和解
        "5-1": "小智",      # 我们……赢了吗？
        "5-2": "小智",      # 皮卡丘……谢谢你救了我。
        "5-3": "皮卡丘",    # 皮卡……皮卡丘！ (皮卡丘回应)
        "5-4": "小智",      # 皮卡丘！你愿意做我的伙伴了吗？
        "5-5": "小智",      # 从现在开始，我们是最好的伙伴了！
    }

    # 遍历所有镜头，添加说话人
    for loc in screenplay.get("locations", []):
        for shot in loc.get("shots", []):
            shot_id = shot.get("shot_id", "")
            # 使用预定义的说话人，如果没有则默认为小智
            shot["speaker"] = shot_speakers.get(shot_id, "小智")

    # 添加语音配置
    screenplay["voice_config"] = voice_config

    # 保存修改
    with open(screenplay_path, 'w', encoding='utf-8') as f:
        json.dump(screenplay, f, ensure_ascii=False, indent=2)

    print(f"✅ 已更新剧本: {screenplay_path}")

    # 打印说话人分配情况
    print("\n说话人分配:")
    print("-" * 60)
    for loc in screenplay.get("locations", []):
        print(f"\n场景 {loc['location_id']}: {loc['name']}")
        for shot in loc.get("shots", []):
            narration = shot.get("narration", "")[:25]
            speaker = shot.get("speaker", "未知")
            print(f"  {shot['shot_id']}: [{speaker}] {narration}...")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manga_add_speakers.py <screenplay_path>")
        sys.exit(1)

    add_speakers_to_screenplay(sys.argv[1])
