"""
消息构建模块

负责生成各种状态消息和用户提示，包括：
- 进度条生成
- 状态消息构建
- 自定义消息处理
- 使用提示生成
"""

import datetime


class MessageBuilder:
    """消息构建类"""

    def __init__(self, plugin):
        """
        初始化消息构建器

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.config_mgr = plugin.config_mgr
        self.limiter = plugin.limiter

    def generate_progress_bar(self, usage, limit, bar_length=10):
        """生成进度条"""
        if limit <= 0:
            return ""

        percentage = (usage / limit) * 100
        filled_length = int(bar_length * usage // limit)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)

        return f"[{bar}] {percentage:.1f}%"

    def get_custom_zero_usage_message(
        self, usage, limit, user_name, group_name, group_mode=None
    ):
        """获取自定义的使用次数为0时的提醒消息"""
        # 获取自定义消息配置
        custom_messages = self.plugin.config["limits"].get("custom_messages", {})

        # 计算剩余次数
        remaining = limit - usage

        # 根据不同的场景选择不同的消息模板
        if group_mode is not None:
            # 群组消息
            if group_mode == "shared":
                # 群组共享模式
                message_template = custom_messages.get(
                    "zero_usage_group_shared_message",
                    "本群组AI访问次数已达上限（{usage}/{limit}），请稍后再试或联系管理员提升限额。",
                )
            else:
                # 群组独立模式
                message_template = custom_messages.get(
                    "zero_usage_group_individual_message",
                    "您在本群组的AI访问次数已达上限（{usage}/{limit}），请稍后再试或联系管理员提升限额。",
                )
        else:
            # 私聊消息
            message_template = custom_messages.get(
                "zero_usage_message",
                "您的AI访问次数已达上限（{usage}/{limit}），请稍后再试或联系管理员提升限额。",
            )

        # 替换模板中的变量
        message = message_template.format(
            usage=usage,
            limit=limit,
            remaining=remaining,
            user_name=user_name or "用户",
            group_name=group_name or "群组",
        )

        return message

    def get_reset_time(self):
        """获取每日重置时间"""
        # 获取配置的重置时间
        reset_time_str = self.plugin.config["limits"].get("daily_reset_time", "00:00")

        # 验证重置时间格式
        try:
            reset_hour, reset_minute = map(int, reset_time_str.split(":"))
            if not (0 <= reset_hour <= 23 and 0 <= reset_minute <= 59):
                raise ValueError("重置时间格式错误")
            # 返回datetime.time对象
            return datetime.time(reset_hour, reset_minute)
        except (ValueError, AttributeError):
            # 如果配置格式错误，使用默认的00:00
            self.logger.log_warning(
                "重置时间配置格式错误: {}，使用默认值00:00", reset_time_str
            )
            return datetime.time(0, 0)

    def get_custom_message(self, message_type, default_message, **kwargs):
        """获取自定义消息模板

        Args:
            message_type: 消息类型
            default_message: 默认消息模板
            **kwargs: 模板变量

        Returns:
            str: 格式化后的消息
        """
        # 获取自定义消息配置
        custom_messages = self.plugin.config["limits"].get("custom_messages", {})

        # 如果配置了自定义消息，则使用自定义消息，否则使用默认消息
        template = custom_messages.get(message_type, default_message)

        # 格式化消息模板
        try:
            return template.format(**kwargs)
        except KeyError as e:
            self.logger.log_warning("消息模板变量错误: {}，使用默认消息", e)
            return default_message.format(**kwargs)
        except Exception as e:
            self.logger.log_error("消息模板格式化错误: {}", e)
            return default_message

    def get_usage_tip(self, remaining, limit):
        """根据剩余次数生成使用提示"""
        # 优先使用配置项中的自定义提示文本
        custom_tip = self.plugin.config["limits"].get(
            "usage_tip", "每日限制次数会在重置时间自动恢复"
        )

        # 如果配置了自定义提示，直接返回
        if custom_tip:
            return custom_tip

        # 否则使用智能提示逻辑
        if remaining <= 0:
            return "⚠️ 今日次数已用完，请明天再试"
        elif remaining <= limit * 0.2:  # 剩余20%以下
            return "⚠️ 剩余次数较少，请谨慎使用"
        elif remaining <= limit * 0.5:  # 剩余50%以下
            return "💡 剩余次数适中，可继续使用"
        else:
            return "✅ 剩余次数充足，可放心使用"

    def get_limit_type(self, user_id, group_id):
        """获取限制类型描述"""
        if str(user_id) in self.plugin.user_limits:
            return "特定限制"
        elif group_id and str(group_id) in self.plugin.group_limits:
            return "群组限制"
        else:
            return "默认限制"

    def get_current_time_period_info(self, current_time_str):
        """获取当前时间段信息"""
        for period in self.plugin.time_period_limits:
            if self.plugin.limiter.is_in_time_period(
                current_time_str, period["start_time"], period["end_time"]
            ):
                return period
        return None

    def build_exempt_user_status(
        self, user_id, group_id, time_period_limit, current_time_str
    ):
        """构建豁免用户状态消息"""
        group_context = "在本群组" if group_id is not None else ""

        status_msg = self.get_custom_message(
            "limit_status_exempt_message",
            "🎉 您{group_context}没有调用次数限制（豁免用户）",
            group_context=group_context,
        )

        # 添加时间段限制信息（即使豁免用户也显示）
        if time_period_limit is not None:
            current_period_info = self.get_current_time_period_info(current_time_str)
            if current_period_info:
                time_period_msg = self.get_custom_message(
                    "limit_status_time_period_message",
                    "\n\n⏰ 当前处于时间段限制：{start_time}-{end_time}\n📋 时间段限制：{time_period_limit} 次",
                    start_time=current_period_info["start_time"],
                    end_time=current_period_info["end_time"],
                    time_period_limit=time_period_limit,
                )
                status_msg += time_period_msg

        return status_msg

    def build_shared_group_status(self, user_id, group_id, limit, reset_time):
        """构建群组共享模式状态消息"""
        usage = self.plugin._get_group_usage(group_id)
        remaining = limit - usage

        # 检查是否显示进度条
        show_progress = self.plugin.config["limits"].get("show_progress_bar", True)
        progress_bar = (
            self.generate_progress_bar(usage, limit) if show_progress else ""
        )

        # 检查是否显示剩余次数
        show_remaining = self.plugin.config["limits"].get("show_remaining_count", True)
        remaining_text = f"\n🎯 剩余次数：{remaining} 次" if show_remaining else ""

        usage_tip = self.get_usage_tip(remaining, limit)
        limit_type = "特定限制" if str(group_id) in self.plugin.group_limits else "默认限制"

        # 构建消息模板
        base_template = (
            "👥 群组共享模式 - {limit_type}\n📊 今日已使用：{usage}/{limit} 次"
        )
        if show_progress:
            base_template += "\n📈 {progress_bar}"
        if show_remaining:
            base_template += "\n🎯 剩余次数：{remaining} 次"
        base_template += "\n\n💡 使用提示：{usage_tip}\n🔄 每日重置时间：{reset_time}"

        return self.get_custom_message(
            "limit_status_group_shared_message",
            base_template,
            limit_type=limit_type,
            usage=usage,
            limit=limit,
            progress_bar=progress_bar,
            remaining=remaining,
            usage_tip=usage_tip,
            reset_time=reset_time,
        )

    def build_individual_group_status(self, user_id, group_id, limit, reset_time):
        """构建群组独立模式状态消息"""
        usage = self.plugin._get_user_usage(user_id, group_id)
        remaining = limit - usage

        # 检查是否显示进度条
        show_progress = self.plugin.config["limits"].get("show_progress_bar", True)
        progress_bar = (
            self.generate_progress_bar(usage, limit) if show_progress else ""
        )

        # 检查是否显示剩余次数
        show_remaining = self.plugin.config["limits"].get("show_remaining_count", True)
        remaining_text = f"\n🎯 剩余次数：{remaining} 次" if show_remaining else ""

        usage_tip = self.get_usage_tip(remaining, limit)
        limit_type = self.get_limit_type(user_id, group_id)

        # 构建消息模板
        base_template = (
            "👤 个人独立模式 - {limit_type}\n📊 今日已使用：{usage}/{limit} 次"
        )
        if show_progress:
            base_template += "\n📈 {progress_bar}"
        if show_remaining:
            base_template += "\n🎯 剩余次数：{remaining} 次"
        base_template += "\n\n💡 使用提示：{usage_tip}\n🔄 每日重置时间：{reset_time}"

        return self.get_custom_message(
            "limit_status_group_individual_message",
            base_template,
            limit_type=limit_type,
            usage=usage,
            limit=limit,
            progress_bar=progress_bar,
            remaining=remaining,
            usage_tip=usage_tip,
            reset_time=reset_time,
        )

    def build_private_status(self, user_id, group_id, limit, reset_time):
        """构建私聊状态消息"""
        usage = self.plugin._get_user_usage(user_id, group_id)
        remaining = limit - usage

        # 检查是否显示进度条
        show_progress = self.plugin.config["limits"].get("show_progress_bar", True)
        progress_bar = (
            self.generate_progress_bar(usage, limit) if show_progress else ""
        )

        # 检查是否显示剩余次数
        show_remaining = self.plugin.config["limits"].get("show_remaining_count", True)
        remaining_text = f"\n🎯 剩余次数：{remaining} 次" if show_remaining else ""

        usage_tip = self.get_usage_tip(remaining, limit)

        # 构建消息模板
        base_template = "👤 个人使用状态\n📊 今日已使用：{usage}/{limit} 次"
        if show_progress:
            base_template += "\n📈 {progress_bar}"
        if show_remaining:
            base_template += "\n🎯 剩余次数：{remaining} 次"
        base_template += "\n\n💡 使用提示：{usage_tip}\n🔄 每日重置时间：{reset_time}"

        return self.get_custom_message(
            "limit_status_private_message",
            base_template,
            usage=usage,
            limit=limit,
            progress_bar=progress_bar,
            remaining=remaining,
            usage_tip=usage_tip,
            reset_time=reset_time,
        )

    def add_time_period_info(
        self, status_msg, user_id, group_id, time_period_limit, current_time_str
    ):
        """添加时间段限制信息到状态消息"""
        if time_period_limit is not None:
            current_period_info = self.get_current_time_period_info(current_time_str)
            if current_period_info:
                time_period_usage = self.plugin._get_time_period_usage(user_id, group_id)
                time_period_remaining = time_period_limit - time_period_usage
                time_period_progress = self.generate_progress_bar(
                    time_period_usage, time_period_limit
                )

                time_period_msg = self.get_custom_message(
                    "limit_status_time_period_message",
                    "\n\n⏰ 当前处于时间段限制：{start_time}-{end_time}\n📋 时间段限制：{time_period_limit} 次\n📊 时间段内已使用：{time_period_usage}/{time_period_limit} 次\n📈 {time_period_progress}\n🎯 时间段内剩余：{time_period_remaining} 次",
                    start_time=current_period_info["start_time"],
                    end_time=current_period_info["end_time"],
                    time_period_limit=time_period_limit,
                    time_period_usage=time_period_usage,
                    time_period_progress=time_period_progress,
                    time_period_remaining=time_period_remaining,
                )
                status_msg += time_period_msg

        return status_msg
