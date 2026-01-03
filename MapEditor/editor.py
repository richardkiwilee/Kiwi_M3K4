"""
地图编辑器 - 基于富甲天下4的地图设计
支持绘制主要路线、放置建筑物和城池
"""
import pygame
import json
import os
import sys
from enum import Enum
from typing import Optional, Tuple, List, Dict

# 添加父目录到路径以便导入M3K4模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 初始化Pygame
pygame.init()
pygame.font.init()

# 常量定义
BLOCK_SIZE = 30  # 每个网格单元的像素大小
GRID_WIDTH = 40  # 网格宽度
GRID_HEIGHT = 30  # 网格高度
TOOLBAR_HEIGHT = 100  # 工具栏高度
SIDEBAR_WIDTH = 200  # 侧边栏宽度

# 屏幕尺寸
SCREEN_WIDTH = BLOCK_SIZE * GRID_WIDTH + SIDEBAR_WIDTH
SCREEN_HEIGHT = BLOCK_SIZE * GRID_HEIGHT + TOOLBAR_HEIGHT

# 颜色定义
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
LIGHT_GRAY = (230, 230, 230)
DARK_GRAY = (100, 100, 100)
CREAM = (255, 253, 245)
ROAD_COLOR = (139, 90, 43)  # 棕色道路
BUILDING_COLOR = (220, 20, 60)  # 红色建筑
CITY_COLOR = (255, 215, 0)  # 金色城池（默认）
ARROW_COLOR = (255, 0, 0)  # 红色箭头
GREEN = (0, 200, 0)
RED = (255, 0, 0)

# 城池类型颜色
CITY_TYPE_COLORS = {
    "陆": (139, 90, 43),      # 棕色（陆地）
    "水": (65, 105, 225),     # 蓝色（水域）
    "林": (34, 139, 34),      # 绿色（森林）
}

# 城池类型深色（用于名称区）
CITY_TYPE_DARK_COLORS = {
    "陆": (109, 70, 33),      # 深棕色
    "水": (45, 85, 205),      # 深蓝色
    "林": (24, 109, 24),      # 深绿色
}

# 城池类型浅色（用于槽位）
CITY_TYPE_LIGHT_COLORS = {
    "陆": (189, 140, 93),     # 浅棕色
    "水": (115, 155, 255),    # 浅蓝色
    "林": (84, 189, 84),      # 浅绿色
}

# 地图元素类型
class CellType(Enum):
    EMPTY = 0
    ROAD = 1
    BUILDING = 2
    CITY = 3
    JUNCTION = 4  # 分叉路口

# 方向枚举（用于建筑旋转和箭头）
class Direction(Enum):
    UP = 0      # 向上，建筑体在入口上方
    RIGHT = 1   # 向右，建筑体在入口右方
    DOWN = 2    # 向下，建筑体在入口下方
    LEFT = 3    # 向左，建筑体在入口左方

class MapCell:
    """地图单元格"""
    def __init__(self):
        self.type = CellType.EMPTY
        self.building_slots = 1  # 城池槽位数（1-3）
        self.direction = Direction.UP  # 建筑/城池的方向（建筑体相对于入口的方向）
        self.arrow_direction = Direction.UP  # 分叉路口的箭头方向
        self.building_id = None  # 建筑物/城池的ID（用于标识同一个建筑的多个格子）
        self.is_entrance = False  # 是否是入口格子
        self.city_name = ""  # 城池名称
        self.city_type = "陆"  # 城池类型（陆/水/林）
        
    def to_dict(self):
        return {
            'type': self.type.value,
            'building_slots': self.building_slots,
            'direction': self.direction.value,
            'arrow_direction': self.arrow_direction.value,
            'building_id': self.building_id,
            'is_entrance': self.is_entrance,
            'city_name': self.city_name,
            'city_type': self.city_type
        }
    
    @staticmethod
    def from_dict(data):
        cell = MapCell()
        cell.type = CellType(data.get('type', 0))
        cell.building_slots = data.get('building_slots', 1)
        cell.direction = Direction(data.get('direction', 0))
        cell.arrow_direction = Direction(data.get('arrow_direction', 0))
        cell.building_id = data.get('building_id')
        cell.is_entrance = data.get('is_entrance', False)
        cell.city_name = data.get('city_name', '')
        cell.city_type = data.get('city_type', '陆')
        return cell

class Tool(Enum):
    """工具类型"""
    ROAD = 0
    BUILDING = 1
    CITY = 2
    JUNCTION = 3
    ERASER = 4

