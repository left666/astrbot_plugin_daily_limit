"""
统计分析模块

负责数据分析和统计报告生成，包括：
- 趋势数据分析
- 使用量统计
- 统计报告生成
- 数据可视化辅助
"""

import datetime


class StatsAnalyzer:
    """统计分析类"""

    def __init__(self, plugin):
        """
        初始化统计分析器

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.usage_tracker = plugin.usage_tracker
        self.redis_client = plugin.redis_client

    def get_user_stats(self, user_id, date_str=None):
        """获取用户统计信息

        Args:
            user_id: 用户ID
            date_str: 日期字符串（可选），默认为今日

        Returns:
            dict: 用户统计信息
        """
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return {}

        try:
            if date_str is None:
                date_str = self.usage_tracker._get_reset_period_date()

            stats_key = f"astrbot:usage_stats:{date_str}:user:{user_id}"
            data = redis_client.redis.hgetall(stats_key)

            if data:
                return {k: int(v) for k, v in data.items()}
            return {}
        except Exception as e:
            self.logger.log_error("获取用户统计失败: {}", str(e))
            return {}

    def get_group_stats(self, group_id, date_str=None):
        """获取群组统计信息

        Args:
            group_id: 群组ID
            date_str: 日期字符串（可选），默认为今日

        Returns:
            dict: 群组统计信息
        """
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return {}

        try:
            if date_str is None:
                date_str = self.usage_tracker._get_reset_period_date()

            stats_key = f"astrbot:usage_stats:{date_str}:group:{group_id}"
            data = redis_client.redis.hgetall(stats_key)

            if data:
                return {k: int(v) for k, v in data.items()}
            return {}
        except Exception as e:
            self.logger.log_error("获取群组统计失败: {}", str(e))
            return {}

    def get_global_stats(self, date_str=None):
        """获取全局统计信息

        Args:
            date_str: 日期字符串（可选），默认为今日

        Returns:
            dict: 全局统计信息
        """
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return {}

        try:
            if date_str is None:
                date_str = self.usage_tracker._get_reset_period_date()

            stats_key = f"astrbot:usage_stats:{date_str}:global"
            data = redis_client.redis.hgetall(stats_key)

            if data:
                return {k: int(v) for k, v in data.items()}
            return {}
        except Exception as e:
            self.logger.log_error("获取全局统计失败: {}", str(e))
            return {}

    def get_trend_data(self, period_type="daily", days=7):
        """获取趋势数据

        Args:
            period_type: 统计周期类型 (daily/weekly/monthly)
            days: 查询天数

        Returns:
            dict: 趋势数据
        """
        return self.usage_tracker._get_trend_data(period_type, days)

    def analyze_trends(self, trend_data):
        """分析趋势数据，生成趋势报告

        Args:
            trend_data: 趋势数据字典

        Returns:
            str: 趋势分析报告
        """
        if not trend_data:
            return "暂无趋势数据"

        try:
            # 提取关键指标
            total_requests, active_users, active_groups, dates = (
                self.extract_trend_metrics(trend_data)
            )

            # 生成报告各部分
            summary = self.generate_summary_section(
                total_requests, active_users, active_groups
            )
            detailed = self.generate_detailed_section(trend_data, dates)

            # 组合完整报告
            trend_report = summary + detailed

            return trend_report

        except Exception as e:
            self.logger.log_error("分析趋势数据失败: {}", str(e))
            return "趋势分析失败，请稍后重试"

    def extract_trend_metrics(self, trend_data):
        """从趋势数据中提取关键指标

        Args:
            trend_data: 趋势数据字典

        Returns:
            tuple: (total_requests, active_users, active_groups, dates)
        """
        total_requests = []
        active_users = []
        active_groups = []
        dates = list(trend_data.keys())

        for date in dates:
            data = trend_data[date]
            total_requests.append(data.get("total_requests", 0))
            active_users.append(data.get("active_users", 0))
            active_groups.append(data.get("active_groups", 0))

        return total_requests, active_users, active_groups, dates

    def generate_summary_section(self, total_requests, active_users, active_groups):
        """生成趋势报告摘要部分

        Args:
            total_requests: 总请求数列表
            active_users: 活跃用户数列表
            active_groups: 活跃群组数列表

        Returns:
            str: 摘要部分文本
        """
        summary = "📈 使用趋势分析报告\n"
        summary += "═══════════════\n\n"

        if total_requests:
            summary += f"📊 总请求数趋势: {total_requests[-1]} 次\n"
        if active_users:
            summary += f"👤 活跃用户数: {active_users[-1]} 人\n"
        if active_groups:
            summary += f"👥 活跃群组数: {active_groups[-1]} 个\n\n"

        return summary

    def generate_detailed_section(self, trend_data, dates):
        """生成详细趋势数据部分

        Args:
            trend_data: 趋势数据字典
            dates: 日期列表

        Returns:
            str: 详细数据部分文本
        """
        detailed = "📅 详细趋势数据:\n"
        for i, date in enumerate(dates):
            data = trend_data[date]
            detailed += f"• {date}: {data.get('total_requests', 0)} 次请求, {data.get('active_users', 0)} 活跃用户\n"

        return detailed

    def get_top_users(self, limit=10, period="daily"):
        """获取使用次数排行榜

        Args:
            limit: 返回用户数量
            period: 统计周期 (daily/weekly/monthly)

        Returns:
            list: 用户排行榜列表
        """
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return []

        try:
            if period == "daily":
                date_str = self.usage_tracker._get_reset_period_date()
                pattern = f"astrbot:usage_stats:{date_str}:user:*"
            elif period == "weekly":
                # 获取本周统计
                week_number = datetime.datetime.now().isocalendar()[1]
                year = datetime.datetime.now().year
                pattern = f"astrbot:trend:weekly:{year}-W{week_number}:user:*"
            else:  # monthly
                month_key = datetime.datetime.now().strftime("%Y-%m")
                pattern = f"astrbot:trend:monthly:{month_key}:user:*"

            keys = redis_client.redis.keys(pattern)
            user_stats = []

            for key in keys:
                data = redis_client.redis.hgetall(key)
                if data:
                    user_id = key.split(":")[-1]
                    total_usage = int(data.get("total_usage", 0))
                    user_stats.append({"user_id": user_id, "usage": total_usage})

            # 按使用次数排序
            user_stats.sort(key=lambda x: x["usage"], reverse=True)

            return user_stats[:limit]
        except Exception as e:
            self.logger.log_error("获取排行榜失败: {}", str(e))
            return []

    def get_usage_distribution(self, group_id=None):
        """获取使用分布情况

        Args:
            group_id: 群组ID（可选），如果提供则返回该群组的分布

        Returns:
            dict: 使用分布数据
        """
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return {}

        try:
            date_str = self.usage_tracker._get_reset_period_date()

            if group_id:
                # 获取群组内用户分布
                pattern = f"astrbot:usage_record:{date_str}:{group_id}:*"
            else:
                # 获取全局分布
                pattern = f"astrbot:usage_stats:{date_str}:user:*"

            keys = redis_client.redis.keys(pattern)
            distribution = {}

            for key in keys:
                if group_id:
                    # 私聊记录
                    user_id = key.split(":")[-1]
                    count = redis_client.redis.llen(key)
                    distribution[user_id] = count
                else:
                    # 统计数据
                    data = redis_client.redis.hgetall(key)
                    if data:
                        user_id = key.split(":")[-1]
                        total_usage = int(data.get("total_usage", 0))
                        distribution[user_id] = total_usage

            return distribution
        except Exception as e:
            self.logger.log_error("获取使用分布失败: {}", str(e))
            return {}

    def calculate_growth_rate(self, current_period, previous_period):
        """计算增长率

        Args:
            current_period: 当前周期数据
            previous_period: 上期周期数据

        Returns:
            float: 增长率百分比
        """
        try:
            if previous_period == 0:
                return 100.0 if current_period > 0 else 0.0

            growth_rate = ((current_period - previous_period) / previous_period) * 100
            return round(growth_rate, 2)
        except Exception as e:
            self.logger.log_error("计算增长率失败: {}", str(e))
            return 0.0

    def format_stats_message(self, stats_data, title="统计信息"):
        """格式化统计消息

        Args:
            stats_data: 统计数据字典
            title: 消息标题

        Returns:
            str: 格式化后的统计消息
        """
        message = f"📊 {title}\n"
        message += "═══════════════\n\n"

        for key, value in stats_data.items():
            message += f"• {key}: {value}\n"

        return message

    def get_today_stats_summary(self):
        """获取今日统计摘要

        Returns:
            dict: 今日统计摘要数据
        """
        redis_client = self.redis_client
        if not redis_client or not redis_client.redis:
            return {}

        try:
            today_key = self.usage_tracker._get_today_key()
            pattern = f"{today_key}:*"
            keys = redis_client.redis.keys(pattern)

            total_calls = 0
            active_users = 0

            for key in keys:
                usage = redis_client.redis.get(key)
                if usage:
                    total_calls += int(usage)
                    active_users += 1

            return {
                "total_calls": total_calls,
                "active_users": active_users,
                "user_limits_count": len(self.plugin.user_limits),
                "group_limits_count": len(self.plugin.group_limits),
                "exempt_users_count": len(self.plugin.config["limits"]["exempt_users"]),
            }
        except Exception as e:
            self.logger.log_error("获取今日统计摘要失败: {}", str(e))
            return {}
