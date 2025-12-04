"""
NBT 文件修改器
用于修改 Minecraft 存档的 level.dat 文件，开启作弊功能
"""
import gzip
import struct
from pathlib import Path
from typing import Optional, Tuple, Any, Dict
from utils.logger import Logger

logger = Logger().get_logger("NBTModifier")


class NBTReader:
    """简单的 NBT 读取器"""
    
    TAG_END = 0
    TAG_BYTE = 1
    TAG_SHORT = 2
    TAG_INT = 3
    TAG_LONG = 4
    TAG_FLOAT = 5
    TAG_DOUBLE = 6
    TAG_BYTE_ARRAY = 7
    TAG_STRING = 8
    TAG_LIST = 9
    TAG_COMPOUND = 10
    TAG_INT_ARRAY = 11
    TAG_LONG_ARRAY = 12
    
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
    
    def read_byte(self) -> int:
        if self.pos >= len(self.data): raise IndexError("Unexpected end of data")
        value = self.data[self.pos]
        self.pos += 1
        return value
    
    def read_short(self) -> int:
        if self.pos + 2 > len(self.data): raise IndexError("Unexpected end of data")
        value = struct.unpack('>h', self.data[self.pos:self.pos + 2])[0]
        self.pos += 2
        return value
    
    def read_int(self) -> int:
        if self.pos + 4 > len(self.data): raise IndexError("Unexpected end of data")
        value = struct.unpack('>i', self.data[self.pos:self.pos + 4])[0]
        self.pos += 4
        return value
    
    def read_long(self) -> int:
        if self.pos + 8 > len(self.data): raise IndexError("Unexpected end of data")
        value = struct.unpack('>q', self.data[self.pos:self.pos + 8])[0]
        self.pos += 8
        return value
    
    def read_float(self) -> float:
        if self.pos + 4 > len(self.data): raise IndexError("Unexpected end of data")
        value = struct.unpack('>f', self.data[self.pos:self.pos + 4])[0]
        self.pos += 4
        return value
    
    def read_double(self) -> float:
        if self.pos + 8 > len(self.data): raise IndexError("Unexpected end of data")
        value = struct.unpack('>d', self.data[self.pos:self.pos + 8])[0]
        self.pos += 8
        return value
    
    def read_string(self) -> str:
        length = self.read_short()
        if length < 0:
            length = 0
        if self.pos + length > len(self.data): raise IndexError("Unexpected end of data")
        try:
            value = self.data[self.pos:self.pos + length].decode('utf-8', errors='replace')
        except Exception:
            value = "<binary>"
        self.pos += length
        return value
    
    def read_byte_array(self) -> bytes:
        length = self.read_int()
        if length < 0: length = 0
        if self.pos + length > len(self.data): raise IndexError("Unexpected end of data")
        value = self.data[self.pos:self.pos + length]
        self.pos += length
        return value
    
    def read_int_array(self) -> list:
        length = self.read_int()
        if length < 0: length = 0
        values = []
        for _ in range(length):
            values.append(self.read_int())
        return values
    
    def read_long_array(self) -> list:
        length = self.read_int()
        if length < 0: length = 0
        values = []
        for _ in range(length):
            values.append(self.read_long())
        return values
    
    def read_tag(self, tag_type: int = None) -> Tuple[int, str, Any]:
        """读取一个完整的标签"""
        if tag_type is None:
            tag_type = self.read_byte()
        
        if tag_type == self.TAG_END:
            return (tag_type, '', None)
        
        name = self.read_string()
        value = self.read_payload(tag_type)
        return (tag_type, name, value)
    
    def read_payload(self, tag_type: int) -> Any:
        """读取标签的内容"""
        if tag_type == self.TAG_BYTE:
            return self.read_byte()
        elif tag_type == self.TAG_SHORT:
            return self.read_short()
        elif tag_type == self.TAG_INT:
            return self.read_int()
        elif tag_type == self.TAG_LONG:
            return self.read_long()
        elif tag_type == self.TAG_FLOAT:
            return self.read_float()
        elif tag_type == self.TAG_DOUBLE:
            return self.read_double()
        elif tag_type == self.TAG_BYTE_ARRAY:
            return self.read_byte_array()
        elif tag_type == self.TAG_STRING:
            return self.read_string()
        elif tag_type == self.TAG_LIST:
            list_type = self.read_byte()
            length = self.read_int()
            values = []
            for _ in range(length):
                values.append(self.read_payload(list_type))
            return {'type': list_type, 'values': values}
        elif tag_type == self.TAG_COMPOUND:
            compound = {}
            while True:
                child_type = self.read_byte()
                if child_type == self.TAG_END:
                    break
                child_name = self.read_string()
                child_value = self.read_payload(child_type)
                compound[child_name] = {'type': child_type, 'value': child_value}
            return compound
        elif tag_type == self.TAG_INT_ARRAY:
            return self.read_int_array()
        elif tag_type == self.TAG_LONG_ARRAY:
            return self.read_long_array()
        else:
            raise ValueError(f"Unknown tag type: {tag_type}")


