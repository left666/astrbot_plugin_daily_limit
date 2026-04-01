"""
Redis键生成和管理模块

负责生成和管理所有Redis键，包括用户键、群组键、统计键等。
"""

import datetime


class RedisKeys:
    """Redis键管理类"""

    def __init__(self, plugin):
        """
        初始化RedisKeys

        Args:
            plugin: 插件实例引用
        """
        self.plugin = plugin
        self.config = plugin.config

    def get_today_key(self):
        """
        获取考虑自定义重置时间的日期键

        返回：
            str: 今天的Redis键前缀
        """
        # 获取配置的重置时间
        reset_time_str = self.config["limits"].get("daily_reset_time", "00:00")

        # 解析重置时间
        try:
            reset_hour, reset_minute = map(int, reset_time_str.split(":"))
            if not (0 <= reset_hour <= 23 and 0 <= reset_minute <= 59):
                raise ValueError("重置时间格式错误")
        except (ValueError, AttributeError):
            # 如果配置格式错误，使用默认的00:00
            reset_hour, reset_minute = 0, 0
            self.plugin.logger.log_warning(
                "重置时间配置格式错误: {}，使用默认值00:00", reset_time_str
            )

        now = datetime.datetime.now()

        # 如果当前时间还没到重置时间，那么属于"昨天"的统计周期
        # 如果当前时间已经到了或超过重置时间，那么属于"今天"的统计周期
        current_reset_time = now.replace(
            hour=reset_hour, minute=reset_minute, second=0, microsecond=0
        )

        if now >= current_reset_time:
            # 当前时间已到达或超过重置时间，使用今天的日期
            today = now.strftime("%Y-%m-%d")
        else:
            # 当前时间还没到重置时间，使用昨天的日期
            yesterday = now - datetime.timedelta(days=1)
            today = yesterday.strftime("%Y-%m-%d")

        return f"astrbot:daily_limit:{today}"

    def get_user_key(self, user_id, group_id=None):
        """
        获取用户在特定群组的Redis键

        Args:
            user_id: 用户ID
            group_id: 群组ID，如果为None则使用"private_chat"

        返回：
            str: 用户的Redis键
        """
        if group_id is None:
            group_id = "private_chat"

        return f"{self.get_today_key()}:{group_id}:{user_id}"

    def get_group_key(self, group_id):
        """
        获取群组共享的Redis键

        Args:
            group_id: 群组ID

        返回：
            str: 群组的Redis键
        """
        return f"{self.get_today_key()}:group:{group_id}"

    def get_reset_period_date(self):
        """
        获取考虑自定义重置时间的日期字符串

        返回：
            str: 当前统计周期的日期字符串
        """
        # 获取配置的重置时间
        reset_time_str = self.config["limits"].get("daily_reset_time", "00:00")

        # 解析重置时间
        try:
            reset_hour, reset_minute = map(int, reset_time_str.split(":"))
            if not (0 <= reset_hour <= 23 and 0 <= reset_minute <= 59):
                raise ValueError("重置时间格式错误")
        except (ValueError, AttributeError):
            # 如果配置格式错误，使用默认的00:00
            reset_hour, reset_minute = 0, 0
            self.plugin.logger.log_warning(
                "重置时间配置格式错误: {}，使用默认值00:00", reset_time_str
            )

        now = datetime.datetime.now()

        # 如果当前时间还没到重置时间，那么属于"昨天"的统计周期
        # 如果当前时间已经到了或超过重置时间，那么属于"今天"的统计周期
        current_reset_time = now.replace(
            hour=reset_hour, minute=reset_minute, second=0, microsecond=0
        )

        if now >= current_reset_time:
            # 当前时间已到达或超过重置时间，使用今天的日期
            return now.strftime("%Y-%m-%d")
        else:
            # 当前时间还没到重置时间，使用昨天的日期
            yesterday = now - datetime.timedelta(days=1)
            return yesterday.strftime("%Y-%m-%d")

    def get_usage_record_key(self, user_id, group_id=None, date_str=None):
        """
        获取使用记录Redis键

        Args:
            user_id: 用户ID
            group_id: 群组ID，如果为None则使用"private_chat"
            date_str: 日期字符串，如果为None则使用当前统计周期

        返回：
            str: 使用记录的Redis键
        """
        if date_str is None:
            # 使用与today_key相同的逻辑，确保日期一致性
            date_str = self.get_reset_period_date()

        if group_id is None:
            group_id = "private_chat"

        return f"astrbot:usage_record:{date_str}:{group_id}:{user_id}"

    def get_usage_stats_key(self, date_str=None):
        """
        获取使用统计Redis键

        Args:
            date_str: 日期字符串，如果为None则使用当前统计周期

        返回：
            str: 使用统计的Redis键
        """
        if date_str is None:
            # 使用与today_key相同的逻辑，确保日期一致性
            date_str = self.get_reset_period_date()

        return f"astrbot:usage_stats:{date_str}"

    def get_trend_stats_key(self, period_type, period_value):
        """
        获取趋势统计Redis键

        Args:
            period_type: 统计周期类型 ('daily', 'weekly', 'monthly')
            period_value: 周期值 (日期字符串、周数、月份)

        返回：
            str: 趋势统计的Redis键
        """
        return f"astrbot:trend_stats:{period_type}:{period_value}"

    def get_week_number(self, date_obj=None):
        """
        获取日期对应的周数

        Args:
            date_obj: 日期对象，如果为None则使用当前时间

        返回：
            int: 周数
        """
        if date_obj is None:
            date_obj = datetime.datetime.now()
        return date_obj.isocalendar()[1]  # 返回周数

    def get_month_key(self, date_obj=None):
        """
        获取月份键（格式：YYYY-MM）

        Args:
            date_obj: 日期对象，如果为None则使用当前时间

        返回：
            str: 月份键
        """
        if date_obj is None:
            date_obj = datetime.datetime.now()
        return date_obj.strftime("%Y-%m")

    def get_hour_key(self, date_obj=None):
        """
        获取小时键（格式：YYYY-MM-DD-HH）

        Args:
            date_obj: 日期对象，如果为None则使用当前时间

        返回：
            str: 小时键
        """
        if date_obj is None:
            date_obj = datetime.datetime.now()
        return date_obj.strftime("%Y-%m-%d-%H")

    def get_seconds_until_tomorrow(self):
        """
        获取到下次重置时间的秒数

        返回：
            int: 秒数
        """
        # 获取配置的重置时间
        reset_time_str = self.config["limits"].get("daily_reset_time", "00:00")

        # 解析重置时间
        try:
            reset_hour, reset_minute = map(int, reset_time_str.split(":"))
            if not (0 <= reset_hour <= 23 and 0 <= reset_minute <= 59):
                raise ValueError("重置时间格式错误")
        except (ValueError, AttributeError):
            # 如果配置格式错误，使用默认的00:00
            reset_hour, reset_minute = 0, 0
            self.plugin.logger.log_warning(
                "重置时间配置格式错误: {}，使用默认值00:00", reset_time_str
            )

        now = datetime.datetime.now()

        # 计算今天的重置时间
        reset_today = now.replace(
            hour=reset_hour, minute=reset_minute, second=0, microsecond=0
        )

        # 如果当前时间已经过了今天的重置时间，则计算明天的重置时间
        if now >= reset_today:
            reset_time = reset_today + datetime.timedelta(days=1)
        else:
            reset_time = reset_today

        return int((reset_time - now).total_seconds())
