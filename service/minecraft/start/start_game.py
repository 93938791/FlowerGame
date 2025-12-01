"""
Minecraft 游戏启动脚本
提供命令行方式启动 Minecraft 游戏
"""
import sys
import json
import argparse
from pathlib import Path
from service.minecraft.game_launcher import GameLauncher


def main():
    parser = argparse.ArgumentParser(description='启动 Minecraft 游戏')
    parser.add_argument('--version', '-v', required=True, help='Minecraft 版本 ID (如 1.21.10)')
    parser.add_argument('--username', '-u', default='Player', help='玩家用户名')
    parser.add_argument('--minecraft-dir', '-d', help='Minecraft 根目录')
    parser.add_argument('--jvm-args', help='JVM 参数 (JSON 格式数组)')
    parser.add_argument('--game-args', help='游戏参数 (JSON 格式数组)')
    
    args = parser.parse_args()
    
    # 确定 Minecraft 目录
    if args.minecraft_dir:
        minecraft_dir = Path(args.minecraft_dir)
    else:
        # 使用默认目录
        from config import Config
        if not Config.is_configured():
            print("❗ 未配置 FlowerGame 目录，请先启动 FlowerGame 主程序进行配置。")
            sys.exit(1)
        Config.init_dirs()
        minecraft_dir = Config.MINECRAFT_DIR
    
    # 确保目录存在
    minecraft_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🎮 启动 Minecraft {args.version}")
    print(f"📁 游戏目录: {minecraft_dir}")
    print(f"👤 用户名: {args.username}")
    
    # 解析 JVM 参数
    jvm_args = []
    if args.jvm_args:
        try:
            jvm_args = json.loads(args.jvm_args)
        except json.JSONDecodeError as e:
            print(f"❌ JVM 参数格式错误: {e}")
            sys.exit(1)
    
    # 解析游戏参数
    game_args = []
    if args.game_args:
        try:
            game_args = json.loads(args.game_args)
        except json.JSONDecodeError as e:
            print(f"❌ 游戏参数格式错误: {e}")
            sys.exit(1)
    
    # 创建游戏启动器
    launcher = GameLauncher(minecraft_dir=minecraft_dir)
    
    # 启动游戏
    process = launcher.launch_game(
        version_id=args.version,
        username=args.username,
        jvm_args=jvm_args,
        extra_game_args=game_args
    )
    
    if process:
        print(f"✅ Minecraft 启动成功，PID: {process.pid}")
        print("🎮 游戏正在运行...")
        # 等待进程结束
        try:
            process.wait()
            print("👋 游戏已退出")
        except KeyboardInterrupt:
            print("⚠️  游戏被中断")
            process.terminate()
    else:
        print("❌ Minecraft 启动失败")
        sys.exit(1)


if __name__ == "__main__":
    main()