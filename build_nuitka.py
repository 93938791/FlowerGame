import os
import sys
import subprocess
import glob

def build_nuitka():
    print("Starting Nuitka build...")
    
    # Nuitka 命令构建
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--enable-plugin=tk-inter",
        # 包含整个 resources 目录（包含 exe, dll, ico, png 等所有文件）
        "--include-data-dir=resources=resources",
        # "--include-data-dir=service=service", # 不需要包含 service 源码目录，Nuitka 会自动编译导入的模块
        "--windows-icon-from-ico=resources/logo.ico",
        "--windows-disable-console", # 禁用控制台窗口
        "--output-dir=dist_nuitka",
        "--output-filename=FlowerGame.exe", # 指定输出文件名
        "--remove-output", # 清理临时构建目录
        "--no-pyi-file",   # 不生成 pyi 文件
        "main.py"
    ]
    
    # 动态添加 easytier 和 syncthing 的二进制文件
    # Nuitka 默认可能会忽略数据目录中的 exe/dll，所以我们显式添加它们
    binary_patterns = [
        "resources/easytier/*.exe",
        "resources/easytier/*.dll",
        "resources/syncthing/*.exe"
    ]
    
    for pattern in binary_patterns:
        files = glob.glob(pattern)
        for file in files:
            # 格式: --include-data-file=source=dest
            # dest 应该是相对于 exe 的路径
            # 例如: resources/easytier/easytier-core.exe -> resources/easytier/easytier-core.exe
            dest = file.replace("\\", "/") # 统一使用正斜杠
            source = file.replace("\\", "/")
            arg = f"--include-data-file={source}={dest}"
            cmd.append(arg)
            print(f"Adding binary file: {arg}")

    print("Running command:", " ".join(cmd))
    
    # 运行命令
    # 注意：Nuitka 首次运行可能需要下载编译器，需要接受提示。
    # --assume-yes-for-downloads 可以自动接受下载
    cmd.append("--assume-yes-for-downloads")
    
    try:
        process = subprocess.run(cmd, check=True)
        print("\nBuild completed successfully!")
        print(f"Executable can be found in: {os.path.abspath('dist_nuitka')}")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with exit code {e.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    build_nuitka()
