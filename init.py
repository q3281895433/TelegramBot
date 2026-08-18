"""
modules/__init__.py
====================
工具模块注册表，按 tier 分成"免费查询"和"付费查询"两套。

【2026-08-17 修复说明】
原版靠在本文件底部手写 `from . import xxx` 来触发每个模块文件里的
register() 调用。这种写法有两个隐患，会导致"功能变多后按钮莫名消失"：

  1. 这些 import 表面上"没被使用"（没有 xxx.func() 这种直接调用），
     只是靠 side effect 注册工具。VS Code / Ruff / autoflake 等
     "保存时自动整理导入"功能常常不认 `# noqa`，会把这些 import
     误判为无用代码直接删掉，导致对应模块再也不会被注册。
  2. 如果手写 import 的顺序被格式化工具重新排序，恰好两个模块又
     不小心用了相同的 key（比如复制别的模块文件忘记改 key），
     字典里"后 import 的覆盖先 import 的"这个规则就会随顺序变化，
     出现"这次是 A 消失，下次是 B 消失"的跷跷板现象。

现在改成【自动扫描 modules/ 目录】，不再需要手写任何 import 行：
新增一个模块，只要在 modules/ 下新建 .py 文件、文件末尾调用
register(...) 就行，完全不用碰这个文件，也就不存在"忘记 import"
或"import 被格式化工具删掉"的问题了。

如果你还是想手动控制加载顺序/临时禁用某个模块，把对应文件名
放进下面的 _EXCLUDE 集合即可（不需要删除文件）。
"""

import importlib
import pkgutil

FREE_MODULES = {}
PAID_MODULES = {}

# 不想被自动加载的模块文件名（不含 .py 后缀），临时禁用某个工具时用
_EXCLUDE = {"__init__"}


def register(key, title, run, emoji="🧩", tier="free", cost=0, prompt="请输入内容："):
    """
    key    : 唯一标识，比如 'converter'。
             ⚠️ 必须在 FREE_MODULES / PAID_MODULES 范围内各自唯一，
             重复的 key 会互相覆盖且不会报错、不会提示，
             新增模块时如果是复制别的文件改的，切记检查这里改掉。
    title  : 按钮上显示的名字
    run    : 函数 (user_input: str) -> str，返回要展示给用户的结果文本
    emoji  : 按钮图标
    tier   : 'free' 或 'paid'，决定挂在哪个面板下
    cost   : 仅 paid 模块生效，这次调用消耗多少积分
    prompt : 点击按钮后，提示用户输入什么
    """
    target = PAID_MODULES if tier == "paid" else FREE_MODULES

    if key in target:
        # 主动报错而不是静默覆盖：这是本次修复的核心——
        # 与其让按钮"悄悄消失"，不如启动时直接崩溃告诉你哪里重名了。
        raise RuntimeError(
            f"模块 key 冲突：'{key}' 在 tier='{tier}' 下已经被注册过一次了，"
            f"请检查 modules/ 目录下是否有两个文件用了相同的 key。"
        )

    target[key] = {
        "key": key, "title": title, "emoji": emoji, "tier": tier, "cost": cost,
        "prompt": prompt, "run": run,
    }


def get_module(tier, key):
    return (PAID_MODULES if tier == "paid" else FREE_MODULES).get(key)


def _autoload():
    """
    扫描 modules/ 目录下所有 .py 文件并逐个 import，
    触发各文件末尾的 register(...) 调用。
    按文件名排序，保证每次启动加载顺序一致（避免"顺序不同导致覆盖结果不同"）。
    """
    package_path = __path__
    package_name = __name__

    names = sorted(
        name for _, name, is_pkg in pkgutil.iter_modules(package_path)
        if not is_pkg and name not in _EXCLUDE
    )
    for name in names:
        importlib.import_module(f"{package_name}.{name}")


_autoload()