class NBTWriter:
    """简单的 NBT 写入器"""
    
    TAG_END = 0
    TAG_BYTE = 1
    TAG_SHORT = 2
    TAG_INT = 3
    TAG_LONG = 4
    TAG_FLOAT = 5
    TAG_DOUBLE = 6
    TAG_BYTE_ARRAY = 7
    TAG_STRING = 8
    TAG_LIST = 9
    TAG_COMPOUND = 10
    TAG_INT_ARRAY = 11
    TAG_LONG_ARRAY = 12
    
    def __init__(self):
        self.data = bytearray()
    
    def write_byte(self, value: int):
        self.data.append(value & 0xFF)
    
    def write_short(self, value: int):
        self.data.extend(struct.pack('>h', value))
    
    def write_int(self, value: int):
        self.data.extend(struct.pack('>i', value))
    
    def write_long(self, value: int):
        self.data.extend(struct.pack('>q', value))
    
    def write_float(self, value: float):
        self.data.extend(struct.pack('>f', value))
    
    def write_double(self, value: float):
        self.data.extend(struct.pack('>d', value))
    
    def write_string(self, value: str):
        encoded = value.encode('utf-8')
        self.write_short(len(encoded))
        self.data.extend(encoded)
    
    def write_byte_array(self, value: bytes):
        self.write_int(len(value))
        self.data.extend(value)
    
    def write_int_array(self, value: list):
        self.write_int(len(value))
        for v in value:
            self.write_int(v)
    
    def write_long_array(self, value: list):
        self.write_int(len(value))
        for v in value:
            self.write_long(v)
    
    def write_tag(self, tag_type: int, name: str, value: Any):
        """写入一个完整的标签"""
        self.write_byte(tag_type)
        if tag_type != self.TAG_END:
            self.write_string(name)
            self.write_payload(tag_type, value)
    
    def write_payload(self, tag_type: int, value: Any):
        """写入标签的内容"""
        if tag_type == self.TAG_BYTE:
            self.write_byte(value)
        elif tag_type == self.TAG_SHORT:
            self.write_short(value)
        elif tag_type == self.TAG_INT:
            self.write_int(value)
        elif tag_type == self.TAG_LONG:
            self.write_long(value)
        elif tag_type == self.TAG_FLOAT:
            self.write_float(value)
        elif tag_type == self.TAG_DOUBLE:
            self.write_double(value)
        elif tag_type == self.TAG_BYTE_ARRAY:
            self.write_byte_array(value)
        elif tag_type == self.TAG_STRING:
            self.write_string(value)
        elif tag_type == self.TAG_LIST:
            list_type = value['type']
            values = value['values']
            self.write_byte(list_type)
            self.write_int(len(values))
            for v in values:
                self.write_payload(list_type, v)
        elif tag_type == self.TAG_COMPOUND:
            for child_name, child_data in value.items():
                child_type = child_data['type']
                child_value = child_data['value']
                self.write_byte(child_type)
                self.write_string(child_name)
                self.write_payload(child_type, child_value)
            self.write_byte(self.TAG_END)
        elif tag_type == self.TAG_INT_ARRAY:
            self.write_int_array(value)
        elif tag_type == self.TAG_LONG_ARRAY:
            self.write_long_array(value)
    
    def get_data(self) -> bytes:
        return bytes(self.data)


