#!/usr/bin/env python3
"""
检查 Minecraft 版本 JSON 文件结构
"""
import json
from pathlib import Path

# 读取版本 JSON 文件
version_json_path = Path(r"C:\Users\Administrator\Desktop\zzz\versions\1.21.10\1.21.10.json")

if version_json_path.exists():
    with open(version_json_path, "r", encoding="utf-8") as f:
        version_data = json.load(f)
    
    print("版本 JSON 文件结构:")
    print("=" * 50)
    
    # 显示基本信息
    print(f"ID: {version_data.get('id', 'N/A')}")
    print(f"类型: {version_data.get('type', 'N/A')}")
    print(f"主类: {version_data.get('mainClass', 'N/A')}")
    
    # 显示参数结构
    if "arguments" in version_data:
        print("\n参数结构:")
        arguments = version_data["arguments"]
        if "game" in arguments:
            print("  游戏参数:")
            for i, arg in enumerate(arguments["game"]):
                print(f"    [{i}] {arg}")
        if "jvm" in arguments:
            print("  JVM 参数:")
            for i, arg in enumerate(arguments["jvm"]):
                print(f"    [{i}] {arg}")
    
    # 显示资产索引信息
    if "assetIndex" in version_data:
        asset_index = version_data["assetIndex"]
        print(f"\n资产索引:")
        print(f"  ID: {asset_index.get('id', 'N/A')}")
        print(f"  SHA1: {asset_index.get('sha1', 'N/A')}")
        print(f"  URL: {asset_index.get('url', 'N/A')}")
    
    # 显示库信息
    if "libraries" in version_data:
        print(f"\n库数量: {len(version_data['libraries'])}")
        # 显示前几个库作为示例
        print("前5个库:")
        for i, lib in enumerate(version_data["libraries"][:5]):
            print(f"  [{i}] {lib.get('name', 'N/A')}")
else:
    print(f"文件不存在: {version_json_path}")