#!/usr/bin/env python3
"""
调试 Minecraft 启动命令
"""
import json
from pathlib import Path
from service.minecraft.game_launcher import GameLauncher

# 使用您指定的目录
minecraft_dir = Path(r"C:\Users\Administrator\Desktop\zzz")

print(f"📁 Minecraft 目录: {minecraft_dir}")

# 检查目录是否存在
if not minecraft_dir.exists():
    print(f"❌ Minecraft 目录不存在: {minecraft_dir}")
    exit(1)

# 检查版本文件
version_json = minecraft_dir / "versions" / "1.21.10" / "1.21.10.json"
version_jar = minecraft_dir / "versions" / "1.21.10" / "1.21.10.jar"

if not version_json.exists():
    print("❌ 版本配置文件不存在:", version_json)
    exit(1)

if not version_jar.exists():
    print("❌ 版本JAR文件不存在:", version_jar)
    exit(1)

print("✅ 版本文件检查通过")

# 读取版本配置
with open(version_json, "r", encoding="utf-8") as f:
    version_data = json.load(f)

# 创建游戏启动器
launcher = GameLauncher(minecraft_dir=minecraft_dir)

# 手动调用构建命令函数来查看生成的命令
try:
    # 获取私有方法（仅用于调试）
    build_method = launcher._GameLauncher__build_launch_command if hasattr(launcher, '_GameLauncher__build_launch_command') else launcher._build_launch_command
    command = build_method(
        version_data=version_data,
        version_id="1.21.10",
        username="TestPlayer",
        uuid="",
        access_token="",
        jvm_args=["-Xmx2G", "-Xms1G"],
        extra_game_args=[]
    )
    
    if command:
        print("\n🚀 生成的启动命令:")
        print("=" * 50)
        print(' '.join(command))
        print("=" * 50)
        
        # 分析命令
        print("\n📝 命令分析:")
        for i, arg in enumerate(command):
            print(f"  [{i:2d}] {arg}")
    else:
        print("❌ 构建命令失败")
except Exception as e:
    print(f"❌ 构建命令时发生异常: {e}")
    import traceback
    traceback.print_exc()