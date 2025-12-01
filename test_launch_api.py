#!/usr/bin/env python3
"""
测试 Minecraft 启动 API 修复
"""
import requests
import json

def test_launch_api():
    """测试启动 API 是否正确传递 UUID 和访问令牌"""
    url = "http://localhost:17890/api/minecraft/launch"
    
    # 测试数据
    test_data = {
        "version_id": "1.21.10",
        "username": "TestPlayer",
        "uuid": "test-uuid-12345",
        "access_token": "test-access-token-67890",
        "jvm_args": ["-Xmx2G"],
        "extra_game_args": []
    }
    
    print("🧪 测试 Minecraft 启动 API...")
    print(f"📤 发送请求到: {url}")
    print(f"📋 请求数据: {json.dumps(test_data, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(url, json=test_data)
        print(f"📥 响应状态码: {response.status_code}")
        print(f"📄 响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API 响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if result.get("ok"):
                print("🎉 游戏启动成功!")
                return True
            else:
                print("❌ 游戏启动失败")
                return False
        else:
            print(f"❌ HTTP 错误: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保服务器正在运行")
        return False
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False

if __name__ == "__main__":
    test_launch_api()