class MapEditor:
    """地图编辑器主类"""
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('地图编辑器 - 富甲天下4')
        
        # 初始化地图网格
        self.grid: List[List[MapCell]] = [[MapCell() for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        
        # 编辑器状态
        self.current_tool = Tool.ROAD
        self.is_drawing = False
        self.next_building_id = 1  # 下一个建筑物ID
        self.selected_building_id = None  # 当前选中的建筑物ID
        
        # 预览状态（用于建筑/城池工具）
        self.preview_direction = Direction.UP  # 预览的方向
        self.preview_slots = 1  # 预览城池的槽位数
        
        # 建筑和城池名称映射（ID -> 名称）
        self.building_names = {}  # {building_id: name}
        self.city_names = {}  # {city_id: name}
        self.city_types = {}  # {city_id: type} 城池类型
        
        # 字体 - 使用系统字体支持中文
        try:
            # 尝试使用Windows系统中文字体
            self.font = pygame.font.SysFont('microsoftyahei', 24)
            self.small_font = pygame.font.SysFont('microsoftyahei', 18)
        except:
            try:
                # 备选方案：使用SimHei字体
                self.font = pygame.font.SysFont('simhei', 24)
                self.small_font = pygame.font.SysFont('simhei', 18)
            except:
                # 最后备选：使用任何可用的中文字体
                chinese_fonts = ['microsoftyahei', 'simhei', 'simsun', 'microsoftyaheiui', 'dengxian', 'fangsong', 'kaiti']
                font_found = False
                for font_name in chinese_fonts:
                    try:
                        self.font = pygame.font.SysFont(font_name, 24)
                        self.small_font = pygame.font.SysFont(font_name, 18)
                        font_found = True
                        break
                    except:
                        continue
                if not font_found:
                    # 如果都失败了，使用默认字体（可能不支持中文）
                    self.font = pygame.font.Font(None, 24)
                    self.small_font = pygame.font.Font(None, 18)
                    print("警告: 未找到支持中文的字体，中文可能无法正确显示")
        
        # 按钮定义
        self.buttons = self._create_buttons()
        
        # 运行状态
        self.running = True
        self.clock = pygame.time.Clock()
        
    def _create_buttons(self) -> List[Dict]:
        """创建工具栏按钮"""
        buttons = []
        button_width = 100
        button_height = 40
        margin = 10
        
        tools = [
            (Tool.ROAD, "道路", ROAD_COLOR),
            (Tool.BUILDING, "建筑", BUILDING_COLOR),
            (Tool.CITY, "城池", CITY_COLOR),
            (Tool.JUNCTION, "分叉", ARROW_COLOR),
            (Tool.ERASER, "擦除", GRAY)
        ]
        
        for i, (tool, text, color) in enumerate(tools):
            x = margin + i * (button_width + margin)
            y = SCREEN_HEIGHT - TOOLBAR_HEIGHT + 20
            buttons.append({
                'rect': pygame.Rect(x, y, button_width, button_height),
                'tool': tool,
                'text': text,
                'color': color
            })
        
        # 保存和加载按钮
        save_x = SCREEN_WIDTH - SIDEBAR_WIDTH + 20
        buttons.append({
            'rect': pygame.Rect(save_x, SCREEN_HEIGHT - TOOLBAR_HEIGHT + 20, 80, 30),
            'action': 'save',
            'text': '保存',
            'color': GREEN
        })
        buttons.append({
            'rect': pygame.Rect(save_x + 90, SCREEN_HEIGHT - TOOLBAR_HEIGHT + 20, 80, 30),
            'action': 'load',
            'text': '加载',
            'color': GRAY
        })
        
        return buttons
    
    def get_grid_pos(self, mouse_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """将鼠标位置转换为网格坐标"""
        x, y = mouse_pos
        if x < 0 or x >= BLOCK_SIZE * GRID_WIDTH or y < 0 or y >= BLOCK_SIZE * GRID_HEIGHT:
            return None
        grid_x = x // BLOCK_SIZE
        grid_y = y // BLOCK_SIZE
        return (grid_x, grid_y)
    
    def handle_mouse_down(self, pos: Tuple[int, int], button: int):
        """处理鼠标按下事件"""
        # 检查是否点击了按钮
        for btn in self.buttons:
            if btn['rect'].collidepoint(pos):
                if 'tool' in btn:
                    self.current_tool = btn['tool']
                elif 'action' in btn:
                    if btn['action'] == 'save':
                        self.save_map()
                    elif btn['action'] == 'load':
                        self.load_map()
                return
        
        # 网格操作
        grid_pos = self.get_grid_pos(pos)
        if grid_pos:
            grid_x, grid_y = grid_pos
            
            if self.current_tool == Tool.ROAD:
                self.is_drawing = True
                # 只有在空地或已有道路上才能绘制道路
                cell = self.grid[grid_y][grid_x]
                if cell.type == CellType.EMPTY or cell.type == CellType.ROAD:
                    cell.type = CellType.ROAD
            elif self.current_tool == Tool.ERASER:
                self.is_drawing = True
                # 删除整个建筑物/城池
                cell = self.grid[grid_y][grid_x]
                if cell.building_id:
                    self.remove_building(cell.building_id)
                else:
                    self.grid[grid_y][grid_x] = MapCell()
            elif self.current_tool in [Tool.BUILDING, Tool.CITY]:
                # 点击放置建筑或选中已有建筑
                cell = self.grid[grid_y][grid_x]
                if cell.building_id:
                    # 选中已有建筑
                    self.selected_building_id = cell.building_id
                else:
                    # 放置建筑
                    if self.current_tool == Tool.BUILDING:
                        self.place_building(grid_x, grid_y, self.preview_direction)
                    elif self.current_tool == Tool.CITY:
                        self.place_city(grid_x, grid_y, self.preview_slots, self.preview_direction)
            elif self.current_tool == Tool.JUNCTION:
                cell = self.grid[grid_y][grid_x]
                cell.type = CellType.JUNCTION
                cell.arrow_direction = Direction.UP
    
    def handle_mouse_motion(self, pos: Tuple[int, int]):
        """处理鼠标移动事件"""
        # 更新预览（如果处于预览模式）
        # 预览会在draw方法中绘制
        
        if self.is_drawing:
            grid_pos = self.get_grid_pos(pos)
            if grid_pos:
                grid_x, grid_y = grid_pos
                if self.current_tool == Tool.ROAD:
                    # 只有在空地或已有道路上才能绘制道路
                    cell = self.grid[grid_y][grid_x]
                    if cell.type == CellType.EMPTY or cell.type == CellType.ROAD:
                        cell.type = CellType.ROAD
                elif self.current_tool == Tool.ERASER:
                    self.grid[grid_y][grid_x] = MapCell()
    
    def handle_mouse_up(self, pos: Tuple[int, int]):
        """处理鼠标释放事件"""
        self.is_drawing = False
    
    def handle_mouse_wheel(self, y: int):
        """处理鼠标滚轮事件"""
        # 如果当前工具是城池，调整预览槽位数
        if self.current_tool == Tool.CITY:
            old_slots = self.preview_slots
            new_slots = max(1, min(3, old_slots + (1 if y > 0 else -1)))
            if new_slots != old_slots:
                self.preview_slots = new_slots
                return
        
        # 否则，尝试调整已有城池的槽位数
        mouse_pos = pygame.mouse.get_pos()
        grid_pos = self.get_grid_pos(mouse_pos)
        
        if grid_pos:
            grid_x, grid_y = grid_pos
            cell = self.grid[grid_y][grid_x]
            
            # 只有城池可以修改槽位数
            if cell.type == CellType.CITY and cell.building_id:
                old_slots = cell.building_slots
                new_slots = max(1, min(3, old_slots + (1 if y > 0 else -1)))
                
                if new_slots != old_slots:
                    # 重新放置城池
                    self.update_city_slots(cell.building_id, new_slots)
    
    def handle_key_down(self, key: int):
        """处理键盘按下事件"""
        if key == pygame.K_r:
            # R键旋转预览或已选中的建筑
            if self.current_tool in [Tool.BUILDING, Tool.CITY]:
                # 旋转预览方向
                self.preview_direction = Direction((self.preview_direction.value + 1) % 4)
            elif self.selected_building_id:
                # 旋转已选中的建筑
                self.rotate_building(self.selected_building_id)
                self.selected_building_id = None
        
        elif key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
            # Ctrl+S 保存
            self.save_map()
        
        elif key == pygame.K_o and pygame.key.get_mods() & pygame.KMOD_CTRL:
            # Ctrl+O 加载
            self.load_map()
    
    def place_building(self, entrance_x: int, entrance_y: int, direction: Direction = Direction.UP):
        """
        放置建筑物
        建筑物占地：2格入口 + 2x2正方形 = 共6格
        入口在道路上（不占面积），建筑体根据方向放置
        """
        building_id = self.next_building_id
        self.next_building_id += 1
        
        # 检查是否有足够空间
        if not self.can_place_building(entrance_x, entrance_y, direction):
            print("无法放置建筑：空间不足")
            return
        
        # 标记入口（2格，不修改道路类型）
        entrance_offsets = self.get_entrance_offsets(direction)
        for dx, dy in entrance_offsets:
            x = entrance_x + dx
            y = entrance_y + dy
            if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                cell = self.grid[y][x]
                cell.building_id = building_id
                cell.is_entrance = True
                cell.direction = direction
        
        # 放置建筑体（2x2正方形）
        offsets = self.get_building_offsets(direction)
        for dx, dy in offsets:
            x = entrance_x + dx
            y = entrance_y + dy
            if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                cell = self.grid[y][x]
                cell.type = CellType.BUILDING
                cell.building_id = building_id
                cell.is_entrance = False
                cell.direction = direction
    
    def place_city(self, entrance_x: int, entrance_y: int, building_slots: int = 1, direction: Direction = Direction.UP, city_type: str = "陆"):
        """
        放置城池
        城池占地：2格入口 + 2x(1+slots)格城池体 = 共6-10格
        入口在道路上（不占面积）
        城池体是矩形，宽度与入口一致（2格）
        city_type: 城池类型（陆/水/林）
        """
        building_id = self.next_building_id
        self.next_building_id += 1
        
        # 保存城池类型
        self.city_types[building_id] = city_type
        
        building_slots = max(1, min(3, building_slots))
        
        # 检查是否有足够空间
        if not self.can_place_city(entrance_x, entrance_y, direction, building_slots):
            print("无法放置城池：空间不足")
            return
        
        # 标记入口（2格，不修改道路类型）
        entrance_offsets = self.get_entrance_offsets(direction)
        for dx, dy in entrance_offsets:
            x = entrance_x + dx
            y = entrance_y + dy
            if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                cell = self.grid[y][x]
                cell.building_id = building_id
                cell.is_entrance = True
                cell.direction = direction
                cell.building_slots = building_slots
        
        # 放置城池体（名称区 + 槽位）
        offsets = self.get_city_offsets(direction, building_slots)
        for i, (dx, dy) in enumerate(offsets):
            x = entrance_x + dx
            y = entrance_y + dy
            if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                cell = self.grid[y][x]
                cell.type = CellType.CITY
                cell.building_id = building_id
                cell.is_entrance = False
                cell.direction = direction
                cell.building_slots = building_slots
                cell.city_type = city_type
                # 前2个格子是名称区（第一行）
                if i < 2:
                    cell.city_name = "城池"
    
    def get_entrance_offsets(self, direction: Direction) -> list:
        """获取入口相对于第一个入口格的偏移量（2格）"""
        if direction == Direction.UP or direction == Direction.DOWN:
            # 垂直方向：入口水平排列
            return [(0, 0), (1, 0)]
        else:  # LEFT or RIGHT
            # 水平方向：入口垂直排列
            return [(0, 0), (0, 1)]
    
    def get_building_offsets(self, direction: Direction) -> list:
        """获取建筑体相对于第一个入口格的偏移量（2x2正方形）"""
        if direction == Direction.UP:
            # 入口水平排列(0,0)(1,0)，建筑体在上方
            return [(0, -1), (1, -1), (0, -2), (1, -2)]
        elif direction == Direction.RIGHT:
            # 入口垂直排列(0,0)(0,1)，建筑体在右方
            return [(1, 0), (2, 0), (1, 1), (2, 1)]
        elif direction == Direction.DOWN:
            # 入口水平排列(0,0)(1,0)，建筑体在下方
            return [(0, 1), (1, 1), (0, 2), (1, 2)]
        else:  # LEFT
            # 入口垂直排列(0,0)(0,1)，建筑体在左方
            return [(-1, 0), (-2, 0), (-1, 1), (-2, 1)]
    
    def get_city_offsets(self, direction: Direction, building_slots: int) -> list:
        """获取城池体相对于第一个入口格的偏移量（名称区 + 槽位）
        城池体应该是矩形，与入口宽度一致
        """
        offsets = []
        if direction == Direction.UP:
            # 入口水平排列(0,0)(1,0)，城池体在上方
            # 每一行都是2格宽，向上扩展
            for i in range(1 + building_slots):
                offsets.append((0, -(i + 1)))
                offsets.append((1, -(i + 1)))
        elif direction == Direction.RIGHT:
            # 入口垂直排列(0,0)(0,1)，城池体在右方
            # 每一列都是2格高，向右扩展
            for i in range(1 + building_slots):
                offsets.append((i + 1, 0))
                offsets.append((i + 1, 1))
        elif direction == Direction.DOWN:
            # 入口水平排列(0,0)(1,0)，城池体在下方
            # 每一行都是2格宽，向下扩展
            for i in range(1 + building_slots):
                offsets.append((0, i + 1))
                offsets.append((1, i + 1))
        else:  # LEFT
            # 入口垂直排列(0,0)(0,1)，城池体在左方
            # 每一列都是2格高，向左扩展
            for i in range(1 + building_slots):
                offsets.append((-(i + 1), 0))
                offsets.append((-(i + 1), 1))
        return offsets
    
    def can_place_building(self, entrance_x: int, entrance_y: int, direction: Direction) -> bool:
        """检查是否可以放置建筑物"""
        # 检查入口位置（2格）是否都是道路，且没有其他入口
        entrance_offsets = self.get_entrance_offsets(direction)
        for dx, dy in entrance_offsets:
            x = entrance_x + dx
            y = entrance_y + dy
            if x < 0 or x >= GRID_WIDTH or y < 0 or y >= GRID_HEIGHT:
                return False
            cell = self.grid[y][x]
            if cell.type != CellType.ROAD:
                return False
            if cell.is_entrance:  # 已经有入口了
                return False
        
        # 检查建筑体位置
        offsets = self.get_building_offsets(direction)
        for dx, dy in offsets:
            x = entrance_x + dx
            y = entrance_y + dy
            if x < 0 or x >= GRID_WIDTH or y < 0 or y >= GRID_HEIGHT:
                return False
            if self.grid[y][x].type != CellType.EMPTY:
                return False
        return True
    
    def can_place_city(self, entrance_x: int, entrance_y: int, direction: Direction, building_slots: int) -> bool:
        """检查是否可以放置城池"""
        # 检查入口位置（2格）是否都是道路，且没有其他入口
        entrance_offsets = self.get_entrance_offsets(direction)
        for dx, dy in entrance_offsets:
            x = entrance_x + dx
            y = entrance_y + dy
            if x < 0 or x >= GRID_WIDTH or y < 0 or y >= GRID_HEIGHT:
                return False
            cell = self.grid[y][x]
            if cell.type != CellType.ROAD:
                return False
            if cell.is_entrance:
                return False
        
        # 检查城池体位置
        offsets = self.get_city_offsets(direction, building_slots)
        for dx, dy in offsets:
            x = entrance_x + dx
            y = entrance_y + dy
            if x < 0 or x >= GRID_WIDTH or y < 0 or y >= GRID_HEIGHT:
                return False
            if self.grid[y][x].type != CellType.EMPTY:
                return False
        return True
    
    def remove_building(self, building_id: int):
        """删除整个建筑物/城池，但保留入口所在的道路"""
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = self.grid[y][x]
                if cell.building_id == building_id:
                    if cell.is_entrance and cell.type == CellType.ROAD:
                        # 入口在道路上，只清除入口标记，保留道路
                        cell.building_id = None
                        cell.is_entrance = False
                        cell.direction = Direction.UP
                        cell.building_slots = 1
                        cell.city_name = ""
                    else:
                        # 非入口格子，完全清除
                        self.grid[y][x] = MapCell()
    
    def rotate_building(self, building_id: int):
        """旋转建筑物/城池的方向（顺时针旋转90度）"""
        # 找到建筑物的所有单元格
        cells = []
        building_type = None
        building_slots = 1
        entrance_pos = None
        old_direction = Direction.UP
        
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = self.grid[y][x]
                if cell.building_id == building_id:
                    cells.append((x, y, cell))
                    if building_type is None:
                        building_type = cell.type
                        building_slots = cell.building_slots
                        old_direction = cell.direction
                    if cell.is_entrance and entrance_pos is None:
                        entrance_pos = (x, y)
        
        if not cells or entrance_pos is None:
            return
        
        # 删除旧建筑
        self.remove_building(building_id)
        
        # 获取新的方向（顺时针旋转90度）
        new_direction = Direction((old_direction.value + 1) % 4)
        
        # 重新放置
        entrance_x, entrance_y = entrance_pos
        if building_type == CellType.BUILDING:
            if self.can_place_building(entrance_x, entrance_y, new_direction):
                # 使用相同buildingID
                self.next_building_id = building_id
                self.place_building(entrance_x, entrance_y, new_direction)
                self.next_building_id = building_id + 1
            else:
                # 如果无法放置，恢复原来的方向
                self.next_building_id = building_id
                self.place_building(entrance_x, entrance_y, old_direction)
                self.next_building_id = building_id + 1
                print("空间不足，无法旋转")
        elif building_type == CellType.CITY:
            if self.can_place_city(entrance_x, entrance_y, new_direction, building_slots):
                self.next_building_id = building_id
                self.place_city(entrance_x, entrance_y, building_slots, new_direction)
                self.next_building_id = building_id + 1
            else:
                # 如果无法放置，恢复原来的方向
                self.next_building_id = building_id
                self.place_city(entrance_x, entrance_y, building_slots, old_direction)
                self.next_building_id = building_id + 1
                print("空间不足，无法旋转")
    
    def update_city_slots(self, building_id: int, new_slots: int):
        """更新城池的建筑槽位数"""
        # 找到城池的入口位置
        entrance_pos = None
        old_direction = Direction.UP
        
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = self.grid[y][x]
                if cell.building_id == building_id and cell.is_entrance:
                    entrance_pos = (x, y)
                    old_direction = cell.direction
                    break
            if entrance_pos:
                break
        
        if entrance_pos is None:
            return
        
        # 删除旧城池
        self.remove_building(building_id)
        
        # 重新放置城池
        entrance_x, entrance_y = entrance_pos
        if self.can_place_city(entrance_x, entrance_y, old_direction, new_slots):
            self.next_building_id = building_id
            self.place_city(entrance_x, entrance_y, new_slots, old_direction)
            self.next_building_id = building_id + 1
        else:
            # 如果无法放置，恢复原来的槽位数
            old_slots = new_slots - 1 if new_slots > 1 else new_slots + 1
            self.next_building_id = building_id
            self.place_city(entrance_x, entrance_y, old_slots, old_direction)
            self.next_building_id = building_id + 1
            print(f"空间不足，无法将槽位数修改为{new_slots}")
    
    def draw_grid(self):
        """绘制网格"""
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                rect = pygame.Rect(x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
                cell = self.grid[y][x]
                
                # 绘制单元格背景
                if cell.type == CellType.ROAD:
                    pygame.draw.rect(self.screen, ROAD_COLOR, rect)
                elif cell.type == CellType.BUILDING:
                    # 区分入口和建筑体
                    if cell.is_entrance:
                        pygame.draw.rect(self.screen, BUILDING_COLOR, rect)
                        # 绘制入口标记
                        text_surf = self.small_font.render("入", True, WHITE)
                        self.screen.blit(text_surf, (rect.x + 5, rect.y + 5))
                    else:
                        # 建筑体使用深红色
                        darker_red = (180, 20, 50)
                        pygame.draw.rect(self.screen, darker_red, rect)
                        # 显示建筑名称（每个格子显示一个字）
                        if cell.building_id:
                            full_name = self.building_names.get(cell.building_id, f'B{cell.building_id}')
                            # 确保名称是2个字
                            if len(full_name) >= 2:
                                # 判断当前格子是建筑体的第几个格子
                                # 通过检查左边和上边是否有相同building_id的建筑格来判断
                                char_index = 0
                                # 检查左边
                                if x > 0 and self.grid[y][x-1].building_id == cell.building_id and self.grid[y][x-1].type == CellType.BUILDING and not self.grid[y][x-1].is_entrance:
                                    char_index = 1
                                # 检查上边
                                elif y > 0 and self.grid[y-1][x].building_id == cell.building_id and self.grid[y-1][x].type == CellType.BUILDING and not self.grid[y-1][x].is_entrance:
                                    # 如果上边有建筑，则当前是第二行，需要再检查左边
                                    if x > 0 and self.grid[y][x-1].building_id == cell.building_id and self.grid[y][x-1].type == CellType.BUILDING and not self.grid[y][x-1].is_entrance:
                                        char_index = 3  # 右下角
                                    else:
                                        char_index = 2  # 左下角
                                
                                # 只显示前2个字（左上和右上）
                                if char_index < 2 and char_index < len(full_name):
                                    char = full_name[char_index]
                                    text_surf = self.font.render(char, True, WHITE)
                                    text_rect = text_surf.get_rect(center=(rect.centerx, rect.centery))
                                    self.screen.blit(text_surf, text_rect)
                elif cell.type == CellType.CITY:
                    # 获取城池类型和对应颜色
                    city_type = cell.city_type
                    base_color = CITY_TYPE_COLORS.get(city_type, CITY_COLOR)
                    dark_color = CITY_TYPE_DARK_COLORS.get(city_type, (225, 185, 0))
                    light_color = CITY_TYPE_LIGHT_COLORS.get(city_type, (255, 235, 100))
                    
                    if cell.is_entrance:
                        pygame.draw.rect(self.screen, base_color, rect)
                        # 绘制入口标记
                        text_surf = self.small_font.render("入", True, WHITE)
                        self.screen.blit(text_surf, (rect.x + 5, rect.y + 5))
                    elif cell.city_name:
                        # 名称区 - 使用深色
                        pygame.draw.rect(self.screen, dark_color, rect)
                        # 显示城池名称（每个格子显示一个字）
                        # 获取完整城池名称
                        if cell.building_id:
                            full_name = self.city_names.get(cell.building_id, f'C{cell.building_id}')
                            # 确保名称是2个字
                            if len(full_name) >= 2:
                                # 判断当前格子是名称区的第几个格子
                                # 通过检查左边和上边是否有相同building_id的名称格来判断
                                char_index = 0
                                if x > 0 and self.grid[y][x-1].building_id == cell.building_id and self.grid[y][x-1].city_name:
                                    char_index = 1
                                elif y > 0 and self.grid[y-1][x].building_id == cell.building_id and self.grid[y-1][x].city_name:
                                    char_index = 1
                                
                                # 显示对应的字符
                                if char_index < len(full_name):
                                    char = full_name[char_index]
                                    text_surf = self.font.render(char, True, WHITE)
                                    text_rect = text_surf.get_rect(center=(rect.centerx, rect.centery))
                                    self.screen.blit(text_surf, text_rect)
                    else:
                        # 建筑槽位 - 使用浅色，不显示"槽"字
                        pygame.draw.rect(self.screen, light_color, rect)
                elif cell.type == CellType.JUNCTION:
                    pygame.draw.rect(self.screen, ROAD_COLOR, rect)
                    # 绘制箭头
                    self.draw_arrow(rect, cell.arrow_direction)
                else:
                    pygame.draw.rect(self.screen, CREAM, rect)
                
                # 绘制网格线
                pygame.draw.rect(self.screen, LIGHT_GRAY, rect, 1)
                
                # 城池特殊处理：粗边框 + 内部细线 + 名称区中间无线
                if cell.type == CellType.CITY and not cell.is_entrance:
                    # 检查是否是城池的边界
                    is_left_edge = x == 0 or self.grid[y][x-1].building_id != cell.building_id or self.grid[y][x-1].type != CellType.CITY
                    is_right_edge = x == GRID_WIDTH-1 or self.grid[y][x+1].building_id != cell.building_id or self.grid[y][x+1].type != CellType.CITY
                    is_top_edge = y == 0 or self.grid[y-1][x].building_id != cell.building_id or self.grid[y-1][x].type != CellType.CITY
                    is_bottom_edge = y == GRID_HEIGHT-1 or self.grid[y+1][x].building_id != cell.building_id or self.grid[y+1][x].type != CellType.CITY
                    
                    # 绘制粗边框（3像素）
                    if is_left_edge:
                        pygame.draw.line(self.screen, BLACK, (rect.left, rect.top), (rect.left, rect.bottom), 3)
                    if is_right_edge:
                        pygame.draw.line(self.screen, BLACK, (rect.right, rect.top), (rect.right, rect.bottom), 3)
                    if is_top_edge:
                        pygame.draw.line(self.screen, BLACK, (rect.left, rect.top), (rect.right, rect.top), 3)
                    if is_bottom_edge:
                        pygame.draw.line(self.screen, BLACK, (rect.left, rect.bottom), (rect.right, rect.bottom), 3)
                    
                    # 绘制内部细线（1像素），但跳过名称区中间的线
                    # 检查右边是否是同一城池的名称区
                    if not is_right_edge:
                        right_cell = self.grid[y][x+1]
                        # 如果当前和右边都是名称区，则不画线
                        if not (cell.city_name and right_cell.city_name):
                            pygame.draw.line(self.screen, DARK_GRAY, (rect.right, rect.top), (rect.right, rect.bottom), 1)
                    
                    # 检查下边是否是同一城池
                    if not is_bottom_edge:
                        pygame.draw.line(self.screen, DARK_GRAY, (rect.left, rect.bottom), (rect.right, rect.bottom), 1)
                
                # 高亮选中的建筑物
                if self.selected_building_id and cell.building_id == self.selected_building_id:
                    pygame.draw.rect(self.screen, GREEN, rect, 3)
    
    def draw_arrow(self, rect: pygame.Rect, direction: Direction):
        """在单元格中绘制箭头"""
        center_x = rect.centerx
        center_y = rect.centery
        size = BLOCK_SIZE // 3
        
        if direction == Direction.UP:
            points = [(center_x, center_y - size), 
                     (center_x - size//2, center_y + size//2),
                     (center_x + size//2, center_y + size//2)]
        elif direction == Direction.RIGHT:
            points = [(center_x + size, center_y),
                     (center_x - size//2, center_y - size//2),
                     (center_x - size//2, center_y + size//2)]
        elif direction == Direction.DOWN:
            points = [(center_x, center_y + size),
                     (center_x - size//2, center_y - size//2),
                     (center_x + size//2, center_y - size//2)]
        else:  # LEFT
            points = [(center_x - size, center_y),
                     (center_x + size//2, center_y - size//2),
                     (center_x + size//2, center_y + size//2)]
        
        pygame.draw.polygon(self.screen, ARROW_COLOR, points)
    
    def draw_toolbar(self):
        """绘制工具栏"""
        toolbar_rect = pygame.Rect(0, SCREEN_HEIGHT - TOOLBAR_HEIGHT, SCREEN_WIDTH, TOOLBAR_HEIGHT)
        pygame.draw.rect(self.screen, DARK_GRAY, toolbar_rect)
        
        # 绘制按钮
        for btn in self.buttons:
            color = btn['color']
            # 如果是当前选中的工具，高亮显示
            if 'tool' in btn and btn['tool'] == self.current_tool:
                pygame.draw.rect(self.screen, WHITE, btn['rect'].inflate(4, 4))
            
            pygame.draw.rect(self.screen, color, btn['rect'])
            pygame.draw.rect(self.screen, BLACK, btn['rect'], 2)
            
            # 绘制按钮文字
            text_surf = self.font.render(btn['text'], True, BLACK)
            text_rect = text_surf.get_rect(center=btn['rect'].center)
            self.screen.blit(text_surf, text_rect)
    
    def draw_sidebar(self):
        """绘制侧边栏"""
        sidebar_rect = pygame.Rect(SCREEN_WIDTH - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, SCREEN_HEIGHT - TOOLBAR_HEIGHT)
        pygame.draw.rect(self.screen, WHITE, sidebar_rect)
        pygame.draw.line(self.screen, BLACK, (SCREEN_WIDTH - SIDEBAR_WIDTH, 0), 
                        (SCREEN_WIDTH - SIDEBAR_WIDTH, SCREEN_HEIGHT - TOOLBAR_HEIGHT), 2)
        
        # 显示当前工具信息
        y_offset = 20
        title = self.font.render("当前工具:", True, BLACK)
        self.screen.blit(title, (SCREEN_WIDTH - SIDEBAR_WIDTH + 10, y_offset))
        y_offset += 30
        
        tool_name = self.current_tool.name
        tool_text = self.font.render(tool_name, True, BLACK)
        self.screen.blit(tool_text, (SCREEN_WIDTH - SIDEBAR_WIDTH + 10, y_offset))
        y_offset += 40
        
        # 显示操作说明
        instructions = [
            "操作说明:",
            "",
            "道路: 点击拖拽绘制",
            "建筑/城池: 点击开启预览",
            "R键: 旋转预览方向",
            "点击放置建筑",
            "分叉: 点击放置",
            "擦除: 点击擦除",
            "",
            "城池操作:",
            "滚轮: 调整槽位(1-3)",
            "选中工具时调整预览",
            "或鼠标在城池上调整",
            "",
            "快捷键:",
            "Ctrl+S: 保存",
            "Ctrl+O: 加载"
        ]
        
        for instruction in instructions:
            text = self.small_font.render(instruction, True, BLACK)
            self.screen.blit(text, (SCREEN_WIDTH - SIDEBAR_WIDTH + 10, y_offset))
            y_offset += 20
    
    def draw(self):
        """绘制整个界面"""
        self.screen.fill(WHITE)
        self.draw_grid()
        self.draw_toolbar()
        self.draw_sidebar()
        
        # 绘制预览虚影（当选中建筑/城池工具时）
        if self.current_tool in [Tool.BUILDING, Tool.CITY]:
            mouse_pos = pygame.mouse.get_pos()
            grid_pos = self.get_grid_pos(mouse_pos)
            if grid_pos:
                grid_x, grid_y = grid_pos
                self.draw_preview(grid_x, grid_y)
        
        pygame.display.flip()
    
    def draw_preview(self, entrance_x: int, entrance_y: int):
        """绘制建筑/城池的预览虚影"""
        alpha = 128  # 半透明
        
        if self.current_tool == Tool.BUILDING:
            # 检查是否可以放置
            can_place = self.can_place_building(entrance_x, entrance_y, self.preview_direction)
            color = (0, 255, 0, alpha) if can_place else (255, 0, 0, alpha)
            
            # 绘制入口（2格）
            entrance_offsets = self.get_entrance_offsets(self.preview_direction)
            for dx, dy in entrance_offsets:
                x = entrance_x + dx
                y = entrance_y + dy
                if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                    rect = pygame.Rect(x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
                    s = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
                    s.fill(color)
                    self.screen.blit(s, rect)
                    pygame.draw.rect(self.screen, BLACK, rect, 2)
            
            # 绘制建筑体
            offsets = self.get_building_offsets(self.preview_direction)
            for dx, dy in offsets:
                x = entrance_x + dx
                y = entrance_y + dy
                if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                    rect = pygame.Rect(x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
                    s = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
                    s.fill(color)
                    self.screen.blit(s, rect)
                    pygame.draw.rect(self.screen, BLACK, rect, 2)
        
        elif self.current_tool == Tool.CITY:
            # 检查是否可以放置
            can_place = self.can_place_city(entrance_x, entrance_y, self.preview_direction, self.preview_slots)
            color = (255, 215, 0, alpha) if can_place else (255, 0, 0, alpha)
            
            # 绘制入口（2格）
            entrance_offsets = self.get_entrance_offsets(self.preview_direction)
            for dx, dy in entrance_offsets:
                x = entrance_x + dx
                y = entrance_y + dy
                if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                    rect = pygame.Rect(x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
                    s = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
                    s.fill(color)
                    self.screen.blit(s, rect)
                    pygame.draw.rect(self.screen, BLACK, rect, 2)
            
            # 绘制城池体
            offsets = self.get_city_offsets(self.preview_direction, self.preview_slots)
            for dx, dy in offsets:
                x = entrance_x + dx
                y = entrance_y + dy
                if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                    rect = pygame.Rect(x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
                    s = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
                    s.fill(color)
                    self.screen.blit(s, rect)
                    pygame.draw.rect(self.screen, BLACK, rect, 2)
    
    def save_map(self, filename: str = "map.json"):
        """保存地图到文件（压缩格式）"""
        roads = []
        buildings = {}
        cities = {}
        
        # 遍历网格收集数据
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = self.grid[y][x]
                
                # 收集道路单元格
                if cell.type == CellType.ROAD:
                    road_cell = {
                        'x': x,
                        'y': y,
                        'entry': None,
                        'id': None,
                        'direction': None
                    }
                    
                    # 检查是否是入口
                    if cell.is_entrance and cell.building_id:
                        # 查找建筑类型
                        for dy in range(GRID_HEIGHT):
                            for dx in range(GRID_WIDTH):
                                check_cell = self.grid[dy][dx]
                                if check_cell.building_id == cell.building_id:
                                    if check_cell.type == CellType.BUILDING:
                                        road_cell['entry'] = 1  # 建筑入口
                                        road_cell['id'] = cell.building_id
                                        break
                                    elif check_cell.type == CellType.CITY:
                                        road_cell['entry'] = 2  # 城池入口
                                        road_cell['id'] = cell.building_id
                                        break
                            if road_cell['entry']:
                                break
                    
                    roads.append(road_cell)
                
                # 收集分叉口
                elif cell.type == CellType.JUNCTION:
                    road_cell = {
                        'x': x,
                        'y': y,
                        'entry': None,
                        'id': None,
                        'direction': cell.arrow_direction.value  # 分叉方向
                    }
                    roads.append(road_cell)
                
                # 收集建筑物
                elif cell.type == CellType.BUILDING and cell.building_id:
                    if cell.building_id not in buildings:
                        # 查找入口位置和方向
                        entrance_x, entrance_y, direction = None, None, Direction.UP
                        for dy in range(GRID_HEIGHT):
                            for dx in range(GRID_WIDTH):
                                check_cell = self.grid[dy][dx]
                                if check_cell.building_id == cell.building_id and check_cell.is_entrance:
                                    entrance_x, entrance_y = dx, dy
                                    direction = check_cell.direction
                                    break
                            if entrance_x is not None:
                                break
                        
                        buildings[cell.building_id] = {
                            'id': cell.building_id,
                            'name': f'建筑{cell.building_id}',
                            'x': entrance_x,
                            'y': entrance_y,
                            'direction': direction.value
                        }
                
                # 收集城池
                elif cell.type == CellType.CITY and cell.building_id:
                    if cell.building_id not in cities:
                        # 查找入口位置和方向
                        entrance_x, entrance_y, direction = None, None, Direction.UP
                        slots_count = cell.building_slots
                        for dy in range(GRID_HEIGHT):
                            for dx in range(GRID_WIDTH):
                                check_cell = self.grid[dy][dx]
                                if check_cell.building_id == cell.building_id and check_cell.is_entrance:
                                    entrance_x, entrance_y = dx, dy
                                    direction = check_cell.direction
                                    break
                            if entrance_x is not None:
                                break
                        
                        # 初始化城池数据
                        city_name = self.city_names.get(cell.building_id, f'城池{cell.building_id}')
                        city_type = self.city_types.get(cell.building_id, '陆')
                        cities[cell.building_id] = {
                            'id': cell.building_id,
                            'name': city_name,
                            'type': city_type,
                            'x': entrance_x,
                            'y': entrance_y,
                            'direction': direction.value,
                            'lv': 1,
                            'people': 0,
                            'army': 0,
                            'slots': [0] * slots_count  # 所有槽位初始为0（空）
                        }
        
        # 构建最终数据结构
        map_data = {
            'width': GRID_WIDTH,
            'height': GRID_HEIGHT,
            'roads': roads,
            'buildings': list(buildings.values()),
            'cities': list(cities.values())
        }
        
        # 保存到MapEditor目录
        save_path = os.path.join(os.path.dirname(__file__), filename)
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(map_data, f, indent=2, ensure_ascii=False)
        
        print(f"地图已保存到: {save_path}")
        print(f"道路: {len(roads)}格, 建筑: {len(buildings)}个, 城池: {len(cities)}个")
    
    def load_map(self, filename: str = "map.json"):
        """从文件加载地图（支持新旧格式）"""
        load_path = os.path.join(os.path.dirname(__file__), filename)
        
        if not os.path.exists(load_path):
            print(f"文件不存在: {load_path}")
            return
        
        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                map_data = json.load(f)
            
            # 重新初始化网格
            self.grid = [[MapCell() for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
            
            # 检查是新格式还是旧格式
            if 'roads' in map_data:
                # 新格式：压缩数据结构
                self._load_compressed_format(map_data)
            elif 'cells' in map_data:
                # 旧格式：完整网格数据
                for y, row in enumerate(map_data['cells']):
                    for x, cell_data in enumerate(row):
                        if y < GRID_HEIGHT and x < GRID_WIDTH:
                            self.grid[y][x] = MapCell.from_dict(cell_data)
            
            print(f"地图已加载: {load_path}")
        except Exception as e:
            print(f"加载地图失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_compressed_format(self, map_data: dict):
        """加载压缩格式的地图数据"""
        # 第一步：加载道路和分叉口（不设置入口标记）
        for road in map_data.get('roads', []):
            x, y = road['x'], road['y']
            if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                cell = self.grid[y][x]
                
                # 检查是否是分叉口（有direction字段且不为null）
                if road.get('direction') is not None:
                    cell.type = CellType.JUNCTION
                    cell.arrow_direction = Direction(road['direction'])
                else:
                    cell.type = CellType.ROAD
                # 注意：不在这里设置入口标记，由place_building/place_city设置
        
        # 第二步：加载建筑物
        for building in map_data.get('buildings', []):
            building_id = building['id']
            # 使用保存的位置和方向
            entrance_x = building.get('x')
            entrance_y = building.get('y')
            direction_value = building.get('direction', 0)
            direction = Direction(direction_value)
            
            if entrance_x is not None and entrance_y is not None:
                # 放置建筑（会自动设置入口标记）
                self.next_building_id = building_id
                result = self.place_building(entrance_x, entrance_y, direction)
                self.next_building_id = building_id + 1
                # 保存建筑名称
                self.building_names[building_id] = building.get('name', f'建筑{building_id}')
        
        # 第三步：加载城池
        for city in map_data.get('cities', []):
            city_id = city['id']
            slots_count = len(city.get('slots', [1]))
            # 使用保存的位置和方向
            entrance_x = city.get('x')
            entrance_y = city.get('y')
            direction_value = city.get('direction', 0)
            direction = Direction(direction_value)
            city_type = city.get('type', '陆')  # 读取城池类型，默认为陆
            
            if entrance_x is not None and entrance_y is not None:
                # 放置城池（会自动设置入口标记）
                self.next_building_id = city_id
                result = self.place_city(entrance_x, entrance_y, slots_count, direction, city_type)
                self.next_building_id = city_id + 1
                # 保存城池名称
                self.city_names[city_id] = city.get('name', f'城池{city_id}')
        
        # 更新next_building_id
        max_id = 0
        for building in map_data.get('buildings', []):
            max_id = max(max_id, building['id'])
        for city in map_data.get('cities', []):
            max_id = max(max_id, city['id'])
        self.next_building_id = max_id + 1
    
    def _infer_direction(self, entrance_cells: list) -> Direction:
        """根据入口单元格位置推断方向"""
        if len(entrance_cells) < 2:
            return Direction.UP
        
        x1, y1 = entrance_cells[0]
        x2, y2 = entrance_cells[1]
        
        # 如果两个入口水平排列，则是UP或DOWN
        if y1 == y2:
            return Direction.UP  # 默认UP
        # 如果两个入口垂直排列，则是LEFT或RIGHT
        elif x1 == x2:
            return Direction.LEFT  # 默认LEFT
        
        return Direction.UP
    
    def run(self):
        """主循环"""
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # 左键
                        self.handle_mouse_down(event.pos, event.button)
                
                elif event.type == pygame.MOUSEMOTION:
                    self.handle_mouse_motion(event.pos)
                
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:  # 左键
                        self.handle_mouse_up(event.pos)
                
                elif event.type == pygame.MOUSEWHEEL:
                    self.handle_mouse_wheel(event.y)
                
                elif event.type == pygame.KEYDOWN:
                    self.handle_key_down(event.key)
            
            self.draw()
            self.clock.tick(60)  # 60 FPS
        
        pygame.quit()

def main():
    """主函数"""
    editor = MapEditor()
    editor.run()

if __name__ == '__main__':
    main()
