"""
Minecraft 下载器测试示例
"""
from pathlib import Path
from service.minecraft.download import MinecraftDownloadManager, LoaderType, DownloadProgress
from utils.logger import logger


def progress_callback(progress: DownloadProgress):
    """进度回调函数"""
    if progress.total > 0:
        percentage = (progress.current / progress.total) * 100
        logger.info(f"[{progress.stage}] {percentage:.1f}% - {progress.message}")
    else:
        logger.info(f"[{progress.stage}] {progress.message}")


def test_list_versions():
    """测试列出版本"""
    logger.info("=== 测试列出版本 ===")
    
    with MinecraftDownloadManager() as manager:
        # 列出最新的 10 个正式版
        versions = manager.list_versions(version_type="release")
        logger.info(f"找到 {len(versions)} 个正式版本")
        
        if versions:
            logger.info("最新的 5 个正式版本:")
            for v in versions[:5]:
                logger.info(f"  - {v.get('id')} ({v.get('releaseTime')})")
        
        return True


def test_download_vanilla():
    """测试下载原版"""
    logger.info("=== 测试下载原版 Minecraft ===")
    
    # 使用自定义目录
    minecraft_dir = Path("C:/Users/Administrator/Desktop/zzz/.minecraft")
    
    with MinecraftDownloadManager(
        minecraft_dir=minecraft_dir,
        max_connections=30,
        progress_callback=progress_callback
    ) as manager:
        # 下载 1.20.1
        success = manager.download_vanilla("1.20.1")
        
        if success:
            logger.info("✓ 下载成功！")
        else:
            logger.error("✗ 下载失败")
        
        return success


def test_download_fabric():
    """测试下载 Fabric 版本"""
    logger.info("=== 测试下载 Fabric 版本 ===")
    
    minecraft_dir = Path("C:/Users/Administrator/Desktop/zzz/.minecraft")
    
    with MinecraftDownloadManager(
        minecraft_dir=minecraft_dir,
        progress_callback=progress_callback
    ) as manager:
        # 先获取 Fabric 版本列表
        fabric_versions = manager.get_loader_versions(LoaderType.FABRIC, "1.20.1")
        
        if fabric_versions:
            logger.info(f"找到 {len(fabric_versions)} 个 Fabric 版本")
            # 使用最新版本
            latest_loader = fabric_versions[0].get("loader", {}).get("version")
            logger.info(f"使用 Fabric Loader: {latest_loader}")
            
            # 下载
            success = manager.download_with_loader(
                mc_version="1.20.1",
                loader_type=LoaderType.FABRIC,
                loader_version=latest_loader
            )
            
            return success
        else:
            logger.error("获取 Fabric 版本列表失败")
            return False


def test_get_loader_versions():
    """测试获取加载器版本"""
    logger.info("=== 测试获取加载器版本 ===")
    
    with MinecraftDownloadManager() as manager:
        # Fabric
        fabric_versions = manager.get_loader_versions(LoaderType.FABRIC, "1.20.1")
        if fabric_versions:
            logger.info(f"✓ Fabric: 找到 {len(fabric_versions)} 个版本")
        
        # Forge
        forge_versions = manager.get_loader_versions(LoaderType.FORGE, "1.20.1")
        if forge_versions:
            logger.info(f"✓ Forge: 找到 {len(forge_versions)} 个版本")
        
        # OptiFine
        optifine_versions = manager.get_loader_versions(LoaderType.OPTIFINE, "1.20.1")
        if optifine_versions:
            logger.info(f"✓ OptiFine: 找到 {len(optifine_versions)} 个版本")
        
        return True


if __name__ == "__main__":
    logger.info("==================== Minecraft 下载器测试 ====================")
    
    # 测试 1: 列出版本
    test_list_versions()
    
    # 测试 2: 获取加载器版本
    # test_get_loader_versions()
    
    # 测试 3: 下载原版（取消注释以运行）
    # test_download_vanilla()
    
    # 测试 4: 下载 Fabric 版本（取消注释以运行）
    # test_download_fabric()
    
    logger.info("==================== 测试完成 ====================")
