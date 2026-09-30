"""精选 100 个差异明显的候选 emoji。

原则：单码点为主、不含肤色、不含 ZWJ 组合、不含旗帜；覆盖动物、食物、
物品、自然、交通、活动、表情、符号等类别，便于模型用是/否问题二分。
"""
from __future__ import annotations

VS16 = "️"

# (emoji, 英文名, 类别)
EMOJI_TABLE: list[tuple[str, str, str]] = [
    # 表情 / 人物
    ("😀", "grinning face", "face"),
    ("😂", "face with tears of joy", "face"),
    ("😍", "smiling face with heart-eyes", "face"),
    ("😎", "smiling face with sunglasses", "face"),
    ("😡", "enraged face", "face"),
    ("😱", "face screaming in fear", "face"),
    ("🤔", "thinking face", "face"),
    ("💀", "skull", "face"),
    ("👻", "ghost", "face"),
    ("🤖", "robot", "face"),
    ("👽", "alien", "face"),
    ("🎅", "Santa Claus", "person"),
    # 动物
    ("🐶", "dog face", "animal"),
    ("🐱", "cat face", "animal"),
    ("🐭", "mouse face", "animal"),
    ("🐰", "rabbit face", "animal"),
    ("🦊", "fox", "animal"),
    ("🐻", "bear", "animal"),
    ("🐼", "panda", "animal"),
    ("🐨", "koala", "animal"),
    ("🦁", "lion", "animal"),
    ("🐮", "cow face", "animal"),
    ("🐷", "pig face", "animal"),
    ("🐸", "frog", "animal"),
    ("🐵", "monkey face", "animal"),
    ("🐔", "chicken", "animal"),
    ("🐧", "penguin", "animal"),
    ("🦉", "owl", "animal"),
    ("🦅", "eagle", "animal"),
    ("🦆", "duck", "animal"),
    ("🐝", "honeybee", "animal"),
    ("🦋", "butterfly", "animal"),
    ("🐌", "snail", "animal"),
    ("🐢", "turtle", "animal"),
    ("🐍", "snake", "animal"),
    ("🦖", "T-Rex dinosaur", "animal"),
    ("🐙", "octopus", "animal"),
    ("🐬", "dolphin", "animal"),
    ("🐳", "spouting whale", "animal"),
    ("🦈", "shark", "animal"),
    ("🐘", "elephant", "animal"),
    ("🦒", "giraffe", "animal"),
    ("🐴", "horse face", "animal"),
    ("🦄", "unicorn", "animal"),
    # 植物 / 自然
    ("🌵", "cactus", "nature"),
    ("🌲", "evergreen tree", "nature"),
    ("🌹", "rose", "nature"),
    ("🌻", "sunflower", "nature"),
    ("🍄", "mushroom", "nature"),
    ("🌈", "rainbow", "nature"),
    ("⭐", "star", "nature"),
    ("🌙", "crescent moon", "nature"),
    ("☀️", "sun", "nature"),
    ("⚡", "high voltage lightning", "nature"),
    ("❄️", "snowflake", "nature"),
    ("🔥", "fire", "nature"),
    ("🌊", "water wave", "nature"),
    ("🌋", "volcano", "nature"),
    # 食物
    ("🍎", "red apple", "food"),
    ("🍌", "banana", "food"),
    ("🍉", "watermelon", "food"),
    ("🍓", "strawberry", "food"),
    ("🍋", "lemon", "food"),
    ("🥕", "carrot", "food"),
    ("🌽", "ear of corn", "food"),
    ("🍕", "pizza", "food"),
    ("🍔", "hamburger", "food"),
    ("🍣", "sushi", "food"),
    ("🍦", "soft ice cream", "food"),
    ("🎂", "birthday cake", "food"),
    ("☕", "hot beverage coffee", "food"),
    ("🍺", "beer mug", "food"),
    # 交通 / 地点
    ("🚗", "automobile car", "vehicle"),
    ("🚲", "bicycle", "vehicle"),
    ("🚀", "rocket", "vehicle"),
    ("✈️", "airplane", "vehicle"),
    ("🚂", "locomotive train", "vehicle"),
    ("⛵", "sailboat", "vehicle"),
    ("🏠", "house", "place"),
    ("🏰", "castle", "place"),
    # 活动 / 运动
    ("⚽", "soccer ball", "activity"),
    ("🏀", "basketball", "activity"),
    ("🎸", "guitar", "activity"),
    ("🎹", "musical keyboard piano", "activity"),
    ("🎮", "video game controller", "activity"),
    ("🎲", "game die", "activity"),
    ("🎁", "wrapped gift", "activity"),
    ("🎈", "balloon", "activity"),
    # 物品
    ("📱", "mobile phone", "object"),
    ("💻", "laptop computer", "object"),
    ("📷", "camera", "object"),
    ("📚", "books", "object"),
    ("✏️", "pencil", "object"),
    ("🔑", "key", "object"),
    ("🔒", "locked padlock", "object"),
    ("💡", "light bulb", "object"),
    ("⏰", "alarm clock", "object"),
    ("🔨", "hammer", "object"),
    ("💎", "gem stone diamond", "object"),
    ("💰", "money bag", "object"),
    ("👑", "crown", "object"),
    ("🎩", "top hat", "object"),
    ("👟", "running shoe", "object"),
    ("👓", "glasses", "object"),
    ("☂️", "umbrella", "object"),
    ("🧸", "teddy bear", "object"),
    # 符号
    ("❤️", "red heart", "symbol"),
    ("✅", "check mark button", "symbol"),
    ("❌", "cross mark", "symbol"),
    ("❓", "question mark", "symbol"),
    ("💯", "hundred points", "symbol"),
]


def normalize(e: str) -> str:
    """去掉变体选择符和空白，用于比较。"""
    return (e or "").strip().replace(VS16, "")


EMOJIS: list[dict] = [
    {"emoji": e, "name": n, "category": c} for e, n, c in EMOJI_TABLE
]
EMOJI_SET: set[str] = {normalize(e) for e, _, _ in EMOJI_TABLE}
NAME_BY_EMOJI: dict[str, str] = {normalize(e): n for e, n, _ in EMOJI_TABLE}

# 启动时校验没有重复
assert len(EMOJI_SET) == len(EMOJI_TABLE), "emoji 列表有重复"


def is_candidate(e: str) -> bool:
    return normalize(e) in EMOJI_SET


def name_of(e: str) -> str:
    return NAME_BY_EMOJI.get(normalize(e), "")


def candidate_list_text() -> str:
    """给模型看的候选集文本：不带类别的平铺列表。

    不暴露内部分类名：裁判看不到这张表，模型若按"是否属于 activity 类"提问，
    裁判只能按常识回答，容易和表里的归类不一致，把模型带偏。
    """
    return ", ".join(f"{e} ({n})" for e, n, _ in EMOJI_TABLE)
