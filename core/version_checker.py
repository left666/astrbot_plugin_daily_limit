"""
版本检查模块

负责检查和通知插件版本更新，包括：
- 版本检查初始化
- 定期版本检查循环
- 版本信息解析
- 版本号比较
- 版本更新通知
"""

import asyncio

import aiohttp

from astrbot.api.event import MessageChain


class VersionChecker:
    """版本检查类"""

    def __init__(self, plugin):
        """
        初始化版本检查器

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.context = plugin.context

        # 版本检查相关变量
        self.version_check_task = None  # 版本检查异步任务
        self.last_checked_version = None  # 上次检查的版本号
        self.last_notified_version = None  # 上次通知的版本号
        self.last_checked_version_info = None  # 上次检查的完整版本信息

    def init_version_check(self):
        """初始化版本检查功能"""
        try:
            # 检查是否启用版本检查功能
            if not self.plugin.config["version_check"].get("enabled", True):
                self.logger.log_info("版本检查功能已禁用")
                return

            # 启动版本检查异步任务
            self.version_check_task = asyncio.create_task(self._version_check_loop())
            self.logger.log_info(
                "版本检查功能已启动，检查间隔：{} 分钟",
                self.plugin.config["version_check"].get("check_interval", 60),
            )

        except Exception as e:
            self.logger.handle_error(e, "初始化版本检查功能")

    async def _version_check_loop(self):
        """版本检查循环任务"""
        while True:
            try:
                # 获取检查间隔（分钟）
                check_interval = self.plugin.config["version_check"].get("check_interval", 60)

                # 执行版本检查
                await self.check_version_update()

                # 等待指定时间后再次检查
                await asyncio.sleep(check_interval * 60)

            except Exception as e:
                self.logger.handle_error(e, "版本检查循环任务")
                # 出错后等待5分钟再重试
                await asyncio.sleep(300)

    async def check_version_update(self):
        """检查版本更新"""
        try:
            # 获取版本检查URL
            check_url = self.plugin.config["version_check"].get(
                "check_url", "https://box.firefly520.top/limit_update.txt"
            )

            self.logger.log_info("开始检查版本更新")

            # 发送HTTP请求获取版本信息
            async with aiohttp.ClientSession() as session:
                async with session.get(check_url, timeout=30) as response:
                    if response.status != 200:
                        self.logger.log_warning(
                            "版本检查请求失败，状态码: {}", response.status
                        )
                        return

                    content = await response.text()

            # 解析版本信息
            version_info = self._parse_version_info(content)
            if not version_info:
                self.logger.log_warning("版本信息解析失败")
                return

            self.last_checked_version = version_info["version"]
            self.last_checked_version_info = version_info  # 存储完整的版本信息

            # 比较版本号
            current_version = self.plugin.config.get("version", "v2.8.7")
            if self._compare_versions(version_info["version"], current_version) > 0:
                # 检测到新版本
                self.logger.log_info(
                    "检测到新版本: {} -> {}", current_version, version_info["version"]
                )

                # 检查是否需要发送通知
                # 如果配置了重复通知或版本不同，则发送通知
                repeat_notification = self.plugin.config["version_check"].get(
                    "repeat_notification", False
                )
                if (
                    repeat_notification
                    or self.last_notified_version != version_info["version"]
                ):
                    await self._send_version_notification(current_version, version_info)
                    self.last_notified_version = version_info["version"]
                else:
                    self.logger.log_info(
                        "已发送过版本 {} 的通知，跳过重复发送", version_info["version"]
                    )
            else:
                self.logger.log_info("当前已是最新版本: {}", current_version)

        except asyncio.TimeoutError:
            self.logger.log_warning("版本检查请求超时")
        except Exception as e:
            self.logger.handle_error(e, "检查版本更新")

    def _parse_version_info(self, content: str) -> dict:
        """解析版本信息文件内容"""
        try:
            version_info = {}
            lines = content.strip().split("\n")

            for line in lines:
                line = line.strip()
                if line.startswith("v："):
                    version_info["version"] = line[2:].strip()
                elif line.startswith("c："):
                    version_info["content"] = line[2:].strip()

            # 验证必需字段
            if "version" not in version_info:
                self.logger.log_warning("版本信息文件中缺少版本号")
                return None

            return version_info

        except Exception as e:
            self.logger.handle_error(e, "解析版本信息")
            return None

    def _compare_versions(self, version1: str, version2: str) -> int:
        """比较两个版本号

        Args:
            version1: 第一个版本号
            version2: 第二个版本号

        Returns:
            int: 1表示version1 > version2, -1表示version1 < version2, 0表示相等
        """
        try:
            # 移除版本号前缀（如"v"）
            v1 = version1.lstrip("vV")
            v2 = version2.lstrip("vV")

            # 分割版本号
            parts1 = v1.split(".")
            parts2 = v2.split(".")

            # 比较每个部分
            for i in range(max(len(parts1), len(parts2))):
                p1 = int(parts1[i]) if i < len(parts1) else 0
                p2 = int(parts2[i]) if i < len(parts2) else 0

                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1

            return 0

        except Exception as e:
            self.logger.handle_error(e, "比较版本号")
            return 0

    async def _send_version_notification(
        self, current_version: str, version_info: dict
    ):
        """发送新版本通知给管理员"""
        try:
            # 获取管理员用户列表
            admin_users = self.plugin.config["version_check"].get("admin_users", [])
            if not admin_users:
                self.logger.log_warning("未配置管理员用户，无法发送版本更新通知")
                return

            # 获取通知消息模板
            template = self.plugin.config["version_check"].get(
                "notification_message",
                "🚀 检测到新版本可用！\n📦 当前版本：{current_version}\n🆕 最新版本：{new_version}\n📝 更新内容：{update_content}\n🔗 下载地址：{download_url}",
            )

            # 格式化消息
            message = template.format(
                current_version=current_version,
                new_version=version_info.get("version", "未知"),
                update_content=version_info.get("content", "暂无更新说明"),
                download_url="https://github.com/left666/astrbot_plugin_daily_limit",
            )

            # 发送给每个管理员
            for user_id in admin_users:
                try:
                    # 创建消息链
                    message_chain = MessageChain().message(message)

                    # 构建会话唯一标识（格式：平台:消息类型:会话ID）
                    # 对于私聊消息，格式为：QQ:FriendMessage:用户ID
                    unified_msg_origin = f"QQ:FriendMessage:{user_id}"

                    # 发送主动消息给管理员
                    await self.context.send_message(unified_msg_origin, message_chain)
                    self.logger.log_info("已发送新版本通知给管理员: {}", user_id)

                except Exception as e:
                    self.logger.handle_error(e, f"发送版本通知给管理员 {user_id}")

        except Exception as e:
            self.logger.handle_error(e, "发送版本通知")
