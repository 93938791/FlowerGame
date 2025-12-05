import PyInstaller.__main__
import uuid
import os
import sys
import shutil

def build():
    # PyInstaller 6.0+ 移除了 --key 参数
    # 为了防报毒，建议使用 Nuitka，或者接受误报并提交厂商
    
    # 定义资源文件
    # 格式: "源路径;目标路径"
    add_data = [
        "resources;resources",
        "service;service",  # 包含 service 目录下的所有 python 文件（虽然 PyInstaller 会自动分析导入，但显式添加非 Python 资源更安全，如果是代码文件通常不需要 add-data 除非是动态加载）
    ]
    
    # 构建参数
    args = [
        'main.py',                      # 入口文件
        '--name=FlowerGame',            # 生成的可执行文件名
        '--onefile',                    # 打包成单文件
        '--clean',                      # 清理缓存
        '--noconfirm',                  # 不确认覆盖
        '--icon=resources/logo.ico',    # 图标
        # '--windowed',                 # 隐藏控制台 (如果需要调试可以看到报错，建议先不加，或者根据用户需求加)
        # 为了防报毒，有时候有控制台反而好一点，但用户体验不好。
        # 这里暂时加上 --noconsole (即 --windowed)，因为用户说了是 UI 相关的
        '--noconsole',
        # 显式设置输出与工作目录，避免与前端 FlowerGameUI 的 dist 冲突
        '--distpath=dist_py',
        '--workpath=build_py'
    ]

    # 添加数据文件
    for data in add_data:
        args.append(f'--add-data={data}')

    # 添加 hidden imports (如果有隐式导入的库)
    hidden_imports = [
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'engineio.async_drivers.aiohttp', # 如果用了 python-socketio/engineio
    ]
    
    for hidden in hidden_imports:
        args.append(f'--hidden-import={hidden}')

    print("Starting build with arguments:", args)
    
    try:
        PyInstaller.__main__.run(args)
        print("\nBuild completed successfully!")
        print(f"Executable can be found in: {os.path.abspath('dist')}")
    except Exception as e:
        print(f"\nBuild failed: {e}")

if __name__ == "__main__":
    build()
