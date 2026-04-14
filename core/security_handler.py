"""
安全处理模块

负责处理安全相关命令，包括防刷机制状态查询、启用/禁用、配置查看等。
"""

import time

from astrbot.api.event import AstrMessageEvent, MessageEventResult


class SecurityHandler:
    """安全处理类"""

    def __init__(self, plugin):
        """
        初始化SecurityHandler

        Args:
            plugin: 插件实例引用
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.config = plugin.config

    async def handle_security_status(self, event: AstrMessageEvent):
        """
        处理安全状态查询

        Args:
            event: 消息事件
        """
        try:
            status_msg = "🛡️ 防刷机制状态\n"
            status_msg += "══════════\n\n"

            # 防刷机制状态
            status_msg += f"• 防刷机制：{'✅ 已启用' if self.plugin.anti_abuse_enabled else '❌ 未启用'}\n"

            # 统计信息
            blocked_count = len(self.plugin.blocked_users)
            monitored_count = len(self.plugin.abuse_records)

            status_msg += f"• 当前被限制用户：{blocked_count} 个\n"
            status_msg += f"• 监控中用户：{monitored_count} 个\n"

            # 异常检测统计
            total_abuse_detections = sum(
                len(records) for records in self.plugin.abuse_records.values()
            )
            status_msg += f"• 累计异常检测：{total_abuse_detections} 次\n"

            # 配置信息
            status_msg += "\n📊 检测阈值配置：\n"
            status_msg += f"• 快速请求：{self.plugin.rapid_request_threshold}次/{self.plugin.rapid_request_window}秒\n"
            status_msg += f"• 连续请求：{self.plugin.consecutive_request_threshold}次/{self.plugin.consecutive_request_window}秒\n"
            status_msg += f"• 自动限制时长：{self.plugin.auto_block_duration}秒\n"

            event.set_result(MessageEventResult().message(status_msg))

        except Exception as e:
            self.logger.log_error("查询安全状态失败: {}", str(e))
            event.set_result(MessageEventResult().message("❌ 查询安全状态失败"))

    async def handle_security_enable(self, event: AstrMessageEvent):
        """
        启用防刷机制

        Args:
            event: 消息事件
        """
        try:
            if self.plugin.anti_abuse_enabled:
                event.set_result(MessageEventResult().message("✅ 防刷机制已经启用"))
                return

            # 启用防刷机制
            self.config["security"]["anti_abuse_enabled"] = True
            self.config.save_config()
            self.plugin.anti_abuse_enabled = True

            event.set_result(MessageEventResult().message("✅ 防刷机制已启用"))

        except Exception as e:
            self.logger.log_error("启用防刷机制失败: {}", str(e))
            event.set_result(MessageEventResult().message("❌ 启用防刷机制失败"))

    async def handle_security_disable(self, event: AstrMessageEvent):
        """
        禁用防刷机制

        Args:
            event: 消息事件
        """
        try:
            if not self.plugin.anti_abuse_enabled:
                event.set_result(MessageEventResult().message("✅ 防刷机制已经禁用"))
                return

            # 禁用防刷机制
            self.config["security"]["anti_abuse_enabled"] = False
            self.config.save_config()
            self.plugin.anti_abuse_enabled = False

            # 清除所有限制记录
            self.plugin.blocked_users.clear()
            self.plugin.abuse_records.clear()
            self.plugin.abuse_stats.clear()

            event.set_result(
                MessageEventResult().message("✅ 防刷机制已禁用，所有限制记录已清除")
            )

        except Exception as e:
            self.logger.log_error("禁用防刷机制失败: {}", str(e))
            event.set_result(MessageEventResult().message("❌ 禁用防刷机制失败"))

    async def handle_security_config(self, event: AstrMessageEvent):
        """
        查看安全配置

        Args:
            event: 消息事件
        """
        try:
            config_msg = "⚙️ 当前安全配置\n"
            config_msg += "══════════\n\n"

            config_msg += f"• 防刷机制：{'✅ 已启用' if self.plugin.anti_abuse_enabled else '❌ 未启用'}\n"
            config_msg += f"• 快速请求阈值：{self.plugin.rapid_request_threshold}次/{self.plugin.rapid_request_window}秒\n"
            config_msg += f"• 连续请求阈值：{self.plugin.consecutive_request_threshold}次/{self.plugin.consecutive_request_window}秒\n"
            config_msg += f"• 自动限制时长：{self.plugin.auto_block_duration}秒\n"
            config_msg += f"• 管理员通知：{'✅ 已启用' if self.plugin.admin_notification_enabled else '❌ 未启用'}\n"
            config_msg += f"• 管理员用户数：{len(self.plugin.admin_users)} 个\n"

            # 显示通知模板（截取前50字符）
            template_preview = self.plugin.block_notification_template[:50]
            if len(self.plugin.block_notification_template) > 50:
                template_preview += "..."
            config_msg += f"• 限制通知模板：{template_preview}\n"

            config_msg += "\n💡 配置说明：\n"
            config_msg += "• 快速请求：检测短时间内的大量请求\n"
            config_msg += "• 连续请求：检测连续不间断的请求\n"
            config_msg += "• 自动限制：检测到异常后自动限制用户\n"

            event.set_result(MessageEventResult().message(config_msg))

        except Exception as e:
            self.logger.log_error("查看安全配置失败: {}", str(e))
            event.set_result(MessageEventResult().message("❌ 查看安全配置失败"))

    async def handle_security_blocklist(self, event: AstrMessageEvent):
        """
        查看被限制用户列表

        Args:
            event: 消息事件
        """
        try:
            if not self.plugin.blocked_users:
                event.set_result(
                    MessageEventResult().message("📋 当前没有被限制的用户")
                )
                return

            blocklist_msg = "🚫 被限制用户列表\n"
            blocklist_msg += "═══════════\n\n"

            current_time = time.time()
            for user_id, block_info in self.plugin.blocked_users.items():
                remaining_time = max(0, block_info["block_until"] - current_time)
                minutes = int(remaining_time // 60)
                seconds = int(remaining_time % 60)

                blocklist_msg += f"• 用户 {user_id}\n"
                blocklist_msg += f"  原因：{block_info['reason']}\n"
                blocklist_msg += f"  剩余时间：{minutes}分{seconds}秒\n"
                blocklist_msg += f"  限制时长：{block_info['duration']}秒\n\n"

            event.set_result(MessageEventResult().message(blocklist_msg))

        except Exception as e:
            self.logger.log_error("查看限制列表失败: {}", str(e))
            event.set_result(MessageEventResult().message("❌ 查看限制列表失败"))

    async def handle_security_unblock(self, event: AstrMessageEvent, user_id: str):
        """
        解除用户限制

        Args:
            event: 消息事件
            user_id: 用户ID
        """
        try:
            user_id = str(user_id)

            if user_id not in self.plugin.blocked_users:
                event.set_result(
                    MessageEventResult().message(f"✅ 用户 {user_id} 没有被限制")
                )
                return

            # 解除限制
            del self.plugin.blocked_users[user_id]

            # 清除异常记录
            if user_id in self.plugin.abuse_records:
                del self.plugin.abuse_records[user_id]
            if user_id in self.plugin.abuse_stats:
                del self.plugin.abuse_stats[user_id]

            event.set_result(
                MessageEventResult().message(f"✅ 已解除用户 {user_id} 的限制")
            )

        except Exception as e:
            self.logger.log_error("解除用户限制失败: {}", str(e))
            event.set_result(MessageEventResult().message("❌ 解除用户限制失败"))

    async def handle_security_stats(self, event: AstrMessageEvent, user_id: str):
        """
        查看用户异常行为统计

        Args:
            event: 消息事件
            user_id: 用户ID
        """
        try:
            user_id = str(user_id)

            stats_msg = f"📊 用户 {user_id} 异常行为统计\n"
            stats_msg += "═════════════\n\n"

            # 检查是否被限制
            if user_id in self.plugin.blocked_users:
                block_info = self.plugin.blocked_users[user_id]
                remaining_time = max(0, block_info["block_until"] - time.time())
                minutes = int(remaining_time // 60)
                seconds = int(remaining_time % 60)

                stats_msg += "🚫 当前状态：被限制\n"
                stats_msg += f"• 限制原因：{block_info['reason']}\n"
                stats_msg += f"• 剩余限制时间：{minutes}分{seconds}秒\n"
                stats_msg += f"• 限制开始时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block_info['blocked_at']))}\n\n"
            else:
                stats_msg += "✅ 当前状态：正常\n\n"

            # 异常记录统计
            if user_id in self.plugin.abuse_records:
                records = self.plugin.abuse_records[user_id]
                current_time = time.time()

                # 最近1小时内的记录
                recent_records = [t for t in records if t > current_time - 3600]

                stats_msg += "📈 最近1小时请求统计：\n"
                stats_msg += f"• 总请求次数：{len(recent_records)} 次\n"

                if recent_records:
                    # 计算请求频率
                    time_range = (
                        max(recent_records) - min(recent_records)
                        if len(recent_records) > 1
                        else 1
                    )
                    frequency = len(recent_records) / max(time_range, 1)
                    stats_msg += f"• 平均频率：{frequency:.2f} 次/秒\n"

                    # 最近请求时间
                    last_request = max(recent_records)
                    time_since_last = current_time - last_request
                    stats_msg += f"• 最后请求：{int(time_since_last)} 秒前\n"

                # 异常检测统计
                if user_id in self.plugin.abuse_stats:
                    user_stats = self.plugin.abuse_stats[user_id]
                    stats_msg += "\n⚠️ 异常检测统计：\n"
                    stats_msg += (
                        f"• 连续请求计数：{user_stats['consecutive_count']} 次\n"
                    )
                    stats_msg += f"• 最后请求时间：{time.strftime('%H:%M:%S', time.localtime(user_stats['last_request_time']))}\n"

            else:
                stats_msg += "📊 该用户暂无异常行为记录\n"

            event.set_result(MessageEventResult().message(stats_msg))

        except Exception as e:
            self.logger.log_error("查看用户统计失败: {}", str(e))
            event.set_result(MessageEventResult().message("❌ 查看用户统计失败"))
