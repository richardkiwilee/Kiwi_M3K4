import time
import traceback
from concurrent import futures
import queue
import random
from enum import Enum
import logging
import json
import grpc
import M3K4.protocol.service_pb2 as pb2
import M3K4.protocol.service_pb2_grpc as rpc
from concurrent.futures import ThreadPoolExecutor
import threading

queues = []
# 配置日志记录器
logger = logging.getLogger('server')
logger.setLevel(logging.DEBUG)
# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
# 将处理器添加到日志记录器
logger.addHandler(console_handler)

class GameStatus(Enum):
    LOBBY = 1
    IN_GAME = 2

class GameServiceServicer(rpc.GameServiceServicer):
    def __init__(self):
        self.status = GameStatus.LOBBY.value
        self.host = None
        self.users = dict()     # 记录当前大厅的玩家状态 {player_id: {player_name, slot, stream, ...}}
        self.player_order = []  # 玩家ID列表，按加入顺序决定回合顺序
        self.current_player_index = 0
        self.seq = 0
        # 游戏状态
        self.game_state = None  # GameState message
        self.map_data = None    # 地图数据

    def StartGame(self):
        """开始游戏"""
        self.status = GameStatus.IN_GAME.value
        self.current_player_index = 0
        # TODO: 初始化游戏状态
        logger.info('Game started')

    # ==================== gRPC 方法实现 ====================
    
    def JoinGame(self, request, context):
        """玩家加入游戏"""
        try:
            player_id = request.player_id
            player_name = request.player_name
            
            # 检查玩家槽位是否已满（最多4个玩家）
            if len(self.users) >= 4:
                return pb2.JoinResponse(
                    success=False,
                    message="游戏已满，无法加入",
                    player_slot=-1
                )
            
            # 第一个玩家作为房主
            if len(self.users) == 0:
                self.host = player_id
            
            # 分配玩家槽位
            player_slot = len(self.users)
            
            # 添加玩家
            if player_id not in self.users:
                self.users[player_id] = {
                    'player_name': player_name,
                    'slot': player_slot,
                    'ready': False
                }
                self.player_order.append(player_id)
                logger.info(f'Player {player_name} (ID: {player_id}) joined at slot {player_slot}')
            else:
                # 玩家重新连接
                logger.info(f'Player {player_name} (ID: {player_id}) reconnected')
            
            # TODO: 构建初始游戏状态
            initial_state = pb2.GameState(
                current_turn=0,
                current_player_id=""
            )
            
            return pb2.JoinResponse(
                success=True,
                message=f"成功加入游戏，槽位 {player_slot}",
                player_slot=player_slot,
                initial_state=initial_state
            )
        except Exception as e:
            logger.error(f'Error in JoinGame: {e}')
            traceback.print_exc()
            return pb2.JoinResponse(
                success=False,
                message=f"加入游戏失败: {str(e)}",
                player_slot=-1
            )
    
    def SubscribeGameEvents(self, request, context):
        """订阅游戏事件流"""
        try:
            player_id = request.player_id
            
            # 创建消息队列
            message_queue = queue.Queue()
            
            # 添加到用户列表
            if player_id not in self.users:
                self.users[player_id] = {'stream': message_queue}
            else:
                self.users[player_id]['stream'] = message_queue
            
            # 注册断开连接回调
            context.add_callback(self._onDisconnectWrapper(request, context))
            
            # 发送初始游戏状态
            self._broadcast_event()
            
            logger.info(f'Player {player_id} subscribed to game events')
            
            # 持续发送消息
            while True:
                message = message_queue.get()
                if message is None:  # 终止信号
                    break
                yield message
        except Exception as e:
            logger.error(f'Error in SubscribeGameEvents for {player_id}: {e}')
            traceback.print_exc()
        finally:
            # 清理
            if player_id in self.users and 'stream' in self.users[player_id]:
                del self.users[player_id]['stream']
    
    def RollDice(self, request, context):
        """投骰子"""
        pass
    
    def UseCard(self, request, context):
        """使用锦囊"""
        pass
    
    def TradeProp(self, request, context):
        """买卖道具"""
        pass
    
    def InteractBuilding(self, request, context):
        """地图建筑互动"""
        pass
    
    def AdjustArmySize(self, request, context):
        """调整兵力"""
        pass
    
    def AdjustCityBuilding(self, request, context):
        """调整建筑"""
        pass
    
    def MoveGeneral(self, request, context):
        """调整武将位置"""
        pass
    
    def PassByAction(self, request, context):
        """过路动作"""
        pass
    
    def get_current_player(self):
        """获取当前回合的玩家"""
        if not self.player_order:
            return None
        return self.player_order[self.current_player_index]

    def next_player(self):
        """移动到下一个玩家"""
        self.current_player_index = (self.current_player_index + 1) % len(self.player_order)
        return self.get_current_player()

    def isAllPlayerReady(self):
        for k in self.users.keys():
            if not self.users[k]['ready']:
                return False
        return True

    def resetPlayerReadyStatus(self):
        for user in self.users.values():
            user['ready'] = False

    def getPlayerFromSender(self, sender: str):
        if sender in self.player_order:
            return sender
        return None
        
    def player_exit(self, username: str):
        """处理玩家退出"""
        # 从玩家顺序列表中移除
        if username in self.player_order:
            self.player_order.remove(username)
        
        # 如果是游戏中状态
        if self.status == GameStatus.IN_GAME.value:
            if len(self.player_order) > 0:
                # 如果退出的是当前玩家，移动到下一个玩家
                if self.current_player_index >= len(self.player_order):
                    self.current_player_index = 0
            else:
                # 如果没有玩家了，重置游戏状态
                self.status = GameStatus.LOBBY.value
        
        # 如果是大厅状态，检查是否需要更换房主
        elif self.status == GameStatus.LOBBY.value and username == self.host and len(self.users) > 0:
            # 选择新房主（第一个在线的玩家）
            self.host = next(iter(self.users.keys()))

    def Subscribe(self, request, context):
        """
        Handle client subscription to game state updates
        """
        # Create a queue for this client's messages
        message_queue = queue.Queue()
        
        # Add the client to our users with their stream queue
        if request.sender not in self.users:
            self.users[request.sender] = {'name': request.sender, 'stream': message_queue}
        else:
            self.users[request.sender]['stream'] = message_queue
            
        # Register disconnect callback
        context.add_callback(self._onDisconnectWrapper(request, context))
            
        # Send initial game state
        self._broadcast()
        
        try:
            while True:
                # Wait for messages in the queue
                message = message_queue.get()
                if message is None:  # Check for termination signal
                    break
                yield message
        except Exception as e:
            logger.error(f"Error in subscription stream for {request.sender}: {e}")
            traceback.print_exc()
        finally:
            # Cleanup when client disconnects
            if request.sender in self.users:
                if 'stream' in self.users[request.sender]:
                    del self.users[request.sender]['stream']

    def _response(self, status, body):
        return pb2.GeneralResponse(
            sequence=self.seq,
            msgtype=1,  # 1 for response
            status=status.value,
            sender='__SERVER__',
            body=json.dumps(body)
        )

    def Broadcast(self, info):
        return pb2.Broadcast(sequence=self.seq, msgtype=200, 
                            status=200, sender='SYSTEM',
                            body=json.dumps(info))

    def _broadcast(self):
        try:
            self.seq += 1
            data = dict()
            data['status'] = self.status
            if data['status'] == GameStatus.LOBBY.value:
                ready_status = dict()
                for user, _data in self.users.items():
                    ready_status[user] = _data.get('ready', False)
                data['ready_status'] = ready_status
                # logger.debug(f'Broadcast - Game Status:{data["status"]}')
                # logger.debug(f'Broadcast - Ready Status:{data["ready_status"]}')
            if data['status'] == GameStatus.IN_GAME.value:
                data['current_player_index'] = self.current_player_index
                data['players'] = self.player_order
                data['manager'] = self.gm.Serialize()
                # logger.debug(f'Broadcast - Game Status:{data["status"]}')        
                # logger.debug(f'Broadcast - Current Player Index:{data["current_player_index"]}')       
        except Exception as ex:
            logger.error(f'Error in broadcast: {ex}')
            traceback.print_exc()
        try:
            _obj = pb2.Broadcast(
                sequence=self.seq,
                msgtype=0,
                status=200,
                sender='__SYSTEM__',
                body=json.dumps(data)
            )
            for user in self.users:
                if 'stream' in self.users[user]:
                    self.users[user]['stream'].put(_obj)
            return data
        except Exception as e:
            logger.error(f'Error in broadcast: {e}')
            logger.error(f'{data}')
            traceback.print_exc()

    def reset_room(self):
        """Reset the room to initial state"""
        self.status = GameStatus.LOBBY.value
        self.host = None
        self.current_player_index = 0
        self.gm = Manager()
        self.users = dict()     # 记录当前大厅的玩家状态
        self.player_order = []  # 玩家名字列表，按加入顺序决定回合顺序
        self.current_player_index = 0
        self.seq = 0
        self.deck = None
        logger.info('Room reset to lobby state')

    def _onDisconnectWrapper(self, request, context):
        def callback():
            try:
                username = request.sender
                if username in self.users:
                    user_data = self.users[username]
                    if 'stream' in user_data:
                        user_data['stream'].put(None)
                    self.users.pop(username)
                    self.player_exit(username)
                    # 检查是否还有其他用户连接
                    if not self.users:
                        # 如果没有用户，重置房间状态
                        logger.info('No users left, resetting room')
                        self.reset_room()                    
                    self._broadcast()
                    logger.debug(f'User {username} disconnected')
            except Exception as e:
                logger.error(f'Error in disconnect callback: {e}')
        return callback


def server(port=50051):
    logger.info('Starting server')
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    servicer = LobbyServicer()
    rpc.add_LobbyServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{port}')
    logger.info(f'Server started, listening on port: {port}')
    server.start()

    def cleanup():
        logger.info('Cleaning up server...')
        try:
            # First stop accepting new connections
            server.stop(0)
            
            # Close all existing client connections
            for username, user_data in list(servicer.users.items()):
                try:
                    if 'stream' in user_data:
                        user_data['stream'].put(None)
                    servicer.users.pop(username)
                except Exception as e:
                    logger.error(f'Error closing connection for {username}: {e}')
            
            # Clear all message queues
            for q in queues:
                try:
                    while not q.empty():
                        q.get_nowait()
                    q.put(None)
                except Exception as e:
                    logger.error(f'Error clearing queue: {e}')
            
            # Wait for all RPCs to complete
            server.wait_for_termination(timeout=2)
            
            logger.info('Server shutdown complete')
        except Exception as e:
            logger.error(f'Error during cleanup: {e}')
            raise

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info('Received shutdown signal')
        cleanup()
        exit()
    except Exception as e:
        logger.error(f'Server error: {e}')
        cleanup()
        exit()


if __name__ == '__main__':
    server()
