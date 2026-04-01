"""
消息配置处理模块

负责处理自定义提醒消息配置，包括消息验证、设置、重置等。
"""

from astrbot.api.event import AstrMessageEvent, MessageEventResult


class MessagesHandler:
    """消息配置处理类"""

    def __init__(self, plugin):
        """
        初始化MessagesHandler

        Args:
            plugin: 插件实例引用
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.config = plugin.config

    def get_default_messages(self) -> dict:
        """
        获取默认消息配置

        Returns:
            dict: 默认消息配置字典
        """
        return {
            "zero_usage_message": "您的AI访问次数已达上限（{usage}/{limit}），请稍后再试或联系管理员提升限额。",
            "zero_usage_group_shared_message": "本群组AI访问次数已达上限（{usage}/{limit}），请稍后再试或联系管理员提升限额。",
            "zero_usage_group_individual_message": "您在本群组的AI访问次数已达上限（{usage}/{limit}），请稍后再试或联系管理员提升限额。",
            "limit_status_private_message": "👤 个人使用状态\n📊 今日已使用：{usage}/{limit} 次\n📈 {progress_bar}\n🎯 剩余次数：{remaining} 次\n\n💡 使用提示：{usage_tip}\n🔄 每日重置时间：{reset_time}",
            "limit_status_group_shared_message": "👥 群组共享模式 - {limit_type}\n📊 今日已使用：{usage}/{limit} 次\n📈 {progress_bar}\n🎯 剩余次数：{remaining} 次\n\n💡 使用提示：{usage_tip}\n🔄 每日重置时间：{reset_time}",
            "limit_status_group_individual_message": "👤 个人独立模式 - {limit_type}\n📊 今日已使用：{usage}/{limit} 次\n📈 {progress_bar}\n🎯 剩余次数：{remaining} 次\n\n💡 使用提示：{usage_tip}\n🔄 每日重置时间：{reset_time}",
            "limit_status_exempt_message": "🎉 您{group_context}没有调用次数限制（豁免用户）",
            "limit_status_time_period_message": "\n\n⏰ 当前处于时间段限制：{start_time}-{end_time}\n📋 时间段限制：{time_period_limit} 次\n📊 时间段内已使用：{time_period_usage}/{time_period_limit} 次\n📈 {time_period_progress}\n🎯 时间段内剩余：{time_period_remaining} 次",
        }

    def get_valid_message_types(self) -> list:
        """
        获取有效的消息类型列表

        Returns:
            list: 有效的消息类型列表
        """
        return [
            "zero_usage_message",
            "zero_usage_group_shared_message",
            "zero_usage_group_individual_message",
            "limit_status_private_message",
            "limit_status_group_shared_message",
            "limit_status_group_individual_message",
            "limit_status_exempt_message",
            "limit_status_time_period_message",
        ]

    def validate_message_content(self, msg_type: str, msg_content: str) -> bool:
        """
        验证消息内容格式

        Args:
            msg_type: 消息类型
            msg_content: 消息内容

        Returns:
            bool: 验证成功返回True，失败返回False
        """
        if msg_type.startswith("zero_usage") and (
            "{usage}" not in msg_content or "{limit}" not in msg_content
        ):
            return False
        return True

    async def handle_messages_help(self, event: AstrMessageEvent) -> None:
        """
        处理消息配置帮助命令

        Args:
            event: 消息事件
        """
        custom_messages = self.config["limits"].get("custom_messages", {})

        help_msg = "📝 自定义提醒消息配置\n"
        help_msg += "═══════════════════\n\n"

        # 显示当前配置
        if custom_messages:
            help_msg += "当前配置：\n"
            for msg_type, msg_content in custom_messages.items():
                help_msg += f"• {msg_type}: {msg_content}\n"
            help_msg += "\n"
        else:
            help_msg += "当前使用默认消息配置\n\n"

        help_msg += "使用方式：\n"
        help_msg += "/limit messages list - 查看当前消息配置\n"
        help_msg += "/limit messages set <类型> <消息内容> - 设置自定义消息\n"
        help_msg += "/limit messages reset <类型> - 重置指定类型的消息为默认值\n"
        help_msg += "/limit messages reset_all - 重置所有消息为默认值\n\n"

        help_msg += "可用消息类型：\n"
        help_msg += "• zero_usage_message - 私聊使用次数为0时的消息\n"
        help_msg += (
            "• zero_usage_group_shared_message - 群组共享模式使用次数为0时的消息\n"
        )
        help_msg += (
            "• zero_usage_group_individual_message - 群组独立模式使用次数为0时的消息\n"
        )
        help_msg += "• limit_status_private_message - /limit_status 私聊状态消息\n"
        help_msg += (
            "• limit_status_group_shared_message - /limit_status 群组共享模式状态消息\n"
        )
        help_msg += "• limit_status_group_individual_message - /limit_status 群组独立模式状态消息\n"
        help_msg += "• limit_status_exempt_message - /limit_status 豁免用户状态消息\n"
        help_msg += (
            "• limit_status_time_period_message - /limit_status 时间段限制状态消息\n\n"
        )

        help_msg += "支持变量：\n"
        help_msg += "• {usage} - 已使用次数\n"
        help_msg += "• {limit} - 限制次数\n"
        help_msg += "• {remaining} - 剩余次数\n"
        help_msg += "• {user_name} - 用户名\n"
        help_msg += "• {group_name} - 群组名\n"
        help_msg += "• {progress_bar} - 进度条\n"
        help_msg += "• {usage_tip} - 使用提示\n"
        help_msg += "• {reset_time} - 重置时间\n"
        help_msg += "• {limit_type} - 限制类型（特定/默认/群组）\n"
        help_msg += "• {group_context} - 群组上下文\n"
        help_msg += "• {start_time} - 时间段开始时间\n"
        help_msg += "• {end_time} - 时间段结束时间\n"
        help_msg += "• {time_period_limit} - 时间段限制次数\n"
        help_msg += "• {time_period_usage} - 时间段内已使用次数\n"
        help_msg += "• {time_period_progress} - 时间段进度条\n"
        help_msg += "• {time_period_remaining} - 时间段内剩余次数"

        event.set_result(MessageEventResult().message(help_msg))

    async def handle_messages_list(self, event: AstrMessageEvent) -> None:
        """
        处理消息列表命令

        Args:
            event: 消息事件
        """
        custom_messages = self.config["limits"].get("custom_messages", {})

        if not custom_messages:
            event.set_result(MessageEventResult().message("当前使用默认消息配置"))
            return

        msg_list = "📝 当前自定义消息配置：\n"
        msg_list += "═══════════════════\n\n"

        for msg_type, msg_content in custom_messages.items():
            msg_list += f"🔹 {msg_type}:\n"
            msg_list += f"   {msg_content}\n\n"

        event.set_result(MessageEventResult().message(msg_list))

    async def handle_messages_set(self, event: AstrMessageEvent, args: list) -> None:
        """
        处理消息设置命令

        Args:
            event: 消息事件
            args: 命令参数列表
        """
        msg_type = args[3]
        msg_content = " ".join(args[4:])

        valid_types = self.get_valid_message_types()
        if msg_type not in valid_types:
            event.set_result(
                MessageEventResult().message(
                    f"无效的消息类型，可用类型：{', '.join(valid_types)}"
                )
            )
            return

        if not self.validate_message_content(msg_type, msg_content):
            event.set_result(
                MessageEventResult().message(
                    "zero_usage消息类型必须包含 {usage} 和 {limit} 变量"
                )
            )
            return

        # 保存自定义消息配置
        if "custom_messages" not in self.config["limits"]:
            self.config["limits"]["custom_messages"] = {}

        self.config["limits"]["custom_messages"][msg_type] = msg_content
        self.config.save_config()

        event.set_result(
            MessageEventResult().message(
                f"✅ 已设置 {msg_type} 的自定义消息\n\n新消息内容：\n{msg_content}"
            )
        )

    async def handle_messages_reset(self, event: AstrMessageEvent, args: list) -> None:
        """
        处理消息重置命令

        Args:
            event: 消息事件
            args: 命令参数列表
        """
        msg_type = args[3]

        valid_types = self.get_valid_message_types()
        if msg_type not in valid_types:
            event.set_result(
                MessageEventResult().message(
                    f"无效的消息类型，可用类型：{', '.join(valid_types)}"
                )
            )
            return

        default_messages = self.get_default_messages()

        # 如果存在自定义配置，则删除该类型
        if (
            "custom_messages" in self.config["limits"]
            and msg_type in self.config["limits"]["custom_messages"]
        ):
            del self.config["limits"]["custom_messages"][msg_type]
            # 如果自定义配置为空，则删除整个配置节
            if not self.config["limits"]["custom_messages"]:
                del self.config["limits"]["custom_messages"]
            self.config.save_config()

        event.set_result(
            MessageEventResult().message(
                f"✅ 已重置 {msg_type} 为默认消息\n\n默认消息内容：\n{default_messages[msg_type]}"
            )
        )

    async def handle_messages_reset_all(self, event: AstrMessageEvent) -> None:
        """
        处理重置所有消息命令

        Args:
            event: 消息事件
        """
        if "custom_messages" in self.config["limits"]:
            del self.config["limits"]["custom_messages"]
            self.config.save_config()

        event.set_result(MessageEventResult().message("✅ 已重置所有消息为默认值"))