class NBTModifier:
    """NBT 文件修改器"""
    
    def __init__(self, minecraft_dir: Path, saves_dir: Path = None):
        """
        初始化 NBT 修改器
        
        Args:
            minecraft_dir: Minecraft 根目录
            saves_dir: 自定义存档目录路径（用于版本隔离模式）
                      如果不提供，默认使用 minecraft_dir/saves
        """
        self.minecraft_dir = Path(minecraft_dir)
        # 支持版本隔离模式：存档可能在 versions/{version}/saves 目录下
        if saves_dir:
            self.saves_dir = Path(saves_dir)
        else:
            self.saves_dir = self.minecraft_dir / "saves"
    
    def get_saves_list(self) -> list:
        """
        获取存档列表
        
        Returns:
            存档信息列表
        """
        saves = []
        
        if not self.saves_dir.exists():
            logger.warning(f"存档目录不存在: {self.saves_dir}")
            return saves
        
        for save_dir in self.saves_dir.iterdir():
            if not save_dir.is_dir():
                continue
            
            # 默认信息（即使 level.dat 不存在或解析失败，我们也列出文件夹）
            save_info = {
                'name': save_dir.name,
                'path': str(save_dir),
                'allow_commands': False,
                'game_mode': 0,
                'last_played': 0,
                'level_name': save_dir.name # 默认使用文件夹名
            }
            
            # 兼容不同版本的 level.dat 文件名
            level_dat = save_dir / "level.dat"
            if not level_dat.exists():
                level_dat = save_dir / "level.dat_old"
                if not level_dat.exists():
                    # 即使没有 level.dat，也作为一个“损坏/空”存档列出来
                    # 这样用户至少知道程序找到了文件夹
                    saves.append(save_info)
                    continue
            
            # 尝试读取存档信息
            try:
                with gzip.open(level_dat, 'rb') as f:
                    data = f.read()
                
                reader = NBTReader(data)
                
                root_type = reader.read_byte()
                if root_type == NBTReader.TAG_COMPOUND:
                    root_name = reader.read_string()
                    root_value = reader.read_payload(root_type)
                    
                    # 查找 Data 标签
                    data_tag = None
                    if 'Data' in root_value:
                        data_tag = root_value['Data']['value']
                    elif 'data' in root_value:
                        data_tag = root_value['data']['value']
                    elif 'LevelName' in root_value:
                        data_tag = root_value
                        
                    if data_tag:
                        if 'allowCommands' in data_tag:
                            save_info['allow_commands'] = bool(data_tag['allowCommands']['value'])
                        if 'GameType' in data_tag:
                            save_info['game_mode'] = data_tag['GameType']['value']
                        if 'LastPlayed' in data_tag:
                            save_info['last_played'] = data_tag['LastPlayed']['value']
                        if 'LevelName' in data_tag:
                            save_info['level_name'] = data_tag['LevelName']['value']
                
            except Exception as e:
                logger.warning(f"读取存档信息失败 {save_dir.name}: {e}")
                # 读取失败，保留默认信息（文件夹名等）
                pass
            
            saves.append(save_info)
        
        # 按最后游玩时间排序（最近的在前）
        saves.sort(key=lambda x: x.get('last_played', 0), reverse=True)
        
        return saves
    
    def enable_commands(self, save_name: str) -> Tuple[bool, str]:
        """
        为存档开启作弊功能
        
        Args:
            save_name: 存档名称
            
        Returns:
            (成功状态, 消息)
        """
        save_dir = self.saves_dir / save_name
        level_dat = save_dir / "level.dat"
        level_dat_backup = save_dir / "level.dat.backup"
        
        if not level_dat.exists():
            return False, f"存档不存在: {save_name}"
        
        try:
            # 读取原始数据
            with gzip.open(level_dat, 'rb') as f:
                data = f.read()
            
            # 备份原始文件
            with gzip.open(level_dat_backup, 'wb') as f:
                f.write(data)
            logger.info(f"已备份 level.dat 到 {level_dat_backup}")
            
            # 解析 NBT
            reader = NBTReader(data)
            tag_type, tag_name, tag_value = reader.read_tag()
            
            if tag_type != NBTReader.TAG_COMPOUND:
                return False, "无效的 level.dat 格式"
            
            # 修改 allowCommands
            data_tag = tag_value.get('Data', {}).get('value', {})
            
            if 'allowCommands' in data_tag:
                data_tag['allowCommands']['value'] = 1
                logger.info("已将 allowCommands 设置为 1")
            else:
                # 添加 allowCommands 字段
                data_tag['allowCommands'] = {'type': NBTReader.TAG_BYTE, 'value': 1}
                logger.info("已添加 allowCommands 字段并设置为 1")
            
            # 写回文件
            writer = NBTWriter()
            writer.write_tag(tag_type, tag_name, tag_value)
            
            with gzip.open(level_dat, 'wb') as f:
                f.write(writer.get_data())
            
            logger.info(f"✅ 已为存档 {save_name} 开启作弊功能")
            return True, f"已为存档 {save_name} 开启作弊功能"
            
        except Exception as e:
            logger.error(f"修改存档失败: {e}", exc_info=True)
            
            # 尝试从备份恢复
            if level_dat_backup.exists():
                try:
                    with gzip.open(level_dat_backup, 'rb') as f:
                        backup_data = f.read()
                    with gzip.open(level_dat, 'wb') as f:
                        f.write(backup_data)
                    logger.info("已从备份恢复 level.dat")
                except Exception as restore_error:
                    logger.error(f"恢复备份失败: {restore_error}")
            
            return False, f"修改存档失败: {str(e)}"
    
    def check_commands_enabled(self, save_name: str) -> bool:
        """
        检查存档是否已开启作弊
        
        Args:
            save_name: 存档名称
            
        Returns:
            是否开启作弊
        """
        save_dir = self.saves_dir / save_name
        level_dat = save_dir / "level.dat"
        
        if not level_dat.exists():
            return False
        
        try:
            with gzip.open(level_dat, 'rb') as f:
                data = f.read()
            
            reader = NBTReader(data)
            tag_type, tag_name, tag_value = reader.read_tag()
            
            if tag_type == NBTReader.TAG_COMPOUND:
                data_tag = tag_value.get('Data', {}).get('value', {})
                if 'allowCommands' in data_tag:
                    return bool(data_tag['allowCommands']['value'])
            
            return False
            
        except Exception as e:
            logger.warning(f"检查存档作弊状态失败: {e}")
            return False

