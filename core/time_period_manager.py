"""
时间段管理模块

负责时间段限制的解析、验证和管理，包括：
- 时间段配置解析
- 时间格式验证
- 时间段使用次数管理
- 时间段限制查询
"""

import datetime


class TimePeriodManager:
    """时间段管理类"""

    def __init__(self, plugin):
        """
        初始化时间段管理器

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.config = plugin.config
        self.logger = plugin.logger
        self.time_period_limits = plugin.time_period_limits

    def parse_time_period_limits(self, limits_config=None):
        """解析时间段限制配置

        Args:
            limits_config: 时间段限制配置，如果为None则从插件配置读取

        Returns:
            list: 解析后的时间段限制列表
        """
        if limits_config is None:
            limits_config = self.config["limits"].get("time_period_limits", "")

        # 处理配置值，兼容字符串和列表两种格式
        if isinstance(limits_config, str):
            # 如果是字符串，按换行符分割并过滤空值
            lines = [
                line.strip()
                for line in limits_config.strip().split("\n")
                if line.strip()
            ]
        elif isinstance(limits_config, list):
            # 如果是列表，确保所有元素都是字符串并过滤空值
            lines = [
                str(line).strip() for line in limits_config if str(line).strip()
            ]
        else:
            # 其他类型，转换为字符串处理
            lines = [str(limits_config).strip()]

        parsed_limits = []
        for line in lines:
            parsed = self.parse_time_period_line(line)
            if parsed:
                parsed_limits.append(parsed)

        return parsed_limits

    def parse_time_period_line(self, line):
        """解析单行时间段限制配置

        Args:
            line: 配置行，格式为 "HH:MM-HH:MM:次数[:启用标志]"

        Returns:
            dict: 解析后的时间段限制，如果解析失败返回None
        """
        # 解析时间范围部分
        time_range_data = self.parse_time_range_from_line(line)
        if not time_range_data:
            return None

        # 解析限制次数
        limit_data = self.parse_limit_from_line(line)
        if limit_data is None:
            return None

        # 解析启用标志
        enabled = self.parse_enabled_flag_from_line(line)

        # 如果启用，则返回时间段限制
        if enabled:
            return {
                "start_time": time_range_data["start_time"],
                "end_time": time_range_data["end_time"],
                "limit": limit_data,
            }
        return None

    def parse_time_range_from_line(self, line):
        """从配置行中解析时间范围

        Args:
            line: 配置行

        Returns:
            dict: 包含start_time和end_time的字典，解析失败返回None
        """
        parts = self._validate_config_line(line, ":", 2)
        if not parts:
            return None

        time_range = parts[0].strip()
        time_parts = self._validate_config_line(time_range, "-", 2)
        if not time_parts:
            return None

        start_time = time_parts[0].strip()
        end_time = time_parts[1].strip()

        # 验证时间格式
        if not self.validate_time_format(start_time) or not self.validate_time_format(end_time):
            self.logger.log_warning("时间段限制时间格式错误: {}", line)
            return None

        return {"start_time": start_time, "end_time": end_time}

    def parse_limit_from_line(self, line):
        """从配置行中解析限制次数

        Args:
            line: 配置行

        Returns:
            int: 限制次数，解析失败返回None
        """
        parts = self._validate_config_line(line, ":", 2)
        if not parts:
            return None

        limit = self._safe_parse_int(parts[1].strip())
        if limit is not None:
            return limit
        else:
            self.logger.log_warning("时间段限制次数格式错误: {}", line)
            return None

    def parse_enabled_flag_from_line(self, line):
        """从配置行中解析启用标志

        Args:
            line: 配置行

        Returns:
            bool: 是否启用
        """
        line = line.strip()
        parts = line.split(":", 2)

        if len(parts) >= 3:
            return self._parse_enabled_flag(parts[2])
        return True

    def validate_time_format(self, time_str):
        """验证时间格式

        Args:
            time_str: 时间字符串，格式应为HH:MM

        Returns:
            bool: 时间格式是否有效
        """
        try:
            datetime.datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    def _parse_enabled_flag(self, enabled_str):
        """解析启用标志

        Args:
            enabled_str: 启用标志字符串

        Returns:
            bool: 是否启用
        """
        if enabled_str is None:
            return True

        enabled_str = enabled_str.strip().lower()
        return enabled_str in ["true", "1", "yes", "y"]

    def _validate_config_line(self, line, separator, expected_parts):
        """验证配置行格式

        Args:
            line: 配置行
            separator: 分隔符
            expected_parts: 期望的分割部分数量

        Returns:
            list: 分割后的部分，验证失败返回None
        """
        parts = line.split(separator)
        if len(parts) < expected_parts:
            return None
        return parts

    def _safe_parse_int(self, value):
        """安全地解析整数

        Args:
            value: 要解析的值

        Returns:
            int: 解析后的整数，失败返回None
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def format_time_period(self, period):
        """格式化时间段为可读字符串

        Args:
            period: 时间段字典，包含start_time和end_time

        Returns:
            str: 格式化后的时间段字符串
        """
        start_time = period.get("start_time", "")
        end_time = period.get("end_time", "")
        limit = period.get("limit", 0)
        return f"{start_time}-{end_time} ({limit}次)"

    def is_in_time_period(self, current_time_str, start_time_str, end_time_str):
        """检查当前时间是否在指定时间段内

        Args:
            current_time_str: 当前时间字符串，格式HH:MM
            start_time_str: 开始时间字符串，格式HH:MM
            end_time_str: 结束时间字符串，格式HH:MM

        Returns:
            bool: 是否在时间段内
        """
        try:
            current_time = datetime.datetime.strptime(current_time_str, "%H:%M")
            start_time = datetime.datetime.strptime(start_time_str, "%H:%M")
            end_time = datetime.datetime.strptime(end_time_str, "%H:%M")

            return start_time <= current_time <= end_time
        except ValueError:
            return False

    def get_current_time_period_limit(self):
        """获取当前时间段适用的限制

        Returns:
            int: 当前时间段的限制次数，如果不在任何时间段内返回None
        """
        current_time_str = datetime.datetime.now().strftime("%H:%M")

        for period in self.time_period_limits:
            if self.is_in_time_period(
                current_time_str, period["start_time"], period["end_time"]
            ):
                return period["limit"]

        return None

    def get_time_period_usage_key(self, user_id, group_id=None, time_period_id=None):
        """获取时间段使用次数的Redis键

        Args:
            user_id: 用户ID
            group_id: 群组ID（可选）
            time_period_id: 时间段ID（可选），如果为None则使用当前时间段

        Returns:
            str: Redis键，如果当前不在任何时间段内返回None
        """
        if time_period_id is None:
            # 如果没有指定时间段ID，使用当前时间段
            current_time_str = datetime.datetime.now().strftime("%H:%M")
            for i, time_limit in enumerate(self.time_period_limits):
                if self.is_in_time_period(
                    current_time_str, time_limit["start_time"], time_limit["end_time"]
                ):
                    time_period_id = i
                    break

            if time_period_id is None:
                return None

        if group_id is None:
            group_id = "private_chat"

        # 使用与today_key相同的逻辑，确保日期一致性
        date_str = self.plugin.usage_tracker._get_reset_period_date()
        return f"astrbot:time_period_limit:{date_str}:{time_period_id}:{group_id}:{user_id}"

    def get_time_period_usage(self, user_id, group_id=None):
        """获取用户在时间段内的使用次数

        Args:
            user_id: 用户ID
            group_id: 群组ID（可选）

        Returns:
            int: 使用次数
        """
        redis_client = self.plugin.redis_client
        if not redis_client or not redis_client.redis:
            return 0

        key = self.get_time_period_usage_key(user_id, group_id)
        if key is None:
            return 0

        usage = redis_client.redis.get(key)
        return int(usage) if usage else 0

    def increment_time_period_usage(self, user_id, group_id=None):
        """增加用户在时间段内的使用次数

        Args:
            user_id: 用户ID
            group_id: 群组ID（可选）

        Returns:
            bool: 是否成功增加
        """
        redis_client = self.plugin.redis_client
        if not redis_client or not redis_client.redis:
            return False

        key = self.get_time_period_usage_key(user_id, group_id)
        if key is None:
            return False

        redis_client.redis.incr(key)
        # 设置过期时间到第二天
        seconds_until_tomorrow = self.plugin.usage_tracker._get_seconds_until_tomorrow()
        redis_client.redis.expire(key, seconds_until_tomorrow)

        return True
