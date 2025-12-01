"""测试真实下载"""
from pathlib import Path
from service.minecraft.download import MinecraftDownloadManager, DownloadProgress
import time

def progress_callback(progress: DownloadProgress):
    """进度回调"""
    if progress.total > 0:
        percentage = (progress.current / progress.total) * 100
        print(f"[{progress.stage}] {percentage:.1f}% - {progress.message}")
    else:
        print(f"[{progress.stage}] {progress.message}")

# 创建下载管理器
minecraft_dir = Path(r"C:\Users\Administrator\Desktop\zzz\.minecraft")
print(f"✓ 目标目录: {minecraft_dir}")

manager = MinecraftDownloadManager(
    minecraft_dir=minecraft_dir,
    # max_connections=10,  # 注释掉让其自动计算
    progress_callback=progress_callback
)

print(f"✓ 下载器已创建，目录: {manager.minecraft_dir}")
print(f"✓ 目录存在: {manager.minecraft_dir.exists()}")

# 开始下载
print("\n开始下载 1.21 版本...")
try:
    success = manager.download_vanilla("1.21")
    print(f"\n{'✓ 下载成功' if success else '✗ 下载失败'}")
except Exception as e:
    print(f"\n✗ 下载异常: {e}")
    import traceback
    traceback.print_exc()
finally:
    manager.close()

print("\n检查下载结果:")
versions_dir = minecraft_dir / "versions" / "1.21"
if versions_dir.exists():
    print(f"✓ 版本目录存在: {versions_dir}")
    files = list(versions_dir.iterdir())
    print(f"✓ 文件数量: {len(files)}")
    for f in files[:5]:  # 显示前5个文件
        print(f"  - {f.name} ({f.stat().st_size / 1024:.1f} KB)")
else:
    print(f"✗ 版本目录不存在: {versions_dir}")
