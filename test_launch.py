#!/usr/bin/env python3
"""
测试 Minecraft 启动功能
"""
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from service.minecraft.game_launcher import GameLauncher
from service.minecraft.start.start_game import main as start_game_main


def test_launch_with_custom_dir():
    """测试使用自定义目录启动游戏功能"""
    print("🎮 测试使用自定义目录启动 Minecraft 功能")
    
    # 使用您指定的目录
    minecraft_dir = Path(r"C:\Users\Administrator\Desktop\zzz")
    
    print(f"📁 Minecraft 目录: {minecraft_dir}")
    
    # 检查目录是否存在
    if not minecraft_dir.exists():
        print(f"❌ Minecraft 目录不存在: {minecraft_dir}")
        return False
    
    # 检查版本目录是否存在
    version_dir = minecraft_dir / "versions" / "1.21.10"
    if not version_dir.exists():
        print(f"❌ 版本目录不存在: {version_dir}")
        return False
    
    # 检查版本文件
    version_json = version_dir / "1.21.10.json"
    version_jar = version_dir / "1.21.10.jar"
    
    if not version_json.exists():
        print("❌ 版本配置文件不存在:", version_json)
        return False
    
    if not version_jar.exists():
        print("❌ 版本JAR文件不存在:", version_jar)
        return False
    
    print("✅ 版本文件检查通过")
    
    # 创建游戏启动器
    launcher = GameLauncher(minecraft_dir=minecraft_dir)
    
    print("🚀 启动 Minecraft 1.21.10...")
    
    # 启动游戏
    process = launcher.launch_game(
        version_id="1.21.10",
        username="TestPlayer",
        jvm_args=["-Xmx2G", "-Xms1G"],
        extra_game_args=[]
    )
    
    if process:
        print(f"✅ Minecraft 启动成功，PID: {process.pid}")
        print("🎮 游戏正在运行...")
        try:
            # 等待游戏进程结束
            return_code = process.wait()
            print(f"👋 游戏已退出，返回码: {return_code}")
            return True
        except KeyboardInterrupt:
            print("⚠️  游戏被中断")
            process.terminate()
            return True
    else:
        print("❌ Minecraft 启动失败")
        return False


def test_launch():
    """测试启动游戏功能 - 使用正确路径"""
    print("🎮 测试 Minecraft 启动功能")
    
    # 使用您指定的目录
    minecraft_dir = Path(r"C:\Users\Administrator\Desktop\zzz")
    
    print(f"📁 Minecraft 目录: {minecraft_dir}")
    
    # 检查目录是否存在
    if not minecraft_dir.exists():
        print(f"❌ Minecraft 目录不存在: {minecraft_dir}")
        return False
    
    # 检查版本目录是否存在
    version_dir = minecraft_dir / "versions" / "1.21.10"
    if not version_dir.exists():
        print(f"❌ 版本目录不存在: {version_dir}")
        return False
    
    # 检查版本文件
    version_json = version_dir / "1.21.10.json"
    version_jar = version_dir / "1.21.10.jar"
    
    if not version_json.exists():
        print("❌ 版本配置文件不存在:", version_json)
        return False
    
    if not version_jar.exists():
        print("❌ 版本JAR文件不存在:", version_jar)
        return False
    
    print("✅ 版本文件检查通过")
    
    # 创建游戏启动器
    launcher = GameLauncher(minecraft_dir=minecraft_dir)
    
    print("🚀 启动 Minecraft 1.21.10...")
    
    # 启动游戏
    process = launcher.launch_game(
        version_id="1.21.10",
        username="TestPlayer",
        jvm_args=["-Xmx2G", "-Xms1G"],
        extra_game_args=[]
    )
    
    if process:
        print(f"✅ Minecraft 启动成功，PID: {process.pid}")
        print("🎮 游戏正在运行...")
        try:
            # 等待游戏进程结束
            return_code = process.wait()
            print(f"👋 游戏已退出，返回码: {return_code}")
            return True
        except KeyboardInterrupt:
            print("⚠️  游戏被中断")
            process.terminate()
            return True
    else:
        print("❌ Minecraft 启动失败")
        return False


def test_cli():
    """测试命令行启动功能"""
    print("🎮 测试命令行启动功能")
    
    # 模拟命令行参数
    import sys
    original_argv = sys.argv.copy()
    
    # 设置测试参数，使用正确的目录
    sys.argv = [
        'test_launch.py',
        '--version', '1.21.10',
        '--username', 'TestPlayerCLI',
        '--minecraft-dir', r'C:\Users\Administrator\Desktop\zzz',
        '--jvm-args', json.dumps(['-Xmx2G', '-Xms1G'])
    ]
    
    try:
        start_game_main()
        return True
    except SystemExit as e:
        if e.code == 0:
            print("✅ 命令行启动测试成功")
            return True
        else:
            print(f"❌ 命令行启动测试失败，退出码: {e.code}")
            return False
    except Exception as e:
        print(f"❌ 命令行启动测试出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 恢复原始参数
        sys.argv = original_argv


if __name__ == "__main__":
    print("=" * 50)
    print("Minecraft 启动功能测试")
    print("=" * 50)
    
    # 测试使用自定义目录的方式
    print("\n1. 测试使用自定义目录方式:")
    success1 = test_launch_with_custom_dir()
    
    # 测试直接调用方式
    print("\n2. 测试直接调用方式:")
    success2 = test_launch()
    
    # 测试命令行方式
    print("\n3. 测试命令行方式:")
    success3 = test_cli()
    
    print("\n" + "=" * 50)
    if success1 or success2 or success3:
        print("🎉 至少有一个测试通过!")
    else:
        print("❌ 所有测试都失败了")
    print("=" * 50)