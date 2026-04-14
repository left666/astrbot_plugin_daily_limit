"""
使用记录和统计模块

负责记录和统计用户使用情况，包括：
- 使用记录存储
- 使用统计更新
- 趋势数据分析
"""

import datetime
import json


class UsageTracker:
    """使用记录和统计类"""

    def __init__(self, plugin):
        """
        初始化使用记录器

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.redis_client = plugin.redis_client

    def record_usage(self, user_id, group_id=None, usage_type="llm_request"):
        """
        记录使用情况

        记录用户或群组的使用情况到Redis中，包括：
        - 使用记录（按日期和时间）
        - 使用统计更新
        - 趋势数据分析
        - 过期时间设置

        参数：
            user_id: 用户ID
            group_id: 群组ID（可选）
            usage_type: 使用类型，默认为"llm_request"

        返回：
            bool: 记录成功返回True，失败返回False
        """
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return False

        try:
            # 记录详细使用信息
            self._record_usage_details(user_id, group_id, usage_type)

            # 更新统计信息
            self._update_usage_stats(user_id, group_id)

            # 记录趋势分析数据
            self._record_trend_data(user_id, group_id, usage_type)

            return True
        except Exception as e:
            self.logger.log_error(
                "记录使用记录失败 (用户: {}, 群组: {}): {}", user_id, group_id, str(e)
            )
            return False

    def _record_usage_details(self, user_id, group_id, usage_type):
        """记录详细使用信息"""
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return

        timestamp = datetime.datetime.now().isoformat()
        record_key = self._get_usage_record_key(user_id, group_id)

        # 创建使用记录数据
        record_data = self._create_usage_record_data(
            user_id, group_id, usage_type, timestamp
        )

        # 使用Redis列表存储使用记录
        redis_client.redis.rpush(record_key, json.dumps(record_data))

        # 设置过期时间到下次重置时间
        self._set_usage_record_expiry(record_key)

    def _create_usage_record_data(self, user_id, group_id, usage_type, timestamp):
        """创建使用记录数据"""
        return {
            "timestamp": timestamp,
            "user_id": user_id,
            "group_id": group_id,
            "usage_type": usage_type,
            "date": self._get_reset_period_date(),
        }

    def _set_usage_record_expiry(self, record_key):
        """设置使用记录过期时间"""
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return

        seconds_until_tomorrow = self._get_seconds_until_tomorrow()
        redis_client.redis.expire(record_key, seconds_until_tomorrow)

    def _update_usage_stats(self, user_id, group_id=None):
        """
        更新使用统计信息

        更新用户和群组的使用统计信息，包括：
        - 活跃用户统计
        - 活跃群组统计
        - 总请求数统计

        参数：
            user_id: 用户ID
            group_id: 群组ID（可选）

        返回：
            bool: 更新成功返回True，失败返回False
        """
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return False

        try:
            date_str = self._get_reset_period_date()
            stats_key = self._get_usage_stats_key(date_str)

            # 收集需要更新的统计键
            keys_to_update = self._collect_stats_keys(stats_key, user_id, group_id)

            # 更新所有统计
            self._update_all_stats(keys_to_update)

            # 设置过期时间
            self._set_expiry_for_stats_keys(keys_to_update)

            return True
        except Exception as e:
            self.logger.log_error(
                "更新使用统计失败 (用户: {}, 群组: {}): {}", user_id, group_id, str(e)
            )
            return False

    def _collect_stats_keys(self, stats_key, user_id, group_id):
        """收集需要更新的统计键"""
        keys_to_update = {
            "user_stats": f"{stats_key}:user:{user_id}",
            "global_stats": f"{stats_key}:global",
        }

        if group_id:
            keys_to_update["group_stats"] = f"{stats_key}:group:{group_id}"
            keys_to_update["group_user_stats"] = (
                f"{stats_key}:group:{group_id}:user:{user_id}"
            )

        return keys_to_update

    def _update_all_stats(self, keys_to_update):
        """更新所有统计信息"""
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return

        # 更新用户统计
        redis_client.redis.hincrby(keys_to_update["user_stats"], "total_usage", 1)

        # 更新全局统计
        redis_client.redis.hincrby(keys_to_update["global_stats"], "total_requests", 1)

    def _get_daily_trend_data(self, days: int, current_time: datetime.datetime) -> dict:
        """获取日趋势数据

        参数：
            days: 查询天数
            current_time: 当前时间

        返回：
            dict: 日趋势数据
        """
        trend_data = {}
        for i in range(days):
            # 为每一天计算对应的重置周期日期
            date_obj = current_time - datetime.timedelta(days=i)

            # 使用与_get_reset_period_date相同的逻辑
            reset_time = self._get_reset_time()
            temp_current = datetime.datetime.combine(date_obj.date(), reset_time)

            if date_obj < temp_current:
                date_obj = date_obj - datetime.timedelta(days=1)

            date_key = date_obj.strftime("%Y-%m-%d")
            trend_key = self._get_trend_stats_key("daily", date_key)

            data = self._get_trend_stats_by_key(trend_key)
            if data:
                trend_data[date_key] = data
        return trend_data

    def _get_weekly_trend_data(
        self, weeks: int, current_time: datetime.datetime
    ) -> dict:
        """获取周趋势数据

        参数：
            weeks: 查询周数
            current_time: 当前时间

        返回：
            dict: 周趋势数据
        """
        trend_data = {}
        for i in range(weeks):
            date_obj = current_time - datetime.timedelta(weeks=i)
            week_number = self._get_week_number(date_obj)
            year = date_obj.year
            week_key = f"{year}-W{week_number}"
            trend_key = self._get_trend_stats_key("weekly", week_key)

            data = self._get_trend_stats_by_key(trend_key)
            if data:
                trend_data[week_key] = data
        return trend_data

    def _get_monthly_trend_data(
        self, months: int, current_time: datetime.datetime
    ) -> dict:
        """获取月趋势数据

        参数：
            months: 查询月数
            current_time: 当前时间

        返回：
            dict: 月趋势数据
        """
        trend_data = {}
        for i in range(months):
            date_obj = current_time - datetime.timedelta(days=i * 30)
            month_key = self._get_month_key(date_obj)
            trend_key = self._get_trend_stats_key("monthly", month_key)

            data = self._get_trend_stats_by_key(trend_key)
            if data:
                trend_data[month_key] = data
        return trend_data

    def _get_trend_data(self, period_type, days=7):
        """获取趋势数据（通用方法）"""
        current_time = datetime.datetime.now()

        if period_type == "daily":
            return self._get_daily_trend_data(days, current_time)
        elif period_type == "weekly":
            return self._get_weekly_trend_data(days, current_time)
        elif period_type == "monthly":
            return self._get_monthly_trend_data(days, current_time)
        else:
            return {}

    def _get_trend_stats_by_key(self, trend_key):
        """根据键获取趋势统计"""
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return {}

        try:
            data = redis_client.redis.hgetall(trend_key)
            if data:
                # 将字符串值转换为整数
                return {k: int(v) for k, v in data.items()}
            return {}
        except Exception as e:
            self.logger.log_error("获取趋势统计失败: {}", str(e))
            return {}

    # 以下方法需要从 main.py 中调用，提供占位符实现
    def _get_usage_record_key(self, user_id, group_id=None, date_str=None):
        """获取使用记录的Redis键"""
        if group_id is None:
            group_id = "private_chat"
        if date_str is None:
            date_str = self._get_reset_period_date()
        return f"astrbot:usage_record:{date_str}:{group_id}:{user_id}"

    def _get_usage_stats_key(self, date_str=None):
        """获取使用统计的Redis键"""
        if date_str is None:
            date_str = self._get_reset_period_date()
        return f"astrbot:usage_stats:{date_str}"

    def _get_trend_stats_key(self, period_type, period_value):
        """获取趋势统计的Redis键"""
        return f"astrbot:trend:{period_type}:{period_value}"

    def _get_week_number(self, date_obj=None):
        """获取周数"""
        if date_obj is None:
            date_obj = datetime.datetime.now()
        return date_obj.isocalendar()[1]

    def _get_month_key(self, date_obj=None):
        """获取月份键"""
        if date_obj is None:
            date_obj = datetime.datetime.now()
        return date_obj.strftime("%Y-%m")

    def _get_reset_period_date(self):
        """获取重置周期的日期字符串"""
        # 这个方法需要在 main.py 中实现
        return datetime.datetime.now().strftime("%Y-%m-%d")

    def _get_reset_time(self):
        """获取重置时间"""
        # 这个方法需要在 main.py 中实现
        reset_time_str = self.plugin.config["limits"].get("daily_reset_time", "00:00")
        hour, minute = map(int, reset_time_str.split(":"))
        return datetime.time(hour=hour, minute=minute)

    def _get_seconds_until_tomorrow(self):
        """获取距离明天的秒数"""
        now = datetime.datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        return int((tomorrow - now).total_seconds())

    def _set_expiry_for_stats_keys(self, keys_to_update):
        """设置统计键的过期时间"""
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return

        seconds_until_tomorrow = self._get_seconds_until_tomorrow()
        for key in keys_to_update.values():
            redis_client.redis.expire(key, seconds_until_tomorrow)

    def _record_trend_data(self, user_id, group_id=None, usage_type="llm_request"):
        """记录趋势分析数据"""
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return

        current_time = datetime.datetime.now()
        date_str = self._get_reset_period_date()

        # 更新日趋势
        daily_trend_key = self._get_trend_stats_key("daily", date_str)
        self._update_trend_stats(daily_trend_key, user_id, group_id, usage_type)

        # 更新小时趋势
        hour_key = self._get_hour_key(current_time)
        hourly_trend_key = self._get_trend_stats_key("hourly", hour_key)
        self._update_trend_basic_stats(hourly_trend_key)

        # 更新峰值统计
        self._update_peak_stats(hourly_trend_key, current_time)

    def _update_trend_stats(self, trend_key, user_id, group_id, usage_type):
        """更新趋势统计"""
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return

        pipe = redis_client.redis.pipeline()
        pipe.hincrby(trend_key, "total_requests", 1)
        pipe.hincrby(trend_key, f"user:{user_id}", 1)

        if group_id:
            pipe.hincrby(trend_key, f"group:{group_id}", 1)

        # 设置过期时间
        expiry_seconds = self._get_trend_expiry_seconds(trend_key)
        pipe.expire(trend_key, expiry_seconds)

        pipe.execute()

    def _update_trend_basic_stats(self, trend_key):
        """更新趋势基本统计"""
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return

        redis_client.redis.hincrby(trend_key, "count", 1)

    def _get_trend_expiry_seconds(self, trend_key):
        """获取趋势数据的过期时间"""
        # 日趋势保留30天，周趋势保留90天，月趋势保留365天
        if "daily" in trend_key:
            return 30 * 24 * 3600
        elif "weekly" in trend_key:
            return 90 * 24 * 3600
        elif "monthly" in trend_key:
            return 365 * 24 * 3600
        elif "hourly" in trend_key:
            return 7 * 24 * 3600
        else:
            return 7 * 24 * 3600

    def _get_hour_key(self, current_time):
        """获取小时键"""
        return current_time.strftime("%Y-%m-%d-%H")

    def _update_peak_stats(self, trend_key, current_time):
        """更新峰值统计"""
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return

        pipe = redis_client.redis.pipeline()

        # 获取当前峰值
        current_peak = redis_client.redis.hget(trend_key, "peak_count")
        new_count = int(current_peak) + 1 if current_peak else 1

        # 更新峰值
        pipe.hset(trend_key, "peak_count", new_count)
        pipe.hset(trend_key, "peak_time", current_time.timestamp())

        pipe.execute()
