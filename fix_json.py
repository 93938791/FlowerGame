import json

json_path = r"C:\Users\Administrator\Desktop\FlowerGame\.minecraft\versions\aaa\1.21.10.json"

# 读取JSON
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 去重libraries
seen = {}
new_libs = []

for lib in data['libraries']:
    name = lib.get('name', '')
    if not name:
        new_libs.append(lib)
        continue
    
    # 提取 groupId:artifactId
    parts = name.split(':')
    if len(parts) >= 2:
        base_name = f"{parts[0]}:{parts[1]}"
        
        if base_name in seen:
            # 有重复，替换为新版本
            old_lib = seen[base_name]
            old_index = new_libs.index(old_lib)
            new_libs[old_index] = lib
            seen[base_name] = lib
            print(f"替换: {old_lib.get('name')} -> {name}")
        else:
            # 第一次见到
            seen[base_name] = lib
            new_libs.append(lib)
    else:
        new_libs.append(lib)

data['libraries'] = new_libs

# 保存
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ 去重完成！原始: {len(data['libraries'])} -> 去重后: {len(new_libs)}")
