"""
核心限制逻辑模块

负责处理用户/群组的限制逻辑，包括：
- 获取用户/群组限制
- 检查消息是否应忽略
- 时间段限制处理
- 群组模式管理
"""

import datetime


class Limiter:
    """核心限制逻辑类"""

    def __init__(self, plugin):
        """
        初始化限制器

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.config = plugin.config
        self.config_mgr = plugin.config_mgr  # 引用配置管理器

    def should_skip_message(self, message_str):
        """检查消息是否应该忽略处理"""
        if not message_str or not self.config_mgr.skip_patterns:
            return False

        # 检查消息是否以任何忽略模式开头
        for pattern in self.config_mgr.skip_patterns:
            if message_str.startswith(pattern):
                return True

        return False

    def get_group_mode(self, group_id):
        """获取群组的模式配置"""
        if not group_id:
            return "individual"  # 私聊默认为独立模式

        # 检查是否有特定群组模式配置
        if str(group_id) in self.config_mgr.group_modes:
            return self.config_mgr.group_modes[str(group_id)]

        # 默认使用共享模式（保持向后兼容性）
        return "shared"

    def parse_time_string(self, time_str):
        """解析时间字符串为时间对象"""
        try:
            return datetime.datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            return None

    def is_in_time_period(self, current_time_str, start_time_str, end_time_str):
        """检查当前时间是否在指定时间段内"""
        current_time = self.parse_time_string(current_time_str)
        start_time = self.parse_time_string(start_time_str)
        end_time = self.parse_time_string(end_time_str)

        if not all([current_time, start_time, end_time]):
            return False

        # 处理跨天的时间段（如 22:00 - 06:00）
        if start_time <= end_time:
            # 不跨天的时间段
            return start_time <= current_time <= end_time
        else:
            # 跨天的时间段
            return current_time >= start_time or current_time <= end_time

    def get_current_time_period_limit(self):
        """获取当前时间段适用的限制"""
        current_time_str = datetime.datetime.now().strftime("%H:%M")

        for time_limit in self.config_mgr.time_period_limits:
            if self.is_in_time_period(
                current_time_str, time_limit["start_time"], time_limit["end_time"]
            ):
                return time_limit["limit"]

        return None  # 没有匹配的时间段限制

    def get_time_period_usage_key(self, user_id, group_id=None, time_period_id=None):
        """获取时间段使用次数的Redis键"""
        if time_period_id is None:
            # 如果没有指定时间段ID，使用当前时间段
            current_time_str = datetime.datetime.now().strftime("%H:%M")
            for i, time_limit in enumerate(self.config_mgr.time_period_limits):
                if self.is_in_time_period(
                    current_time_str, time_limit["start_time"], time_limit["end_time"]
                ):
                    time_period_id = i
                    break

            if time_period_id is None:
                return None

        if group_id is None:
            group_id = "private_chat"

        # 使用与_today_key相同的逻辑，确保日期一致性
        date_str = self._get_reset_period_date()
        return f"astrbot:time_period_limit:{date_str}:{time_period_id}:{group_id}:{user_id}"

    def get_time_period_usage(self, user_id, group_id=None):
        """获取用户在时间段内的使用次数"""
        redis_client = self.plugin.redis_client
        if not redis_client or not redis_client.redis:
            return 0

        key = self.get_time_period_usage_key(user_id, group_id)
        if key is None:
            return 0

        usage = redis_client.redis.get(key)
        return int(usage) if usage else 0

    def increment_time_period_usage(self, user_id, group_id=None):
        """增加用户在时间段内的使用次数"""
        redis_client = self.plugin.redis_client
        if not redis_client or not redis_client.redis:
            return False

        key = self.get_time_period_usage_key(user_id, group_id)
        if key is None:
            return False

        # 增加计数并设置过期时间
        pipe = redis_client.redis.pipeline()
        pipe.incr(key)

        # 设置过期时间到下次重置时间
        seconds_until_tomorrow = self._get_seconds_until_tomorrow()
        pipe.expire(key, seconds_until_tomorrow)

        pipe.execute()
        return True

    def get_user_limit(self, user_id, group_id=None):
        """获取用户的调用限制次数"""
        user_id_str = str(user_id)

        # 检查用户是否豁免（优先级最高）
        if user_id_str in self.config["limits"]["exempt_users"]:
            return float("inf")  # 无限制

        # 检查时间段限制（优先级第二）
        time_period_limit = self.get_current_time_period_limit()
        if time_period_limit is not None:
            return time_period_limit

        # 检查用户是否为优先级用户（优先级第三）
        if user_id_str in self.config["limits"].get("priority_users", []):
            # 优先级用户在任何群聊中只受特定限制，不参与特定群聊限制
            if user_id_str in self.config_mgr.user_limits:
                return self.config_mgr.user_limits[user_id_str]
            else:
                return self.config["limits"]["default_daily_limit"]

        # 检查用户特定限制
        if user_id_str in self.config_mgr.user_limits:
            return self.config_mgr.user_limits[user_id_str]

        # 检查群组特定限制
        if group_id and str(group_id) in self.config_mgr.group_limits:
            return self.config_mgr.group_limits[str(group_id)]

        # 返回默认限制
        return self.config["limits"]["default_daily_limit"]

    def _get_reset_period_date(self):
        """获取重置周期的日期字符串"""
        # 这个方法需要在 main.py 中实现，因为它依赖 _get_today_key
        # 这里提供一个占位符
        return datetime.datetime.now().strftime("%Y-%m-%d")

    def _get_seconds_until_tomorrow(self):
        """获取距离明天的秒数"""
        # 这个方法需要在 main.py 中实现
        # 这里提供一个简单的实现
        now = datetime.datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        return int((tomorrow - now).total_seconds())
