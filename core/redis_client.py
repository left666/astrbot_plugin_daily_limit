"""
Redis 连接管理模块

提供 Redis 连接的初始化、验证、重连和状态查询功能。
"""

import redis
import redis.exceptions


class RedisClient:
    """Redis 连接管理类"""

    def __init__(self, plugin):
        """
        初始化 Redis 客户端

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.config = plugin.config
        self.redis_client = None

    def init_redis(self):
        """初始化Redis连接"""
        try:
            # 获取连接池大小配置
            pool_size = self.config["limits"].get("redis_connection_pool_size", 10)

            self.redis_client = redis.Redis(
                host=self.config["redis"]["host"],
                port=self.config["redis"]["port"],
                db=self.config["redis"]["db"],
                password=self.config["redis"]["password"],
                decode_responses=True,  # 自动将响应解码为字符串
                max_connections=pool_size,  # 使用配置的连接池大小
            )
            # 测试连接
            self.redis_client.ping()
            self.logger.log_info("Redis连接成功，连接池大小: {}", pool_size)
        except Exception as e:
            self.logger.log_error("Redis连接失败: {}", str(e))
            self.redis_client = None

    def validate_redis_connection(self) -> bool:
        """
        验证Redis连接状态

        检查Redis连接是否可用，包括连接状态和响应能力。

        返回：
            bool: Redis连接是否可用
        """
        if not self.redis_client:
            self.logger.log_error("Redis连接未初始化")
            return False

        try:
            # 发送ping命令验证连接
            response = self.redis_client.ping()
            if not response:
                self.logger.log_warning("Redis ping响应异常: {}", response)
                return False

            return True

        except redis.exceptions.ConnectionError as e:
            self.logger.log_error("Redis连接错误: {}", str(e))
            return False
        except redis.exceptions.TimeoutError as e:
            self.logger.log_error("Redis连接超时: {}", str(e))
            return False
        except Exception as e:
            self.logger.handle_error(e, "Redis连接验证")
            return False

    def get_redis_status(self):
        """
        获取Redis连接状态信息

        返回：
            dict: Redis连接状态信息字典
        """
        if not self.redis_client:
            return {
                "connected": False,
                "status": "未初始化",
                "error": "Redis连接未初始化",
            }

        try:
            # 检查连接状态
            self.redis_client.ping()

            # 获取Redis服务器信息
            info = self.redis_client.info()

            return {
                "connected": True,
                "status": "正常",
                "response_time": "正常",
                "server_version": info.get("redis_version", "未知"),
                "used_memory": info.get("used_memory_human", "未知"),
                "connected_clients": info.get("connected_clients", 0),
            }

        except Exception as e:
            return {"connected": False, "status": "异常", "error": str(e)}

    def reconnect_redis(self):
        """
        重新连接Redis

        当Redis连接断开时，尝试重新建立连接。

        返回：
            bool: 重连成功返回True，失败返回False
        """
        if not self.redis_client:
            self.logger.log_error("Redis连接未初始化，无法重连")
            return False

        try:
            # 关闭现有连接
            if (
                hasattr(self.redis_client, "connection_pool")
                and self.redis_client.connection_pool
            ):
                self.redis_client.connection_pool.disconnect()

            # 重新连接
            self.redis_client.connection_pool.reset()

            # 验证新连接
            if self.validate_redis_connection():
                self.logger.log_info("Redis重连成功")
                return True
            else:
                self.logger.log_error("Redis重连失败")
                return False

        except Exception as e:
            self.logger.log_error("Redis重连过程中出错: {}", str(e))
            return False

    @property
    def redis(self):
        """获取 Redis 客户端实例"""
        return self.redis_client
