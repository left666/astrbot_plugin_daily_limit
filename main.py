import asyncio
import datetime
import importlib.util
import json
import os
import sys
import time

import aiohttp

import astrbot.api.star as star  # type: ignore
from astrbot.api import AstrBotConfig  # type: ignore
from astrbot.api.event import (  # type: ignore
    AstrMessageEvent,
    MessageChain,
    MessageEventResult,
    filter,
)
from astrbot.api.event.filter import PermissionType  # type: ignore
from astrbot.api.platform import MessageType  # type: ignore
from astrbot.api.provider import ProviderRequest  # type: ignore

# Web服务器导入
WebServer = None
try:
    # 添加当前目录到Python路径
    import os
    import sys

    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    from web_server import WebServer
except ImportError:
    # 注意：在模块级别不能使用self，这里只是定义变量
    WebServer = None
    # 实际的日志记录将在插件初始化后进行

# 核心模块导入 - 使用 importlib 从特定路径导入，避免与其他插件冲突
Logger = None
RedisClient = None
ConfigManager = None
ConfigLoader = None
Limiter = None
Security = None
UsageTracker = None
MessageBuilder = None
VersionChecker = None
HelpManager = None
StatsAnalyzer = None
TimePeriodManager = None
WebManager = None
RedisKeys = None
SecurityHandler = None
MessagesHandler = None
_import_error = None

def _load_core_module(module_name):
    """从插件的 core 目录加载模块"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    core_dir = os.path.join(current_dir, "core")
    module_path = os.path.join(core_dir, f"{module_name}.py")

    spec = importlib.util.spec_from_file_location(f"astrbot_daily_limit.core.{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法为 {module_name} 创建模块规范")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"astrbot_daily_limit.core.{module_name}"] = module
    spec.loader.exec_module(module)
    return module

try:
    Logger = _load_core_module("logger").Logger
    RedisClient = _load_core_module("redis_client").RedisClient
    ConfigManager = _load_core_module("config_manager").ConfigManager
    ConfigLoader = _load_core_module("config_loader").ConfigLoader
    Limiter = _load_core_module("limiter").Limiter
    Security = _load_core_module("security").Security
    UsageTracker = _load_core_module("usage_tracker").UsageTracker
    MessageBuilder = _load_core_module("message_builder").MessageBuilder
    VersionChecker = _load_core_module("version_checker").VersionChecker
    HelpManager = _load_core_module("help_manager").HelpManager
    StatsAnalyzer = _load_core_module("stats_analyzer").StatsAnalyzer
    TimePeriodManager = _load_core_module("time_period_manager").TimePeriodManager
    WebManager = _load_core_module("web_manager").WebManager
    RedisKeys = _load_core_module("redis_keys").RedisKeys
    SecurityHandler = _load_core_module("security_handler").SecurityHandler
    MessagesHandler = _load_core_module("messages_handler").MessagesHandler
except Exception as e:
    _import_error = str(e)


@star.register(
    name="daily_limit",
    desc="限制用户每日调用大模型的次数",
    author="left666 & Sakura520222",
    version="v2.8.7",
    repo="https://github.com/left666/astrbot_plugin_daily_limit",
)
class DailyLimitPlugin(star.Star):
    """限制群组成员每日调用大模型的次数"""

    def __init__(self, context: star.Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.context = context
        self.config = config
        self.group_limits = {}  # 群组特定限制 {"group_id": limit_count}
        self.user_limits = {}  # 用户特定限制 {"user_id": limit_count}
        self.group_modes = {}  # 群组模式配置 {"group_id": "shared"或"individual"}
        self.time_period_limits = []  # 时间段限制配置
        self.usage_records = {}  # 使用记录 {"user_id": {"date": count}}
        self.skip_patterns = []  # 忽略处理的模式列表
        self.web_server = None  # Web服务器实例
        self.web_server_thread = None  # Web服务器线程

        # 版本检查相关变量
        self.version_check_task = None  # 版本检查异步任务
        self.last_checked_version = None  # 上次检查的版本号
        self.last_notified_version = None  # 上次通知的版本号

        # 安全增强相关变量
        self.abuse_records = {}  # 异常行为记录 {"user_id": {"timestamp": count}}
        self.blocked_users = {}  # 被限制的用户 {"user_id": "block_until_timestamp"}
        self.abuse_stats = {}  # 异常统计 {"user_id": {"total_abuse_count": count, "last_abuse_time": timestamp}}
        self.zero_usage_notified_users = {}  # 零使用次数提醒记录 {"user_id": last_notified_timestamp}

        # 初始化核心模块（必须最先初始化，因为其他代码依赖日志）
        required_modules = [
            Logger, RedisClient, ConfigManager, ConfigLoader, Limiter, Security,
            UsageTracker, MessageBuilder, VersionChecker, HelpManager,
            StatsAnalyzer, TimePeriodManager, WebManager, RedisKeys,
            SecurityHandler, MessagesHandler
        ]
        if any(m is None for m in required_modules):
            # 核心模块导入失败，无法继续
            error_msg = f"核心模块导入失败。导入错误: {_import_error}"
            raise RuntimeError(error_msg)

        # 所有核心模块都可用，进行初始化
        self.logger = Logger(self)
        self.redis_client = RedisClient(self)
        self.config_mgr = ConfigManager(self)
        self.config_loader = ConfigLoader(self)
        self.limiter = Limiter(self)
        self.security = Security(self)
        self.usage_tracker = UsageTracker(self)
        self.message_builder = MessageBuilder(self)
        self.version_checker = VersionChecker(self)
        self.help_manager = HelpManager(self)
        self.stats_analyzer = StatsAnalyzer(self)
        self.time_period_mgr = TimePeriodManager(self)
        self.web_manager = WebManager(self)
        self.redis_keys = RedisKeys(self)
        self.security_handler = SecurityHandler(self)
        self.messages_handler = MessagesHandler(self)

        # 加载群组和用户特定限制（通过ConfigLoader模块）
        self.config_loader.load_limits_from_config()

        # 将安全模块数据引用到实例变量，保持向后兼容
        self.abuse_records = self.security.abuse_records
        self.blocked_users = self.security.blocked_users
        self.abuse_stats = self.security.abuse_stats
        self.anti_abuse_enabled = self.security.anti_abuse_enabled

        # 初始化Redis连接
        self._init_redis()

        # 初始化Web服务器（通过WebManager模块）
        if WebServer is None:
            self._log_warning("Web服务器模块导入失败，Web管理界面功能将不可用")
        else:
            # 初始化Web服务器
            self.web_manager.init_web_server()
            # 同步web_server引用
            self.web_server = self.web_manager.web_server

        # 初始化版本检查功能
        self.version_checker.init_version_check()

    def _load_limits_from_config(self):
        """从配置文件加载群组和用户特定限制（代理方法）"""
        self.config_loader.load_limits_from_config()

    def _parse_limits_config(
        self, config_key: str, limits_dict: dict, limit_type: str
    ) -> None:
        """通用限制配置解析方法（代理方法）"""
        self.config_loader.parse_limits_config(config_key, limits_dict, limit_type)

    def _parse_group_limits(self):
        """解析群组特定限制配置（代理方法）"""
        self.config_loader.parse_group_limits()

    def _parse_user_limits(self):
        """解析用户特定限制配置（代理方法）"""
        self.config_loader.parse_user_limits()

    def _parse_config_lines(self, config_text, parser_func):
        """通用配置行解析器（代理方法）"""
        self.config_loader.parse_config_lines(config_text, parser_func)

    def _log(self, level: str, message: str, *args) -> None:
        """统一的日志记录方法"""
        self.logger.log(level, message, *args)

    def _log_warning(self, message, *args):
        """警告日志记录"""
        self.logger.log_warning(message, *args)

    def _log_error(self, message, *args):
        """错误日志记录"""
        self.logger.log_error(message, *args)

    def _log_info(self, message, *args):
        """信息日志记录"""
        self.logger.log_info(message, *args)

    def _handle_error(
        self, error: Exception, context: str = "", user_message: str = None
    ) -> None:
        """统一的错误处理方法"""
        self.logger.handle_error(error, context, user_message)

    def _safe_execute(
        self, func, *args, context: str = "", default_return=None, **kwargs
    ):
        """安全执行函数，捕获异常并记录"""
        return self.logger.safe_execute(func, *args, context=context, default_return=default_return, **kwargs)

    def _validate_redis_connection(self) -> bool:
        """验证Redis连接状态"""
        return self.redis_client.validate_redis_connection()

    def get_redis_status(self):
        """获取Redis连接状态信息"""
        return self.redis_client.get_redis_status()

    def _reconnect_redis(self):
        """重新连接Redis"""
        result = self.redis_client.reconnect_redis()
        self.redis = self.redis_client.redis
        return result

    def _validate_config_structure(self) -> bool:
        """验证配置结构完整性（代理方法）"""
        return self.config_loader.validate_config_structure()

    def _safe_parse_int(self, value_str, default=None):
        """安全解析整数（代理方法）"""
        return self.config_loader.safe_parse_int(value_str, default)

    def _validate_config_line(self, line, required_separator=":", min_parts=2):
        """验证配置行格式（代理方法）"""
        return self.config_loader.validate_config_line(line, required_separator, min_parts)

    def _parse_limit_line(self, line, limits_dict, limit_type):
        """解析单行限制配置（代理方法）"""
        self.config_loader.parse_limit_line(line, limits_dict, limit_type)

    def _parse_group_modes(self):
        """解析群组模式配置（代理方法）"""
        self.config_loader.parse_group_modes()

    def _parse_group_mode_line(self, line):
        """解析单行群组模式配置（代理方法）"""
        self.config_loader.parse_group_mode_line(line)

    def _load_skip_patterns(self):
        """加载忽略模式配置（代理方法）"""
        self.config_loader.load_skip_patterns()

    def _load_security_config(self):
        """加载安全配置（代理方法）"""
        self.config_loader.load_security_config()

    def _load_basic_security_config(self, security_config):
        """加载基础安全配置（代理方法）"""
        self.config_loader.load_basic_security_config(security_config)

    def _load_detection_thresholds(self, security_config):
        """加载检测阈值配置（代理方法）"""
        self.config_loader.load_detection_thresholds(security_config)

    def _load_auto_block_config(self, security_config):
        """加载自动限制配置（代理方法）"""
        self.config_loader.load_auto_block_config(security_config)

    def _load_notification_config(self, security_config):
        """加载通知配置（代理方法）"""
        self.config_loader.load_notification_config(security_config)

    def _init_notification_records(self):
        """初始化通知记录（代理方法）"""
        self.config_loader.init_notification_records()

    def _set_default_security_config(self):
        """设置默认安全配置（代理方法）"""
        self.config_loader.set_default_security_config()

    def _validate_daily_reset_time(self):
        """验证每日重置时间配置（代理方法）"""
        self.config_loader.validate_daily_reset_time()

    def _detect_abuse_behavior(self, user_id, timestamp=None):
        """检测异常使用行为

        这是异常检测的主入口函数，负责协调整个检测流程。

        参数:
            user_id: 用户ID（字符串或数字）
            timestamp: 当前时间戳（可选，默认使用当前时间）

        返回:
            dict: 检测结果，包含以下字段：
                - is_abuse (bool): 是否检测到异常行为
                - reason (str): 检测结果描述
                - type (str, 可选): 异常类型（如"rapid_request", "consecutive_request"）
                - count (int, 可选): 异常请求次数
                - block_until (float, 可选): 限制结束时间戳
                - original_reason (str, 可选): 原始限制原因
        """
        if self.security:
            return self.security.detect_abuse_behavior(user_id, timestamp)

        # 使用内置实现（兼容旧代码）
        if not self.anti_abuse_enabled:
            return {"is_abuse": False, "reason": "防刷机制未启用"}

        try:
            return self._execute_abuse_detection_pipeline(user_id, timestamp)
        except Exception as e:
            self._log_error("检测异常使用行为失败: {}", str(e))
            return {"is_abuse": False, "reason": "检测失败"}

    def _execute_abuse_detection_pipeline(self, user_id, timestamp):
        """执行异常检测流水线

        这是异常检测的核心流程，按顺序执行以下步骤：
        1. 清理过期通知记录
        2. 检查用户限制状态
        3. 初始化用户记录
        4. 记录当前请求并清理过期记录
        5. 执行异常检测规则
        6. 更新用户统计信息

        参数:
            user_id: 用户ID（字符串）
            timestamp: 当前时间戳（可选）

        返回:
            dict: 检测结果，格式与 _detect_abuse_behavior 相同
        """
        user_id = str(user_id)
        current_time = timestamp or time.time()

        try:
            # 执行异常检测流程
            return self._run_abuse_detection_flow(user_id, current_time)

        except Exception as e:
            self._log_error("异常检测流水线执行失败 - 用户 {}: {}", user_id, str(e))
            # 在检测过程中发生异常时，返回安全结果，避免误判
            return {"is_abuse": False, "reason": "检测过程异常，允许使用"}

    def _run_abuse_detection_flow(self, user_id, current_time):
        """执行异常检测流程

        参数:
            user_id: 用户ID（字符串）
            current_time: 当前时间戳

        返回:
            dict: 检测结果
        """
        # 步骤1: 清理过期通知记录
        self._cleanup_expired_notifications(current_time)

        # 步骤2: 检查用户是否已被限制
        block_check_result = self._check_user_block_status(user_id, current_time)
        if block_check_result["is_abuse"]:
            return block_check_result

        # 步骤3: 初始化用户记录
        self._init_user_records(user_id)

        # 步骤4: 记录用户请求并清理过期记录
        self._record_user_request(user_id, current_time)

        # 步骤5: 执行异常检测规则
        abuse_result = self._execute_abuse_detection_rules(user_id, current_time)
        if abuse_result["is_abuse"]:
            return abuse_result

        # 步骤6: 更新用户统计信息
        self._update_user_stats(user_id, current_time)

        return {"is_abuse": False, "reason": "正常使用"}

    def _execute_abuse_detection_rules(self, user_id, current_time):
        """执行异常检测规则

        按顺序执行以下检测规则：
        1. 快速请求检测：检查用户在短时间内是否发送过多请求
        2. 连续请求检测：检查用户是否连续发送请求（间隔时间过短）

        参数:
            user_id: 用户ID（字符串）
            current_time: 当前时间戳

        返回:
            dict: 检测结果，如果任一规则检测到异常则立即返回
        """
        try:
            # 检测快速请求异常
            rapid_request_result = self._detect_rapid_requests(user_id, current_time)
            if rapid_request_result["is_abuse"]:
                return rapid_request_result

            # 检测连续请求异常
            consecutive_request_result = self._detect_consecutive_requests(
                user_id, current_time
            )
            if consecutive_request_result["is_abuse"]:
                return consecutive_request_result

            return {"is_abuse": False, "reason": "所有检测规则通过"}

        except Exception as e:
            self._log_error("异常检测规则执行失败 - 用户 {}: {}", user_id, str(e))
            # 在规则检测过程中发生异常时，返回安全结果
            return {"is_abuse": False, "reason": "规则检测异常，允许使用"}

    def _cleanup_expired_notifications(self, current_time):
        """清理过期通知记录（保留最近24小时的数据）"""
        try:
            notification_cutoff_time = current_time - 86400  # 24小时
            if hasattr(self, "notified_users"):
                self.notified_users = {
                    uid: time
                    for uid, time in self.notified_users.items()
                    if time > notification_cutoff_time
                }
            if hasattr(self, "notified_admins"):
                self.notified_admins = {
                    uid: time
                    for uid, time in self.notified_admins.items()
                    if time > notification_cutoff_time
                }
        except Exception as e:
            self._log_error("清理过期通知记录失败: {}", str(e))
            # 清理失败不影响主要功能，继续执行

    def _check_user_block_status(self, user_id, current_time):
        """检查用户是否已被限制"""
        try:
            if hasattr(self, "blocked_users") and user_id in self.blocked_users:
                block_info = self.blocked_users[user_id]
                if current_time < block_info["block_until"]:
                    return {
                        "is_abuse": True,
                        "reason": "用户已被限制",
                        "block_until": block_info["block_until"],
                        "original_reason": block_info["reason"],
                    }
                else:
                    # 限制已过期，移除记录
                    self._cleanup_expired_block(user_id)
            return {"is_abuse": False, "reason": "用户未被限制"}
        except Exception as e:
            self._log_error("检查用户限制状态失败 - 用户 {}: {}", user_id, str(e))
            # 检查失败时返回安全结果
            return {"is_abuse": False, "reason": "限制状态检查异常，允许使用"}

    def _cleanup_expired_block(self, user_id):
        """清理过期的用户限制记录"""
        del self.blocked_users[user_id]
        if user_id in self.abuse_records:
            del self.abuse_records[user_id]
        if user_id in self.abuse_stats:
            del self.abuse_stats[user_id]

    def _init_user_records(self, user_id):
        """初始化用户记录"""
        try:
            if not hasattr(self, "abuse_records"):
                self.abuse_records = {}
            if not hasattr(self, "abuse_stats"):
                self.abuse_stats = {}

            if user_id not in self.abuse_records:
                self.abuse_records[user_id] = []
            if user_id not in self.abuse_stats:
                self.abuse_stats[user_id] = {
                    "last_request_time": 0,
                    "consecutive_count": 0,
                    "rapid_count": 0,
                }
        except Exception as e:
            self._log_error("初始化用户记录失败 - 用户 {}: {}", user_id, str(e))
            # 初始化失败不影响主要功能，继续执行

    def _record_user_request(self, user_id, current_time):
        """记录用户请求并清理过期记录"""
        try:
            # 确保记录字典存在
            if not hasattr(self, "abuse_records") or user_id not in self.abuse_records:
                self._init_user_records(user_id)

            # 记录当前请求
            self.abuse_records[user_id].append(current_time)

            # 清理过期记录（保留最近1小时的数据）
            cutoff_time = current_time - 3600
            self.abuse_records[user_id] = [
                t for t in self.abuse_records[user_id] if t > cutoff_time
            ]

        except Exception as e:
            self._log_error("记录用户请求失败 - 用户 {}: {}", user_id, str(e))
            # 记录失败不影响主要功能，继续执行

    def _detect_rapid_requests(self, user_id, current_time):
        """检测快速请求异常"""
        recent_requests = [
            t
            for t in self.abuse_records[user_id]
            if t > current_time - self.rapid_request_window
        ]

        if len(recent_requests) >= self.rapid_request_threshold:
            return {
                "is_abuse": True,
                "reason": f"快速请求异常：{len(recent_requests)}次/{self.rapid_request_window}秒",
                "type": "rapid_request",
                "count": len(recent_requests),
            }
        return {"is_abuse": False, "reason": "快速请求正常"}

    def _detect_consecutive_requests(self, user_id, current_time):
        """检测连续请求异常"""
        stats = self.abuse_stats[user_id]
        time_since_last = (
            current_time - stats["last_request_time"]
            if stats["last_request_time"] > 0
            else float("inf")
        )

        if time_since_last <= self.consecutive_request_window:
            stats["consecutive_count"] += 1
            if stats["consecutive_count"] >= self.consecutive_request_threshold:
                return {
                    "is_abuse": True,
                    "reason": f"连续请求异常：{stats['consecutive_count']}次连续请求",
                    "type": "consecutive_request",
                    "count": stats["consecutive_count"],
                }
        else:
            stats["consecutive_count"] = 1

        return {"is_abuse": False, "reason": "连续请求正常"}

    def _update_user_stats(self, user_id, current_time):
        """更新用户统计信息"""
        self.abuse_stats[user_id]["last_request_time"] = current_time

    async def _block_user_for_abuse(self, user_id, reason, duration=None):
        """限制用户使用

        参数:
            user_id: 用户ID
            reason: 限制原因
            duration: 限制时长（秒），默认使用配置值

        返回:
            dict: 包含限制信息的字典
        """
        if self.security:
            return await self.security.block_user_for_abuse(user_id, reason, duration)

        # 使用内置实现（兼容旧代码）
        try:
            user_id = str(user_id)
            block_duration = duration or self.auto_block_duration
            block_until = time.time() + block_duration

            block_info = {
                "block_until": block_until,
                "reason": reason,
                "blocked_at": time.time(),
                "duration": block_duration,
            }

            self.blocked_users[user_id] = block_info

            self._log_warning(
                "用户 {} 因 {} 被限制使用 {} 秒", user_id, reason, block_duration
            )

            # 注意：管理员通知现在由 _handle_abuse_detected 方法统一处理
            # 避免重复发送通知

            return block_info

        except Exception as e:
            self._log_error("限制用户失败: {}", str(e))
            # 返回一个默认的block_info，避免后续代码出错
            return {
                "block_until": time.time() + 300,  # 默认5分钟
                "reason": reason,
                "blocked_at": time.time(),
                "duration": 300,
            }

    async def _notify_admins_about_block(self, user_id, reason, duration):
        """通知管理员关于用户限制"""
        try:
            from astrbot.api.event import MessageChain

            message = (
                f"🛡️ 防刷机制通知\n"
                f"══════════\n"
                f"• 用户ID：{user_id}\n"
                f"• 限制原因：{reason}\n"
                f"• 限制时长：{duration}秒\n"
                f"• 限制时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
                f"\n💡 如需解除限制，请使用命令：\n"
                f"/limit security unblock {user_id}"
            )

            # 为每个管理员用户发送通知
            for admin_user in self.admin_users:
                try:
                    # 构建管理员用户的会话标识
                    # 格式：platform_name:message_type:session_id
                    # 根据实际UMO格式：QQ:FriendMessage:123456789
                    admin_umo = f"QQ:FriendMessage:{admin_user}"  # QQ平台私聊格式

                    # 创建消息链
                    message_chain = MessageChain().message(message)

                    # 发送主动消息
                    await self.context.send_message(admin_umo, message_chain)
                    self._log_info("已向管理员 {} 发送限制通知", admin_user)

                except Exception as admin_error:
                    self._log_error(
                        "向管理员 {} 发送通知失败: {}", admin_user, str(admin_error)
                    )

            self._log_info("管理员通知发送完成")

        except Exception as e:
            self._log_error("发送管理员通知失败: {}", str(e))

    def _validate_daily_reset_time(self):
        """验证每日重置时间配置"""
        reset_time_str = self.config["limits"].get("daily_reset_time", "00:00")

        # 验证重置时间格式
        try:
            reset_hour, reset_minute = map(int, reset_time_str.split(":"))
            if not (0 <= reset_hour <= 23 and 0 <= reset_minute <= 59):
                raise ValueError("重置时间格式错误")
            self._log_info("重置时间配置验证通过: {}", reset_time_str)
        except (ValueError, AttributeError) as e:
            # 如果配置格式错误，记录警告并使用默认值
            self._log_warning(
                "重置时间配置格式错误: {}，错误: {}，使用默认值00:00", reset_time_str, e
            )
            # 自动修复为默认值
            self.config["limits"]["daily_reset_time"] = "00:00"
            try:
                self.config.save_config()
                self._log_info("已自动修复重置时间配置为默认值00:00")
            except Exception as save_error:
                self._log_error("保存重置时间配置失败: {}", save_error)

    def _save_group_limit(self, group_id, limit):
        """保存群组特定限制到配置文件（新格式：群组ID:限制次数）"""
        group_id = str(group_id)

        # 获取当前配置文本
        current_text = self.config["limits"].get("group_limits", "").strip()
        lines = current_text.split("\n") if current_text else []

        # 查找并更新现有行，或添加新行
        updated = False
        new_lines = []
        for line in lines:
            line = line.strip()
            if line and ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[0].strip() == group_id:
                    # 更新现有行
                    new_lines.append(f"{group_id}:{limit}")
                    updated = True
                else:
                    # 保留其他行
                    new_lines.append(line)

        # 如果没有找到现有行，添加新行
        if not updated:
            new_lines.append(f"{group_id}:{limit}")

        # 更新配置并保存
        self.config["limits"]["group_limits"] = "\n".join(new_lines)
        self.config.save_config()

    def _save_user_limit(self, user_id, limit):
        """保存用户特定限制到配置文件（新格式：用户ID:限制次数）"""
        user_id = str(user_id)

        # 获取当前配置文本
        current_text = self.config["limits"].get("user_limits", "").strip()
        lines = current_text.split("\n") if current_text else []

        # 查找并更新现有行，或添加新行
        updated = False
        new_lines = []
        for line in lines:
            line = line.strip()
            if line and ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[0].strip() == user_id:
                    # 更新现有行
                    new_lines.append(f"{user_id}:{limit}")
                    updated = True
                else:
                    # 保留其他行
                    new_lines.append(line)

        # 如果没有找到现有行，添加新行
        if not updated:
            new_lines.append(f"{user_id}:{limit}")

        # 更新配置并保存
        self.config["limits"]["user_limits"] = "\n".join(new_lines)
        self.config.save_config()

    def _save_group_mode(self, group_id, mode):
        """保存群组模式配置到配置文件（新格式：群组ID:模式）"""
        group_id = str(group_id)

        # 获取当前配置文本
        current_text = self.config["limits"].get("group_mode_settings", "").strip()
        lines = current_text.split("\n") if current_text else []

        # 查找并更新现有行，或添加新行
        updated = False
        new_lines = []
        for line in lines:
            line = line.strip()
            if line and ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[0].strip() == group_id:
                    # 更新现有行
                    new_lines.append(f"{group_id}:{mode}")
                    updated = True
                else:
                    # 保留其他行
                    new_lines.append(line)

        # 如果没有找到现有行，添加新行
        if not updated:
            new_lines.append(f"{group_id}:{mode}")

        # 更新配置并保存
        self.config["limits"]["group_mode_settings"] = "\n".join(new_lines)
        self.config.save_config()

    def _init_redis(self):
        """初始化Redis连接"""
        self.redis_client.init_redis()
        self.redis = self.redis_client.redis

    def _init_web_server(self):
        """
        初始化Web服务器（代理方法）

        返回：
            bool: 初始化成功返回True，失败返回False
        """
        return self.web_manager.init_web_server()

    def _create_web_server_instance(self):
        """创建Web服务器实例（代理方法）"""
        from web_server import WebServer as _WebServer
        web_config = self.config.get("web_server", {})
        host = web_config.get("host", "127.0.0.1")
        port = web_config.get("port", 10245)
        domain = web_config.get("domain", "")
        return _WebServer(self, host=host, port=port, domain=domain)

    def _start_web_server(self):
        """启动Web服务器（代理方法）"""
        return self.web_manager.start_web_server()

    def _handle_web_server_start_success(self):
        """处理Web服务器启动成功的情况（代理方法）"""
        self.web_manager.handle_web_server_start_success()

    def _log_web_server_access_url(self):
        """记录Web服务器访问地址（代理方法）"""
        self.web_manager.log_web_server_access_url()

    def _handle_web_server_start_failure(self):
        """处理Web服务器启动失败的情况（代理方法）"""
        self.web_manager.handle_web_server_start_failure()

    def _handle_web_server_init_error(self, error):
        """处理Web服务器初始化错误（代理方法）"""
        self.web_manager.handle_web_server_init_error(error)

    def _is_web_server_running(self):
        """
        检查Web服务器是否正在运行（代理方法）

        返回：
            bool: Web服务器是否正在运行
        """
        if hasattr(self, "web_server") and self.web_server:
            return self.web_server.is_running()
        return False

    def get_web_server_status(self):
        """
        获取Web服务器状态信息

        返回：
            dict: Web服务器状态信息字典，如果未启动则返回None
        """
        if hasattr(self, "web_server") and self.web_server:
            return self.web_server.get_status()
        return None

    # Redis键生成代理方法
    def _get_today_key(self):
        """获取考虑自定义重置时间的日期键（代理方法）"""
        return self.redis_keys.get_today_key()

    def _get_user_key(self, user_id, group_id=None):
        """获取用户在特定群组的Redis键（代理方法）"""
        return self.redis_keys.get_user_key(user_id, group_id)

    def _get_group_key(self, group_id):
        """获取群组共享的Redis键（代理方法）"""
        return self.redis_keys.get_group_key(group_id)

    def _get_reset_period_date(self):
        """获取考虑自定义重置时间的日期字符串（代理方法）"""
        return self.redis_keys.get_reset_period_date()

    def _get_usage_record_key(self, user_id, group_id=None, date_str=None):
        """获取使用记录Redis键（代理方法）"""
        return self.redis_keys.get_usage_record_key(user_id, group_id, date_str)

    def _get_usage_stats_key(self, date_str=None):
        """获取使用统计Redis键（代理方法）"""
        return self.redis_keys.get_usage_stats_key(date_str)

    def _get_trend_stats_key(self, period_type, period_value):
        """获取趋势统计Redis键（代理方法）"""
        return self.redis_keys.get_trend_stats_key(period_type, period_value)

    def _get_week_number(self, date_obj=None):
        """获取日期对应的周数（代理方法）"""
        return self.redis_keys.get_week_number(date_obj)

    def _get_month_key(self, date_obj=None):
        """获取月份键（代理方法）"""
        return self.redis_keys.get_month_key(date_obj)

    def _get_hour_key(self, date_obj=None):
        """获取小时键（代理方法）"""
        return self.redis_keys.get_hour_key(date_obj)

    def _get_seconds_until_tomorrow(self):
        """获取到下次重置时间的秒数（代理方法）"""
        return self.redis_keys.get_seconds_until_tomorrow()

    def _record_trend_data(self, user_id, group_id=None, usage_type="llm_request"):
        """记录趋势分析数据

        记录小时、日、周、月四个维度的使用趋势数据
        """
        if not self.redis:
            return False

        try:
            current_time = datetime.datetime.now()

            # 记录小时趋势数据，精确到小时级别
            hour_key = self._get_trend_stats_key(
                "hourly", self._get_hour_key(current_time)
            )
            self._update_trend_stats(hour_key, user_id, group_id, usage_type)

            # 记录日趋势数据，使用与主逻辑相同的日期计算
            daily_key = self._get_trend_stats_key(
                "daily", self._get_reset_period_date()
            )
            self._update_trend_stats(daily_key, user_id, group_id, usage_type)

            # 记录周趋势数据
            week_number = self._get_week_number(current_time)
            year = current_time.year
            weekly_key = self._get_trend_stats_key("weekly", f"{year}-W{week_number}")
            self._update_trend_stats(weekly_key, user_id, group_id, usage_type)

            # 记录月趋势数据
            month_key = self._get_trend_stats_key(
                "monthly", self._get_month_key(current_time)
            )
            self._update_trend_stats(month_key, user_id, group_id, usage_type)

            return True
        except Exception as e:
            self._log_error("记录趋势数据失败: {}", str(e))
            return False

    def _update_trend_stats(self, trend_key, user_id, group_id, usage_type):
        """更新趋势统计数据"""
        current_time = datetime.datetime.now()

        # 执行主要统计更新
        self._update_trend_basic_stats(
            trend_key, user_id, group_id, usage_type, current_time
        )

        # 处理小时统计的特殊逻辑
        if "hourly" in trend_key:
            self._update_hourly_stats(trend_key, user_id, group_id, current_time)

        # 更新峰值请求数（非小时统计）
        if "hourly" not in trend_key:
            self._update_peak_stats(trend_key, current_time)

    def _update_trend_basic_stats(
        self, trend_key, user_id, group_id, usage_type, current_time
    ):
        """更新趋势基本统计数据"""
        pipe = self.redis.pipeline()

        # 更新总请求数
        pipe.hincrby(trend_key, "total_requests", 1)

        # 更新用户统计
        pipe.hincrby(trend_key, f"user:{user_id}", 1)

        # 更新群组统计（如果有群组）
        if group_id:
            pipe.hincrby(trend_key, f"group:{group_id}", 1)

        # 更新使用类型统计
        pipe.hincrby(trend_key, f"usage_type:{usage_type}", 1)

        # 记录统计数据的更新时间
        pipe.hset(trend_key, "updated_at", current_time.timestamp())

        # 设置过期时间
        pipe.expire(trend_key, self._get_trend_expiry_seconds(trend_key))

        pipe.execute()

    def _get_trend_expiry_seconds(self, trend_key):
        """获取趋势数据的过期时间（秒）"""
        if "monthly" in trend_key:
            return 180 * 24 * 3600  # 6个月
        elif "weekly" in trend_key:
            return 84 * 24 * 3600  # 12周
        elif "daily" in trend_key:
            return 30 * 24 * 3600  # 30天
        elif "hourly" in trend_key:
            return 7 * 24 * 3600  # 7天
        else:  # daily
            return 30 * 24 * 3600  # 30天

    def _update_hourly_stats(self, trend_key, user_id, group_id, current_time):
        """更新小时统计的特殊数据"""
        pipe = self.redis.pipeline()

        # 记录请求计数
        pipe.hincrby(trend_key, "request_count", 1)

        # 记录当前时间戳
        pipe.hset(trend_key, "last_request_time", current_time.timestamp())

        # 更新活跃用户集
        active_users_key = f"{trend_key}:active_users"
        pipe.sadd(active_users_key, user_id)
        pipe.expire(active_users_key, 7 * 24 * 3600)

        # 如果有群组，更新活跃群组集
        if group_id:
            active_groups_key = f"{trend_key}:active_groups"
            pipe.sadd(active_groups_key, group_id)
            pipe.expire(active_groups_key, 7 * 24 * 3600)

        pipe.execute()

    def _update_peak_stats(self, trend_key, current_time):
        """更新峰值请求数"""
        # 单独获取当前总请求数和峰值，不使用Pipeline
        current_total = self.redis.hget(trend_key, "total_requests")
        current_peak = self.redis.hget(trend_key, "peak_requests")

        # 转换为整数进行比较
        current_total_int = int(current_total) if current_total else 0
        current_peak_int = int(current_peak) if current_peak else 0

        # 如果当前总请求数大于峰值，更新峰值
        if current_total_int > current_peak_int:
            peak_pipe = self.redis.pipeline()
            peak_pipe.hset(trend_key, "peak_requests", current_total_int)
            peak_pipe.hset(trend_key, "peak_time", current_time.timestamp())
            peak_pipe.execute()

    def _should_skip_message(self, message_str):
        """检查消息是否应该忽略处理"""
        return self.limiter.should_skip_message(message_str)

    def _get_group_mode(self, group_id):
        """获取群组的模式配置"""
        return self.limiter.get_group_mode(group_id)

    def _parse_time_string(self, time_str):
        """解析时间字符串为时间对象"""
        return self.limiter.parse_time_string(time_str)

    def _is_in_time_period(self, current_time_str, start_time_str, end_time_str):
        """检查当前时间是否在指定时间段内"""
        return self.limiter.is_in_time_period(current_time_str, start_time_str, end_time_str)

    def _get_current_time_period_limit(self):
        """获取当前时间段适用的限制"""
        return self.limiter.get_current_time_period_limit()

    def _get_time_period_usage_key(self, user_id, group_id=None, time_period_id=None):
        """获取时间段使用次数的Redis键"""
        if self.limiter:
            return self.limiter.get_time_period_usage_key(user_id, group_id, time_period_id)

        # 使用内置实现（兼容旧代码）
        if time_period_id is None:
            # 如果没有指定时间段ID，使用当前时间段
            current_time_str = datetime.datetime.now().strftime("%H:%M")
            for i, time_limit in enumerate(self.time_period_limits):
                if self.time_period_mgr.is_in_time_period(
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

    def _get_time_period_usage(self, user_id, group_id=None):
        """获取用户在时间段内的使用次数"""
        if self.limiter:
            return self.limiter.get_time_period_usage(user_id, group_id)

        # 使用内置实现（兼容旧代码）
        if not self.redis:
            return 0

        key = self.time_period_mgr.get_time_period_usage_key(user_id, group_id)
        if key is None:
            return 0

        usage = self.redis.get(key)
        return int(usage) if usage else 0

    def _increment_time_period_usage(self, user_id, group_id=None):
        """增加用户在时间段内的使用次数"""
        if self.limiter:
            return self.limiter.increment_time_period_usage(user_id, group_id)

        # 使用内置实现（兼容旧代码）
        if not self.redis:
            return False

        key = self.time_period_mgr.get_time_period_usage_key(user_id, group_id)
        if key is None:
            return False

        # 增加计数并设置过期时间
        pipe = self.redis.pipeline()
        pipe.incr(key)

        # 设置过期时间到下次重置时间
        seconds_until_tomorrow = self._get_seconds_until_tomorrow()
        pipe.expire(key, seconds_until_tomorrow)

        pipe.execute()
        return True

    def _get_user_limit(self, user_id, group_id=None):
        """获取用户的调用限制次数"""
        if self.limiter:
            return self.limiter.get_user_limit(user_id, group_id)

        # 使用内置实现（兼容旧代码）
        user_id_str = str(user_id)

        # 检查用户是否豁免（优先级最高）
        if user_id_str in self.config["limits"]["exempt_users"]:
            return float("inf")  # 无限制

        # 检查时间段限制（优先级第二）
        time_period_limit = self.time_period_mgr.get_current_time_period_limit()
        if time_period_limit is not None:
            return time_period_limit

        # 检查用户是否为优先级用户（优先级第三）
        if user_id_str in self.config["limits"].get("priority_users", []):
            # 优先级用户在任何群聊中只受特定限制，不参与特定群聊限制
            if user_id_str in self.user_limits:
                return self.user_limits[user_id_str]
            else:
                return self.config["limits"]["default_daily_limit"]

        # 检查用户特定限制
        if user_id_str in self.user_limits:
            return self.user_limits[user_id_str]

        # 检查群组特定限制
        if group_id and str(group_id) in self.group_limits:
            return self.group_limits[str(group_id)]

        # 返回默认限制
        return self.config["limits"]["default_daily_limit"]

    def _get_usage_by_type(self, user_id=None, group_id=None):
        """通用使用次数获取函数"""
        if not self.redis:
            return 0

        try:
            # 检查时间段限制（优先级最高）
            time_period_limit = self.time_period_mgr.get_current_time_period_limit()
            if time_period_limit is not None:
                # 有时间段限制时，使用时间段内的使用次数
                return self.time_period_mgr.get_time_period_usage(user_id, group_id)

            # 没有时间段限制时，使用日使用次数
            if user_id is None:
                key = self._get_group_key(group_id)
            else:
                key = self._get_user_key(user_id, group_id)

            usage = self.redis.get(key)
            return int(usage) if usage else 0
        except Exception as e:
            self._log_error(
                "获取使用次数失败 (用户: {}, 群组: {}): {}", user_id, group_id, str(e)
            )
            return 0

    def _get_user_usage(self, user_id, group_id=None):
        """获取用户已使用次数（兼容旧版本）"""
        return self._get_usage_by_type(user_id=user_id, group_id=group_id)

    def _get_group_usage(self, group_id):
        """获取群组共享使用次数"""
        return self._get_usage_by_type(group_id=group_id)

    def _increment_usage_by_type(self, user_id=None, group_id=None):
        """通用使用次数增加函数"""
        if not self.redis:
            return False

        try:
            # 检查时间段限制（优先级最高）
            time_period_limit = self.time_period_mgr.get_current_time_period_limit()
            if time_period_limit is not None:
                # 有时间段限制时，增加时间段使用次数
                if self._increment_time_period_usage(user_id, group_id):
                    return True

            # 没有时间段限制时，增加日使用次数
            if user_id is None:
                key = self._get_group_key(group_id)
            else:
                key = self._get_user_key(user_id, group_id)

            # 增加计数并设置过期时间
            pipe = self.redis.pipeline()
            pipe.incr(key)

            # 设置过期时间到下次重置时间
            seconds_until_tomorrow = self._get_seconds_until_tomorrow()
            pipe.expire(key, seconds_until_tomorrow)

            pipe.execute()
            return True
        except Exception as e:
            self._log_error(
                "增加使用次数失败 (用户: {}, 群组: {}): {}", user_id, group_id, str(e)
            )
            return False

    def _increment_user_usage(self, user_id, group_id=None):
        """增加用户使用次数（兼容旧版本）"""
        return self._increment_usage_by_type(user_id=user_id, group_id=group_id)

    def _increment_group_usage(self, group_id):
        """增加群组共享使用次数"""
        return self._increment_usage_by_type(group_id=group_id)

    def _record_usage(self, user_id, group_id=None, usage_type="llm_request"):
        """
        记录使用情况

        参数：
            user_id: 用户ID
            group_id: 群组ID（可选）
            usage_type: 使用类型，默认为"llm_request"

        返回：
            bool: 记录成功返回True，失败返回False
        """
        return self.usage_tracker.record_usage(user_id, group_id, usage_type)

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
        if not self.redis:
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
            self._log_error(
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
        # 更新用户统计
        self.redis.hincrby(keys_to_update["user_stats"], "total_usage", 1)

        # 更新全局统计
        self.redis.hincrby(keys_to_update["global_stats"], "total_requests", 1)

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
            reset_time = self.message_builder.get_reset_time()
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
            date_obj = current_time - datetime.timedelta(days=30 * i)
            month_key = self._get_month_key(date_obj)
            trend_key = self._get_trend_stats_key("monthly", month_key)

            data = self._get_trend_stats_by_key(trend_key)
            if data:
                trend_data[month_key] = data
        return trend_data

    def _get_trend_data(self, period_type, days=7):
        """获取趋势数据

        参数：
            period_type: 统计周期类型 ('daily', 'weekly', 'monthly')
            days: 查询天数（仅对daily类型有效）
        """
        if not self.redis:
            return {}

        try:
            current_time = datetime.datetime.now()

            if period_type == "daily":
                return self._get_daily_trend_data(days, current_time)
            elif period_type == "weekly":
                return self._get_weekly_trend_data(4, current_time)
            elif period_type == "monthly":
                return self._get_monthly_trend_data(6, current_time)
            else:
                return {}

        except Exception as e:
            self._log_error("获取趋势数据失败: {}", str(e))
            return {}

    def _get_trend_stats_by_key(self, trend_key):
        """根据趋势键获取统计数据"""
        try:
            data = self.redis.hgetall(trend_key)
            if not data:
                return None

            # 解析统计数据
            stats = {
                "total_requests": int(data.get("total_requests", 0)),
                "active_users": 0,
                "active_groups": 0,
                "usage_types": {},
            }

            # 统计活跃用户和群组
            user_set = set()
            group_set = set()

            for key, value in data.items():
                if key.startswith("user:"):
                    user_id = key.split(":")[1]
                    user_set.add(user_id)
                    stats["active_users"] = len(user_set)
                elif key.startswith("group:"):
                    group_id = key.split(":")[1]
                    group_set.add(group_id)
                    stats["active_groups"] = len(group_set)
                elif key.startswith("usage_type:"):
                    usage_type = key.split(":")[1]
                    stats["usage_types"][usage_type] = int(value)

            return stats

        except Exception as e:
            self._log_error("解析趋势统计数据失败: {}", str(e))
            return None

    def _set_expiry_for_stats_keys(self, keys_to_update):
        """为统计键设置过期时间"""
        # 计算到明天凌晨的秒数
        seconds_until_tomorrow = self._get_seconds_until_tomorrow()

        # 为所有存在的键设置过期时间
        for key in keys_to_update.values():
            if self.redis.exists(key):
                self.redis.expire(key, seconds_until_tomorrow)

    def _should_process_request(
        self, event: AstrMessageEvent, req: ProviderRequest
    ) -> bool:
        """检查是否应该处理请求（不再调用 stop_event，由调用者决定）"""
        if not self._validate_redis_connection():
            return False

        if not req.prompt.strip() or self._should_skip_message(event.message_str):
            return False

        return True

    def _is_exempt_user(self, user_id: int) -> bool:
        """检查用户是否为豁免用户"""
        return str(user_id) in self.config["limits"]["exempt_users"]

    def _get_usage_info(self, user_id: int, group_id: int | None) -> tuple:
        """
        获取使用信息（使用次数和限制）

        根据用户ID和群组ID获取当前的使用情况信息，包括：
        - 当前使用次数
        - 限制次数
        - 使用类型（个人/群组共享/个人独立）

        参数：
            user_id: 用户ID
            group_id: 群组ID（可选）

        返回：
            tuple: (使用次数, 限制次数, 使用类型描述)
        """
        limit = self._get_user_limit(user_id, group_id)

        if group_id is not None:
            group_mode = self._get_group_mode(group_id)
            if group_mode == "shared":
                usage = self._get_group_usage(group_id)
                usage_type = "群组共享"
            else:
                usage = self._get_user_usage(user_id, group_id)
                usage_type = "个人独立"
        else:
            usage = self._get_user_usage(user_id, group_id)
            usage_type = "个人"

        return usage, limit, usage_type

    async def _handle_abuse_detected(
        self, event: AstrMessageEvent, user_id: int, abuse_result: dict
    ):
        """处理检测到的异常使用行为"""
        try:
            user_id_str = str(user_id)
            current_time = time.time()

            # 检查是否在冷却时间内（避免重复通知）
            if user_id_str in self.notified_users:
                last_notification_time = self.notified_users[user_id_str]
                if current_time - last_notification_time < self.notification_cooldown:
                    self._log_info("用户 {} 在冷却时间内，跳过重复通知", user_id_str)
                    event.stop_event()
                    return

            # 自动限制用户
            block_info = await self._block_user_for_abuse(user_id_str, abuse_result)

            # 发送限制通知（如果不在冷却时间内）
            user_name = event.get_sender_name()
            block_message = self._format_block_notification(
                user_name, abuse_result, block_info
            )

            if event.get_message_type() == MessageType.GROUP_MESSAGE:
                await event.send(
                    MessageChain().at(user_name, user_id).message(block_message)
                )
            else:
                await event.send(MessageChain().message(block_message))

            # 记录通知时间
            self.notified_users[user_id_str] = current_time

            # 记录异常检测日志
            self._log_warning(
                "检测到用户 {} 异常使用行为：{}，已自动限制 {} 秒",
                user_id_str,
                abuse_result["reason"],
                block_info["duration"],
            )

            # 通知管理员（如果启用且不在冷却时间内）
            if self.admin_notification_enabled:
                if user_id_str in self.notified_admins:
                    last_admin_notification_time = self.notified_admins[user_id_str]
                    if (
                        current_time - last_admin_notification_time
                        < self.notification_cooldown
                    ):
                        self._log_info("管理员通知在冷却时间内，跳过重复通知")
                    else:
                        await self._notify_admins_about_block(
                            user_id_str, abuse_result["reason"], block_info["duration"]
                        )
                        self.notified_admins[user_id_str] = current_time
                else:
                    await self._notify_admins_about_block(
                        user_id_str, abuse_result["reason"], block_info["duration"]
                    )
                    self.notified_admins[user_id_str] = current_time

            event.stop_event()

        except Exception as e:
            self._log_error("处理异常使用行为失败: {}", str(e))
            # 即使处理失败，也要阻止请求继续
            event.stop_event()

    def _format_block_notification(
        self, user_name: str, abuse_result: dict, block_info: dict
    ) -> str:
        """格式化限制通知消息"""
        template = self.block_notification_template

        # 替换模板变量
        message = template.replace("{user_name}", user_name)
        message = message.replace("{reason}", abuse_result["reason"])
        message = message.replace("{auto_block_duration}", str(block_info["duration"]))
        message = message.replace(
            "{duration}", str(block_info["duration"])
        )  # 兼容两种占位符

        # 计算剩余时间
        remaining_time = max(0, block_info["block_until"] - time.time())
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)
        message = message.replace("{remaining_time}", f"{minutes}分{seconds}秒")

        return message

    async def _handle_limit_exceeded(
        self,
        event: AstrMessageEvent,
        user_id: int,
        group_id: int | None,
        usage: int,
        limit: int,
    ):
        """处理超过限制的情况"""
        self._log_info("用户 {} 在群 {} 中已达到调用限制 {}", user_id, group_id, limit)

        # 获取自定义消息配置
        custom_messages = self.config["limits"].get("custom_messages", {})

        # 检查是否启用了零使用次数提醒冷却
        cooldown_enabled = custom_messages.get("zero_usage_reminder_enabled", True)

        # 生成唯一标识符（用户ID + 群组ID）
        user_key = f"{user_id}_{group_id}" if group_id else f"{user_id}_private"

        # 如果启用了冷却，检查是否在冷却时间内
        if cooldown_enabled:
            current_time = time.time()
            cooldown_time = custom_messages.get("zero_usage_reminder_cooldown", 300)

            # 检查用户是否在冷却时间内
            if user_key in self.zero_usage_notified_users:
                last_notified_time = self.zero_usage_notified_users[user_key]
                if current_time - last_notified_time < cooldown_time:
                    # 在冷却时间内，不发送提醒
                    self._log_info("用户 {} 在冷却时间内，跳过零使用次数提醒", user_key)
                    event.stop_event()
                    return

        if group_id is not None:
            user_name = event.get_sender_name()
            # 使用群组ID作为群组名称，因为AstrMessageEvent没有get_group_name方法
            group_name = f"群组({group_id})" or "群组"
            group_mode = self._get_group_mode(group_id)

            custom_message = self.message_builder.get_custom_zero_usage_message(
                usage, limit, user_name, group_name, group_mode
            )

            await event.send(
                MessageChain().at(user_name, user_id).message(custom_message)
            )
        else:
            user_name = event.get_sender_name()
            custom_message = self.message_builder.get_custom_zero_usage_message(
                usage, limit, user_name, None, None
            )
            await event.send(MessageChain().message(custom_message))

        # 记录提醒时间
        if cooldown_enabled:
            self.zero_usage_notified_users[user_key] = time.time()

        event.stop_event()

    async def _send_reminder(
        self,
        event: AstrMessageEvent,
        user_id: int,
        group_id: int | None,
        remaining: int,
    ):
        """发送剩余次数提醒"""
        if group_id is not None:
            user_name = event.get_sender_name()
            if self._get_group_mode(group_id) == "shared":
                reminder_msg = f"💡 提醒：本群组剩余AI调用次数为 {remaining} 次"
            else:
                reminder_msg = f"💡 提醒：您在本群组剩余AI调用次数为 {remaining} 次"
            await event.send(
                MessageChain().at(user_name, user_id).message(reminder_msg)
            )
        else:
            reminder_msg = f"💡 提醒：您剩余AI调用次数为 {remaining} 次"
            await event.send(MessageChain().message(reminder_msg))

    def _increment_usage(self, user_id: int, group_id: int | None):
        """
        增加使用次数

        根据群组模式智能增加使用次数：
        - 共享模式：增加群组使用次数
        - 独立模式：增加用户在该群组的使用次数
        - 私聊：增加用户个人使用次数

        参数：
            user_id: 用户ID
            group_id: 群组ID（可选，为None时表示私聊）
        """
        if group_id is not None:
            group_mode = self._get_group_mode(group_id)
            if group_mode == "shared":
                self._increment_group_usage(group_id)
            else:
                self._increment_user_usage(user_id, group_id)
        else:
            self._increment_user_usage(user_id, group_id)

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        处理LLM请求事件

        这是插件的核心事件处理函数，负责：
        - 验证请求是否应该处理
        - 检查用户权限和限制
        - 检测异常使用行为（防刷机制）
        - 记录使用情况
        - 处理超过限制的情况
        - 发送提醒消息

        参数：
            event: AstrMessageEvent对象，包含消息事件信息
            req: ProviderRequest对象，包含LLM请求信息

        返回：
            bool: 是否允许继续处理请求
        """
        # 首先获取用户ID，用于豁免检查
        user_id = event.get_sender_id()

        # 豁免用户检查 - 提前到最前面，确保豁免用户不受任何限制
        if self._is_exempt_user(user_id):
            return True

        # 基础检查（_should_process_request 不再调用 stop_event）
        if not self._should_process_request(event, req):
            event.stop_event()
            return False

        # 防刷机制检测（如果启用）
        if self.anti_abuse_enabled:
            abuse_result = self._detect_abuse_behavior(user_id, time.time())
            if abuse_result["is_abuse"]:
                # 检测到异常使用行为，自动限制用户
                await self._handle_abuse_detected(event, user_id, abuse_result)
                return False

        # 获取群组信息
        group_id = None
        if event.get_message_type() == MessageType.GROUP_MESSAGE:
            group_id = event.get_group_id()

        # 获取使用信息
        usage, limit, usage_type = self._get_usage_info(user_id, group_id)

        # 检查限制
        if usage >= limit:
            await self._handle_limit_exceeded(event, user_id, group_id, usage, limit)
            return False

        # 发送提醒
        remaining = limit - usage
        if remaining in [1, 3, 5]:
            await self._send_reminder(event, user_id, group_id, remaining)

        # 增加使用次数
        self._increment_usage(user_id, group_id)
        self._record_usage(user_id, group_id, "llm_request")

        return True

    @filter.command("limit_status")
    async def limit_status(self, event: AstrMessageEvent):
        """用户查看当前使用状态"""
        user_id = event.get_sender_id()
        group_id = (
            event.get_group_id()
            if event.get_message_type() == MessageType.GROUP_MESSAGE
            else None
        )

        # 检查是否允许普通用户查询使用限制
        allow_normal_check = self.config["limits"].get(
            "allow_normal_users_check_limit", True
        )

        # 如果不允许普通用户查询，检查用户是否是管理员
        # 注意：这里的管理员检查逻辑是简单示例，实际项目中可能需要更复杂的权限检查
        if not allow_normal_check:
            # 这里假设只有在admin_users列表中的用户才能查询
            if str(user_id) not in self.admin_users:
                event.set_result(MessageEventResult().message("您没有权限查询使用限制"))
                return

        # 检查使用状态
        limit = self._get_user_limit(user_id, group_id)
        time_period_limit = self.time_period_mgr.get_current_time_period_limit()
        current_time_str = datetime.datetime.now().strftime("%H:%M")

        # 首先检查用户是否被豁免（优先级最高）
        if str(user_id) in self.config["limits"]["exempt_users"]:
            status_msg = self.message_builder.build_exempt_user_status(
                user_id, group_id, time_period_limit, current_time_str
            )
        else:
            reset_time = self.message_builder.get_reset_time()

            # 根据群组模式显示正确的状态信息
            if group_id is not None:
                group_mode = self._get_group_mode(group_id)
                if group_mode == "shared":
                    status_msg = self.message_builder.build_shared_group_status(
                        user_id, group_id, limit, reset_time
                    )
                else:
                    status_msg = self.message_builder.build_individual_group_status(
                        user_id, group_id, limit, reset_time
                    )
            else:
                status_msg = self.message_builder.build_private_status(
                    user_id, group_id, limit, reset_time
                )

            # 添加时间段限制信息
            status_msg = self.message_builder.add_time_period_info(
                status_msg, user_id, group_id, time_period_limit, current_time_str
            )

        event.set_result(MessageEventResult().message(status_msg))

    @filter.command("限制帮助")
    async def limit_help_all(self, event: AstrMessageEvent):
        """显示本插件所有指令及其帮助信息"""
        help_msg = (
            "🚀 日调用限制插件 v2.8.7 - 完整指令帮助\n"
            "═════════════════════════\n\n"
            "👤 用户指令（所有人可用）：\n"
            "├── /limit_status - 查看您今日的使用状态和剩余次数\n"
            "└── /限制帮助 - 显示本帮助信息\n\n"
            "👨‍💼 管理员指令（仅管理员可用）：\n"
            "├── /limit help - 显示详细管理员帮助信息\n"
            "├── /limit set <用户ID> <次数> - 设置特定用户的每日限制次数\n"
            "├── /limit setgroup <次数> - 设置当前群组的每日限制次数\n"
            "├── /limit setmode <shared|individual> - 设置群组使用模式（共享/独立）\n"
            "├── /limit getmode - 查看当前群组使用模式\n"
            "├── /limit exempt <用户ID> - 将用户添加到豁免列表（不受限制）\n"
            "├── /limit unexempt <用户ID> - 将用户从豁免列表移除\n"
            "├── /limit list_user - 列出所有用户特定限制\n"
            "├── /limit list_group - 列出所有群组特定限制\n"
            "├── /limit stats - 查看今日使用统计信息\n"
            "├── /limit history [用户ID] [天数] - 查询使用历史记录\n"
            "├── /limit analytics [日期] - 多维度统计分析\n"
            "├── /limit top [数量] - 查看使用次数排行榜\n"
            "├── /limit status - 检查插件状态和健康状态\n"
            "├── /limit reset <用户ID|all> - 重置用户使用次数\n"
            "└── /limit skip_patterns - 管理忽略处理的模式配置\n\n"
            "⏰ 时间段限制命令：\n"
            "├── /limit timeperiod list - 列出所有时间段限制配置\n"
            "├── /limit timeperiod add <开始时间> <结束时间> <次数> - 添加时间段限制\n"
            "├── /limit timeperiod remove <索引> - 删除时间段限制\n"
            "├── /limit timeperiod enable <索引> - 启用时间段限制\n"
            "└── /limit timeperiod disable <索引> - 禁用时间段限制\n\n"
            "\n🕐 重置时间管理命令：\n"
            "├── /limit resettime get - 查看当前重置时间\n"
            "├── /limit resettime set <时间> - 设置每日重置时间\n"
            "│   示例：/limit resettime set 06:00 - 设置为早上6点重置\n"
            "└── /limit resettime reset - 重置为默认时间（00:00）\n"
            "🔧 忽略模式管理命令：\n"
            "├── /limit skip_patterns list - 查看当前忽略模式\n"
            "├── /limit skip_patterns add <模式> - 添加忽略模式\n"
            "├── /limit skip_patterns remove <模式> - 移除忽略模式\n"
            "└── /limit skip_patterns reset - 重置为默认模式\n\n"
            "💡 核心功能特性：\n"
            "✅ 智能限制系统：多级权限管理，支持用户、群组、豁免用户三级体系\n"
            "✅ 时间段限制：支持按时间段设置不同的调用限制（优先级最高）\n"
            "✅ 群组协作模式：支持共享模式（群组共享次数）和独立模式（成员独立次数）\n"
            "✅ 数据监控分析：实时监控、使用统计、排行榜和状态监控\n"
            "✅ 使用记录：详细记录每次调用，支持历史查询和统计分析\n"
            "✅ 自定义忽略模式：可配置需要忽略处理的消息前缀\n\n"
            "🎯 优先级规则（从高到低）：\n"
            "1️⃣ ⏰ 时间段限制 - 优先级最高（特定时间段内的限制）\n"
            "2️⃣ 🏆 豁免用户 - 完全不受限制（白名单用户）\n"
            "3️⃣ 👤 用户特定限制 - 针对单个用户的个性化设置\n"
            "4️⃣ 👥 群组特定限制 - 针对整个群组的统一设置\n"
            "5️⃣ ⚙️ 默认限制 - 全局默认设置（兜底规则）\n\n"
            "📊 使用模式说明：\n"
            "• 🔄 共享模式：群组内所有成员共享使用次数（默认模式）\n"
            "   └── 适合小型团队协作，统一管理使用次数\n"
            "• 👤 独立模式：群组内每个成员有独立的使用次数\n"
            "   └── 适合大型团队，成员间互不影响\n\n"
            "🔔 智能提醒：\n"
            "• 📢 剩余次数提醒：当剩余1、3、5次时会自动提醒\n"
            "• 📊 使用状态监控：实时监控使用情况，防止滥用\n\n"
            "📝 使用提示：\n"
            "• 普通用户可使用 /limit_status 查看自己的使用状态\n"
            "• 管理员可使用 /limit help 查看详细管理命令\n"
            "• 时间段限制优先级最高，会覆盖其他限制规则\n"
            "• 默认忽略模式：#、*（可自定义添加）\n\n"
            "📝 版本信息：v2.8.7 | 作者：left666 | 改进：Sakura520222\n"
            "═════════════════════════"
        )

        event.set_result(MessageEventResult().message(help_msg))

    @filter.command_group("limit")
    def limit_command_group(self):
        """限制命令组"""
        pass

    def _get_default_messages(self) -> dict:
        """获取默认消息配置（代理方法）"""
        return self.messages_handler.get_default_messages()

    def _get_valid_message_types(self) -> list:
        """获取有效的消息类型列表（代理方法）"""
        return self.messages_handler.get_valid_message_types()

    def _validate_message_content(self, msg_type: str, msg_content: str) -> bool:
        """验证消息内容格式（代理方法）"""
        return self.messages_handler.validate_message_content(msg_type, msg_content)

    async def _handle_messages_help(self, event: AstrMessageEvent) -> None:
        """处理消息配置帮助命令（代理方法）"""
        await self.messages_handler.handle_messages_help(event)

    async def _handle_messages_list(self, event: AstrMessageEvent) -> None:
        """处理消息列表命令（代理方法）"""
        await self.messages_handler.handle_messages_list(event)

    async def _handle_messages_set(self, event: AstrMessageEvent, args: list) -> None:
        """处理消息设置命令（代理方法）"""
        await self.messages_handler.handle_messages_set(event, args)

    async def _handle_messages_reset(self, event: AstrMessageEvent, args: list) -> None:
        """处理消息重置命令（代理方法）"""
        await self.messages_handler.handle_messages_reset(event, args)

    async def _handle_messages_reset_all(self, event: AstrMessageEvent) -> None:
        """处理重置所有消息命令（代理方法）"""
        await self.messages_handler.handle_messages_reset_all(event)

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("messages")
    async def limit_messages(self, event: AstrMessageEvent):
        """管理自定义提醒消息配置（仅管理员）"""
        args = event.message_str.strip().split()

        # 检查命令格式：/limit messages [action] [type] [message]
        if len(args) < 3:
            await self._handle_messages_help(event)
            return

        action = args[2]

        if action == "list":
            await self._handle_messages_list(event)
        elif action == "set" and len(args) > 4:
            await self._handle_messages_set(event, args)
        elif action == "reset" and len(args) > 3:
            await self._handle_messages_reset(event, args)
        elif action == "reset_all":
            await self._handle_messages_reset_all(event)
        else:
            event.set_result(
                MessageEventResult().message(
                    "无效的命令格式，请使用 /limit messages 查看帮助"
                )
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("skip_patterns")
    async def limit_skip_patterns(self, event: AstrMessageEvent):
        """管理忽略模式配置（仅管理员）"""
        args = event.message_str.strip().split()

        # 检查命令格式：/limit skip_patterns [action] [pattern]
        if len(args) < 3:
            # 显示当前忽略模式和帮助信息
            patterns_str = ", ".join([f'"{pattern}"' for pattern in self.skip_patterns])
            event.set_result(
                MessageEventResult().message(
                    f"当前忽略模式：{patterns_str}\n"
                    f"使用方式：/limit skip_patterns list - 查看当前模式\n"
                    f"使用方式：/limit skip_patterns add <模式> - 添加忽略模式\n"
                    f"使用方式：/limit skip_patterns remove <模式> - 移除忽略模式\n"
                    f"使用方式：/limit skip_patterns reset - 重置为默认模式"
                )
            )
            return

        action = args[2]

        if action == "list":
            # 显示当前忽略模式
            patterns_str = ", ".join([f'"{pattern}"' for pattern in self.skip_patterns])
            event.set_result(
                MessageEventResult().message(f"当前忽略模式：{patterns_str}")
            )

        elif action == "add" and len(args) > 3:
            # 添加忽略模式
            pattern = args[3]
            if pattern in self.skip_patterns:
                event.set_result(
                    MessageEventResult().message(f"忽略模式 '{pattern}' 已存在")
                )
            else:
                self.skip_patterns.append(pattern)
                # 保存到配置文件
                self.config["limits"]["skip_patterns"] = self.skip_patterns
                self.config.save_config()
                event.set_result(
                    MessageEventResult().message(f"已添加忽略模式：'{pattern}'")
                )

        elif action == "remove" and len(args) > 3:
            # 移除忽略模式
            pattern = args[3]
            if pattern in self.skip_patterns:
                self.skip_patterns.remove(pattern)
                # 保存到配置文件
                self.config["limits"]["skip_patterns"] = self.skip_patterns
                self.config.save_config()
                event.set_result(
                    MessageEventResult().message(f"已移除忽略模式：'{pattern}'")
                )
            else:
                event.set_result(
                    MessageEventResult().message(f"忽略模式 '{pattern}' 不存在")
                )

        elif action == "reset":
            # 重置为默认模式
            self.skip_patterns = ["@所有人", "#"]
            # 保存到配置文件
            self.config["limits"]["skip_patterns"] = self.skip_patterns
            self.config.save_config()
            event.set_result(
                MessageEventResult().message("已重置忽略模式为默认值：'@所有人', '#'")
            )

        else:
            event.set_result(
                MessageEventResult().message(
                    "无效的命令格式，请使用 /limit skip_patterns 查看帮助"
                )
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("resettime")
    async def limit_resettime(self, event: AstrMessageEvent):
        """管理每日重置时间配置（仅管理员）"""
        args = event.message_str.strip().split()

        # 检查命令格式：/limit resettime [action] [time]
        if len(args) < 3:
            # 显示当前重置时间配置和帮助信息
            current_reset_time = self.config["limits"].get("daily_reset_time", "00:00")

            help_msg = "🕐 每日重置时间配置管理\n"
            help_msg += "═══════════════════\n\n"
            help_msg += f"当前重置时间：{current_reset_time}\n\n"
            help_msg += "使用方式：\n"
            help_msg += "/limit resettime get - 查看当前重置时间\n"
            help_msg += "/limit resettime set <时间> - 设置每日重置时间\n"
            help_msg += "/limit resettime reset - 重置为默认时间（00:00）\n\n"
            help_msg += "时间格式说明：\n"
            help_msg += "• 格式：HH:MM（24小时制）\n"
            help_msg += "• 示例：/limit resettime set 06:00 - 设置为早上6点重置\n"
            help_msg += (
                "• 示例：/limit resettime set 23:59 - 设置为晚上11点59分重置\n\n"
            )
            help_msg += "💡 功能说明：\n"
            help_msg += "• 每日重置时间决定了使用次数何时清零\n"
            help_msg += "• 默认重置时间为凌晨00:00\n"
            help_msg += "• 设置后，所有用户和群组的使用次数将在指定时间重置\n"

            event.set_result(MessageEventResult().message(help_msg))
            return

        action = args[2]

        if action == "get":
            # 查看当前重置时间
            current_reset_time = self.config["limits"].get("daily_reset_time", "00:00")
            next_reset_time = self._get_reset_time()
            seconds_until_reset = self._get_seconds_until_tomorrow()

            # 计算距离下次重置的时间
            hours_until_reset = seconds_until_reset // 3600
            minutes_until_reset = (seconds_until_reset % 3600) // 60

            status_msg = "🕐 当前重置时间配置\n"
            status_msg += "═══════════════════\n\n"
            status_msg += f"• 当前重置时间：{current_reset_time}\n"
            status_msg += f"• 下次重置时间：{next_reset_time}\n"
            status_msg += (
                f"• 距离下次重置：{hours_until_reset}小时{minutes_until_reset}分钟\n"
            )

            event.set_result(MessageEventResult().message(status_msg))

        elif action == "set" and len(args) > 3:
            # 设置重置时间
            new_time = args[3]

            # 验证时间格式
            try:
                # 使用现有的时间格式验证方法
                if not self._validate_time_format(new_time):
                    event.set_result(
                        MessageEventResult().message(
                            f"❌ 时间格式错误：{new_time}\n请使用 HH:MM 格式（24小时制）\n示例：06:00、23:59"
                        )
                    )
                    return

                # 保存配置
                self.config["limits"]["daily_reset_time"] = new_time
                self.config.save_config()

                # 重新验证配置
                self._validate_daily_reset_time()

                event.set_result(
                    MessageEventResult().message(
                        f"✅ 已设置每日重置时间为 {new_time}\n\n下次重置将在 {self._get_reset_time()} 进行"
                    )
                )

            except Exception as e:
                self._log_error("设置重置时间失败: {}", str(e))
                event.set_result(
                    MessageEventResult().message(f"❌ 设置重置时间失败：{str(e)}")
                )

        elif action == "reset":
            # 重置为默认时间
            if "daily_reset_time" in self.config["limits"]:
                del self.config["limits"]["daily_reset_time"]
                self.config.save_config()

                # 重新验证配置
                self._validate_daily_reset_time()

                event.set_result(
                    MessageEventResult().message("✅ 已重置每日重置时间为默认值 00:00")
                )
            else:
                event.set_result(
                    MessageEventResult().message("✅ 当前已使用默认重置时间 00:00")
                )

        else:
            event.set_result(
                MessageEventResult().message(
                    "❌ 无效的命令格式，请使用 /limit resettime 查看帮助"
                )
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("help")
    async def limit_help(self, event: AstrMessageEvent):
        """显示详细帮助信息（仅管理员）"""
        help_msg = self.help_manager.build_full_help()
        event.set_result(MessageEventResult().message(help_msg))
    @limit_command_group.command("set")
    async def limit_set(
        self, event: AstrMessageEvent, user_id: str = None, limit: int = None
    ):
        """设置特定用户的限制（仅管理员）"""

        if user_id is None or limit is None:
            event.set_result(
                MessageEventResult().message("用法: /limit set <用户ID> <次数>")
            )
            return

        try:
            limit = int(limit)
            if limit < 0:
                event.set_result(
                    MessageEventResult().message("限制次数必须大于或等于0")
                )
                return

            self.user_limits[user_id] = limit
            self._save_user_limit(user_id, limit)

            event.set_result(
                MessageEventResult().message(
                    f"已设置用户 {user_id} 的每日调用限制为 {limit} 次"
                )
            )
        except ValueError:
            event.set_result(MessageEventResult().message("限制次数必须为整数"))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("setgroup")
    async def limit_setgroup(self, event: AstrMessageEvent, limit: int = None):
        """设置当前群组的限制（仅管理员）"""

        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            event.set_result(MessageEventResult().message("此命令只能在群聊中使用"))
            return

        if limit is None:
            event.set_result(
                MessageEventResult().message("用法: /limit setgroup <次数>")
            )
            return

        try:
            limit = int(limit)
            if limit < 0:
                event.set_result(
                    MessageEventResult().message("限制次数必须大于或等于0")
                )
                return

            group_id = event.get_group_id()
            self.group_limits[group_id] = limit
            self._save_group_limit(group_id, limit)

            event.set_result(
                MessageEventResult().message(
                    f"已设置当前群组的每日调用限制为 {limit} 次"
                )
            )
        except ValueError:
            event.set_result(MessageEventResult().message("限制次数必须为整数"))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("setmode")
    async def limit_setmode(self, event: AstrMessageEvent, mode: str = None):
        """设置当前群组的使用模式（仅管理员）"""

        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            event.set_result(MessageEventResult().message("此命令只能在群聊中使用"))
            return

        if mode is None:
            event.set_result(
                MessageEventResult().message("用法: /limit setmode <shared|individual>")
            )
            return

        if mode not in ["shared", "individual"]:
            event.set_result(
                MessageEventResult().message(
                    "模式必须是 'shared'（共享）或 'individual'（独立）"
                )
            )
            return

        group_id = event.get_group_id()
        self.group_modes[group_id] = mode
        self._save_group_mode(group_id, mode)
        mode_text = "共享" if mode == "shared" else "独立"
        event.set_result(
            MessageEventResult().message(f"已设置当前群组的使用模式为 {mode_text} 模式")
        )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("getmode")
    async def limit_getmode(self, event: AstrMessageEvent):
        """查看当前群组的使用模式（仅管理员）"""

        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            event.set_result(MessageEventResult().message("此命令只能在群聊中使用"))
            return

        group_id = event.get_group_id()
        mode = self._get_group_mode(group_id)
        mode_text = "共享" if mode == "shared" else "独立"
        event.set_result(
            MessageEventResult().message(f"当前群组的使用模式为 {mode_text} 模式")
        )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("exempt")
    async def limit_exempt(self, event: AstrMessageEvent, user_id: str = None):
        """将用户添加到豁免列表（仅管理员）"""

        if user_id is None:
            event.set_result(
                MessageEventResult().message("用法: /limit exempt <用户ID>")
            )
            return

        if user_id not in self.config["limits"]["exempt_users"]:
            self.config["limits"]["exempt_users"].append(user_id)
            self.config.save_config()

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("security")
    async def limit_security(self, event: AstrMessageEvent):
        """防刷机制管理命令（仅管理员）"""
        args = event.message_str.strip().split()

        # 检查命令格式：/limit security [action] [user_id]
        if len(args) < 3:
            # 显示安全命令帮助信息
            help_msg = "🛡️ 防刷机制管理命令\n"
            help_msg += "═════════════\n\n"
            help_msg += self._build_security_commands_help()
            event.set_result(MessageEventResult().message(help_msg))
            return

        action = args[2]

        if action == "status":
            await self._handle_security_status(event)
        elif action == "enable":
            await self._handle_security_enable(event)
        elif action == "disable":
            await self._handle_security_disable(event)
        elif action == "config":
            await self._handle_security_config(event)
        elif action == "blocklist":
            await self._handle_security_blocklist(event)
        elif action == "unblock" and len(args) > 3:
            await self._handle_security_unblock(event, args[3])
        elif action == "stats" and len(args) > 3:
            await self._handle_security_stats(event, args[3])
        else:
            event.set_result(
                MessageEventResult().message(
                    "❌ 无效的安全命令，请使用 /limit security 查看帮助"
                )
            )

    async def _handle_security_status(self, event: AstrMessageEvent):
        """处理安全状态查询（代理方法）"""
        await self.security_handler.handle_security_status(event)

    async def _handle_security_enable(self, event: AstrMessageEvent):
        """启用防刷机制（代理方法）"""
        await self.security_handler.handle_security_enable(event)

    async def _handle_security_disable(self, event: AstrMessageEvent):
        """禁用防刷机制（代理方法）"""
        await self.security_handler.handle_security_disable(event)

    async def _handle_security_config(self, event: AstrMessageEvent):
        """查看安全配置（代理方法）"""
        await self.security_handler.handle_security_config(event)

    async def _handle_security_blocklist(self, event: AstrMessageEvent):
        """查看被限制用户列表（代理方法）"""
        await self.security_handler.handle_security_blocklist(event)

    async def _handle_security_unblock(self, event: AstrMessageEvent, user_id: str):
        """解除用户限制（代理方法）"""
        await self.security_handler.handle_security_unblock(event, user_id)

    async def _handle_security_stats(self, event: AstrMessageEvent, user_id: str):
        """查看用户异常行为统计（代理方法）"""
        await self.security_handler.handle_security_stats(event, user_id)

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("unexempt")
    async def limit_unexempt(self, event: AstrMessageEvent, user_id: str = None):
        """将用户从豁免列表移除（仅管理员）"""

        if user_id is None:
            event.set_result(
                MessageEventResult().message("用法: /limit unexempt <用户ID>")
            )
            return

        if user_id in self.config["limits"]["exempt_users"]:
            self.config["limits"]["exempt_users"].remove(user_id)
            self.config.save_config()

            event.set_result(
                MessageEventResult().message(f"已将用户 {user_id} 从豁免列表移除")
            )
        else:
            event.set_result(
                MessageEventResult().message(f"用户 {user_id} 不在豁免列表中")
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("priority")
    async def limit_priority(self, event: AstrMessageEvent, user_id: str = None):
        """将用户添加到优先级列表（仅管理员）"""

        if user_id is None:
            event.set_result(
                MessageEventResult().message("用法: /limit priority <用户ID>")
            )
            return

        if user_id not in self.config["limits"].get("priority_users", []):
            if "priority_users" not in self.config["limits"]:
                self.config["limits"]["priority_users"] = []
            self.config["limits"]["priority_users"].append(user_id)
            self.config.save_config()

            event.set_result(
                MessageEventResult().message(f"已将用户 {user_id} 添加到优先级列表")
            )
        else:
            event.set_result(
                MessageEventResult().message(f"用户 {user_id} 已在优先级列表中")
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("unpriority")
    async def limit_unpriority(self, event: AstrMessageEvent, user_id: str = None):
        """将用户从优先级列表移除（仅管理员）"""

        if user_id is None:
            event.set_result(
                MessageEventResult().message("用法: /limit unpriority <用户ID>")
            )
            return

        if user_id in self.config["limits"].get("priority_users", []):
            self.config["limits"]["priority_users"].remove(user_id)
            self.config.save_config()

            event.set_result(
                MessageEventResult().message(f"已将用户 {user_id} 从优先级列表移除")
            )
        else:
            event.set_result(
                MessageEventResult().message(f"用户 {user_id} 不在优先级列表中")
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("list_exempt")
    async def limit_list_exempt(self, event: AstrMessageEvent):
        """列出所有豁免用户（仅管理员）"""
        if not self.config["limits"]["exempt_users"]:
            event.set_result(MessageEventResult().message("当前没有设置任何豁免用户"))
            return

        exempt_users_str = "豁免用户列表：\n"
        for user_id in self.config["limits"]["exempt_users"]:
            exempt_users_str += f"- 用户 {user_id}\n"

        event.set_result(MessageEventResult().message(exempt_users_str))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("list_priority")
    async def limit_list_priority(self, event: AstrMessageEvent):
        """列出所有优先级用户（仅管理员）"""
        if not self.config["limits"].get("priority_users", []):
            event.set_result(MessageEventResult().message("当前没有设置任何优先级用户"))
            return

        priority_users_str = "优先级用户列表：\n"
        for user_id in self.config["limits"]["priority_users"]:
            priority_users_str += f"- 用户 {user_id}\n"

        event.set_result(MessageEventResult().message(priority_users_str))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("list_user")
    async def limit_list_user(self, event: AstrMessageEvent):
        """列出所有用户特定限制（仅管理员）"""
        if not self.user_limits:
            event.set_result(
                MessageEventResult().message("当前没有设置任何用户特定限制")
            )
            return

        user_limits_str = "用户特定限制列表：\n"
        for user_id, limit in self.user_limits.items():
            user_limits_str += f"- 用户 {user_id}: {limit} 次/天\n"

        event.set_result(MessageEventResult().message(user_limits_str))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("list_group")
    async def limit_list_group(self, event: AstrMessageEvent):
        """列出所有群组特定限制（仅管理员）"""
        if not self.group_limits:
            event.set_result(
                MessageEventResult().message("当前没有设置任何群组特定限制")
            )
            return

        group_limits_str = "群组特定限制列表：\n"
        for group_id, limit in self.group_limits.items():
            group_limits_str += f"- 群组 {group_id}: {limit} 次/天\n"

        event.set_result(MessageEventResult().message(group_limits_str))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("stats")
    async def limit_stats(self, event: AstrMessageEvent):
        """显示插件使用统计信息（仅管理员）"""
        if not self.redis:
            event.set_result(
                MessageEventResult().message("Redis未连接，无法获取统计信息")
            )
            return

        try:
            # 使用 stats_analyzer 获取今日统计摘要
            stats_data = self.stats_analyzer.get_today_stats_summary()

            stats_msg = (
                f"📊 今日统计信息：\n"
                f"• 活跃用户数: {stats_data.get('active_users', 0)}\n"
                f"• 总调用次数: {stats_data.get('total_calls', 0)}\n"
                f"• 用户特定限制数: {stats_data.get('user_limits_count', 0)}\n"
                f"• 群组特定限制数: {stats_data.get('group_limits_count', 0)}\n"
                f"• 豁免用户数: {stats_data.get('exempt_users_count', 0)}"
            )

            event.set_result(MessageEventResult().message(stats_msg))
        except Exception as e:
            self._log_error("获取统计信息失败: {}", str(e))
            event.set_result(MessageEventResult().message("获取统计信息失败"))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("history")
    async def limit_history(
        self, event: AstrMessageEvent, user_id: str = None, days: int = 7
    ):
        """查询使用历史记录（仅管理员）"""
        if not self._validate_redis_connection():
            event.set_result(
                MessageEventResult().message("Redis未连接，无法获取历史记录")
            )
            return

        try:
            if days < 1 or days > 30:
                event.set_result(MessageEventResult().message("查询天数应在1-30之间"))
                return

            # 获取最近days天的使用记录
            date_list = []
            for i in range(days):
                date = datetime.datetime.now() - datetime.timedelta(days=i)
                date_list.append(date.strftime("%Y-%m-%d"))

            if user_id:
                # 查询特定用户的历史记录
                user_records = {}
                for date_str in date_list:
                    # 查询个人聊天记录
                    private_key = self._get_usage_record_key(user_id, None, date_str)
                    private_records = self._safe_execute(
                        lambda: self.redis.lrange(private_key, 0, -1),
                        context=f"查询用户{user_id}在{date_str}的个人记录",
                        default_return=[],
                    )

                    # 查询群组记录
                    group_pattern = f"astrbot:usage_record:{date_str}:*:{user_id}"
                    group_keys = self._safe_execute(
                        lambda: self.redis.keys(group_pattern),
                        context=f"查询用户{user_id}在{date_str}的群组记录键",
                        default_return=[],
                    )

                    daily_total = len(private_records)

                    for key in group_keys:
                        group_records = self._safe_execute(
                            lambda k: self.redis.lrange(k, 0, -1),
                            key,
                            context=f"查询用户{user_id}在群组键{key}的记录",
                            default_return=[],
                        )
                        daily_total += len(group_records)

                    if daily_total > 0:
                        user_records[date_str] = daily_total

                if not user_records:
                    event.set_result(
                        MessageEventResult().message(
                            f"用户 {user_id} 在最近{days}天内没有使用记录"
                        )
                    )
                    return

                history_msg = f"📊 用户 {user_id} 最近{days}天使用历史：\n"
                for date_str, count in sorted(user_records.items(), reverse=True):
                    history_msg += f"• {date_str}: {count}次\n"

                event.set_result(MessageEventResult().message(history_msg))
            else:
                # 查询全局历史记录
                global_stats = {}
                for date_str in date_list:
                    stats_key = self._get_usage_stats_key(date_str)
                    global_key = f"{stats_key}:global"

                    total_requests = self._safe_execute(
                        lambda: self.redis.hget(global_key, "total_requests"),
                        context=f"查询{date_str}全局统计",
                        default_return=None,
                    )
                    if total_requests:
                        global_stats[date_str] = int(total_requests)

                if not global_stats:
                    event.set_result(
                        MessageEventResult().message(f"最近{days}天内没有使用记录")
                    )
                    return

                history_msg = f"📊 最近{days}天全局使用统计：\n"
                for date_str, count in sorted(global_stats.items(), reverse=True):
                    history_msg += f"• {date_str}: {count}次\n"

                event.set_result(MessageEventResult().message(history_msg))

        except Exception as e:
            self._handle_error(e, "历史记录查询", "查询历史记录时发生错误，请稍后重试")
            event.set_result(
                MessageEventResult().message("查询历史记录失败，请稍后重试")
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("trends")
    async def limit_trends(self, event: AstrMessageEvent, period: str = "day"):
        """使用趋势分析（仅管理员）

        Args:
            period: 分析周期，支持 day/week/month
        """
        if not self._validate_redis_connection():
            event.set_result(
                MessageEventResult().message("Redis未连接，无法获取趋势数据")
            )
            return

        try:
            # 验证周期参数
            valid_periods = ["day", "week", "month"]
            if period not in valid_periods:
                event.set_result(
                    MessageEventResult().message(
                        f"无效的分析周期，支持：{', '.join(valid_periods)}"
                    )
                )
                return

            # 映射周期参数到内部类型
            period_mapping = {"day": "daily", "week": "weekly", "month": "monthly"}
            period_type = period_mapping.get(period, "daily")

            # 获取趋势数据
            trend_data = self.stats_analyzer.get_trend_data(period_type)

            if not trend_data:
                event.set_result(
                    MessageEventResult().message(f"暂无{period}周期的趋势数据")
                )
                return

            # 分析趋势数据
            trend_report = self.stats_analyzer.analyze_trends(trend_data)

            # 构建趋势分析消息
            trend_msg = f"📈 {period.capitalize()}使用趋势分析：\n\n"
            trend_msg += trend_report

            event.set_result(MessageEventResult().message(trend_msg))

        except Exception as e:
            self._handle_error(e, "趋势分析", "获取趋势数据时发生错误，请稍后重试")
            event.set_result(
                MessageEventResult().message("获取趋势数据失败，请稍后重试")
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("trends_api")
    async def limit_trends_api(self, event: AstrMessageEvent, period: str = "week"):
        """获取趋势分析API数据（仅管理员）

        Args:
            period: 分析周期，支持 day/week/month
        """
        if not self._validate_redis_connection():
            event.set_result(
                MessageEventResult().message("Redis未连接，无法获取趋势数据")
            )
            return

        try:
            # 验证周期参数
            valid_periods = ["day", "week", "month"]
            if period not in valid_periods:
                event.set_result(
                    MessageEventResult().message(
                        f"无效的分析周期，支持：{', '.join(valid_periods)}"
                    )
                )
                return

            # 映射周期参数到内部类型
            period_mapping = {"day": "daily", "week": "weekly", "month": "monthly"}
            period_type = period_mapping.get(period, "weekly")

            # 获取趋势数据
            trend_data = self.stats_analyzer.get_trend_data(period_type)

            if not trend_data:
                event.set_result(
                    MessageEventResult().message(f"暂无{period}周期的趋势数据")
                )
                return

            # 格式化API响应数据
            api_response = {
                "success": True,
                "period": period,
                "data": trend_data,
                "summary": {
                    "total_periods": len(trend_data),
                    "total_requests": sum(
                        [data.get("total_requests", 0) for data in trend_data.values()]
                    ),
                    "max_active_users": max(
                        [data.get("active_users", 0) for data in trend_data.values()]
                    )
                    if trend_data
                    else 0,
                    "max_active_groups": max(
                        [data.get("active_groups", 0) for data in trend_data.values()]
                    )
                    if trend_data
                    else 0,
                },
            }

            # 返回JSON格式的API数据
            event.set_result(
                MessageEventResult().message(
                    f"📊 {period.capitalize()}趋势分析API数据：\n```json\n{json.dumps(api_response, indent=2, ensure_ascii=False)}\n```"
                )
            )

        except Exception as e:
            self._handle_error(e, "趋势分析API", "获取趋势数据时发生错误，请稍后重试")
            event.set_result(
                MessageEventResult().message("获取趋势数据失败，请稍后重试")
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("analytics")
    async def limit_analytics(self, event: AstrMessageEvent, date_str: str = None):
        """多维度统计分析（仅管理员）"""
        if not self._validate_redis_connection():
            event.set_result(
                MessageEventResult().message("Redis未连接，无法获取分析数据")
            )
            return

        try:
            if date_str is None:
                date_str = self._get_reset_period_date()

            stats_key = self._get_usage_stats_key(date_str)

            # 获取全局统计
            global_key = f"{stats_key}:global"
            total_requests = self._safe_execute(
                lambda: self.redis.hget(global_key, "total_requests"),
                context=f"获取{date_str}全局统计",
                default_return=None,
            )

            # 获取用户统计
            user_pattern = f"{stats_key}:user:*"
            user_keys = self._safe_execute(
                lambda: self.redis.keys(user_pattern),
                context=f"获取{date_str}用户统计键",
                default_return=[],
            )

            # 获取群组统计
            group_pattern = f"{stats_key}:group:*"
            group_keys = self._safe_execute(
                lambda: self.redis.keys(group_pattern),
                context=f"获取{date_str}群组统计键",
                default_return=[],
            )

            analytics_msg = f"📈 {date_str} 多维度统计分析：\n\n"

            # 全局统计
            if total_requests:
                analytics_msg += "🌍 全局统计：\n"
                analytics_msg += f"• 总调用次数: {int(total_requests)}次\n"

            # 用户统计
            if user_keys:
                analytics_msg += "\n👤 用户统计：\n"
                analytics_msg += f"• 活跃用户数: {len(user_keys)}人\n"

                # 计算用户平均使用次数
                user_total = 0
                for key in user_keys:
                    usage = self._safe_execute(
                        lambda k: self.redis.hget(k, "total_usage"),
                        key,
                        context=f"获取用户键{key}的使用统计",
                        default_return=None,
                    )
                    if usage:
                        user_total += int(usage)

                if len(user_keys) > 0:
                    avg_usage = user_total / len(user_keys)
                    analytics_msg += f"• 用户平均使用次数: {avg_usage:.1f}次\n"

            # 群组统计
            if group_keys:
                analytics_msg += "\n👥 群组统计：\n"
                analytics_msg += f"• 活跃群组数: {len(group_keys)}个\n"

                # 计算群组平均使用次数
                group_total = 0
                for key in group_keys:
                    usage = self._safe_execute(
                        lambda k: self.redis.hget(k, "total_usage"),
                        key,
                        context=f"获取群组键{key}的使用统计",
                        default_return=None,
                    )
                    if usage:
                        group_total += int(usage)

                if len(group_keys) > 0:
                    avg_group_usage = group_total / len(group_keys)
                    analytics_msg += f"• 群组平均使用次数: {avg_group_usage:.1f}次\n"

            # 使用分布分析
            if user_keys:
                analytics_msg += "\n📊 使用分布：\n"

                # 统计不同使用频次的用户数量
                usage_levels = {"低(1-5次)": 0, "中(6-20次)": 0, "高(21+次)": 0}

                for key in user_keys:
                    usage = self._safe_execute(
                        lambda k: self.redis.hget(k, "total_usage"),
                        key,
                        context=f"获取用户键{key}的使用分布",
                        default_return=None,
                    )
                    if usage:
                        usage_count = int(usage)
                        if usage_count <= 5:
                            usage_levels["低(1-5次)"] += 1
                        elif usage_count <= 20:
                            usage_levels["中(6-20次)"] += 1
                        else:
                            usage_levels["高(21+次)"] += 1

                for level, count in usage_levels.items():
                    if count > 0:
                        percentage = (count / len(user_keys)) * 100
                        analytics_msg += f"• {level}: {count}人 ({percentage:.1f}%)\n"

            event.set_result(MessageEventResult().message(analytics_msg))

        except Exception as e:
            self._handle_error(e, "统计分析", "获取分析数据时发生错误，请稍后重试")
            event.set_result(
                MessageEventResult().message("获取分析数据失败，请稍后重试")
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("status")
    async def limit_status_admin(self, event: AstrMessageEvent):
        """检查插件状态和健康状态（仅管理员）"""
        try:
            # 检查Redis连接状态
            redis_status = "✅ 正常" if self.redis else "❌ 未连接"

            # 检查Redis连接是否可用
            redis_available = False
            if self.redis:
                try:
                    self.redis.ping()
                    redis_available = True
                except:
                    redis_available = False

            redis_available_status = "✅ 可用" if redis_available else "❌ 不可用"

            # 获取配置信息
            default_limit = self.config["limits"]["default_daily_limit"]
            exempt_users_count = len(self.config["limits"]["exempt_users"])
            group_limits_count = len(self.group_limits)
            user_limits_count = len(self.user_limits)

            # 获取今日统计
            today_stats = "无法获取"
            if self.redis and redis_available:
                try:
                    today_key = self._get_today_key()
                    pattern = f"{today_key}:*"
                    keys = self.redis.keys(pattern)

                    total_calls = 0
                    active_users = 0

                    for key in keys:
                        usage = self.redis.get(key)
                        if usage:
                            total_calls += int(usage)
                            active_users += 1

                    today_stats = f"活跃用户: {active_users}, 总调用: {total_calls}"
                except:
                    today_stats = "获取失败"

            # 构建状态报告
            status_msg = (
                "🔍 插件状态监控报告\n\n"
                f"📊 Redis连接状态: {redis_status}\n"
                f"🔌 Redis可用性: {redis_available_status}\n\n"
                f"⚙️ 配置信息:\n"
                f"• 默认限制: {default_limit} 次/天\n"
                f"• 豁免用户数: {exempt_users_count} 个\n"
                f"• 群组限制数: {group_limits_count} 个\n"
                f"• 用户限制数: {user_limits_count} 个\n\n"
                f"📈 今日统计: {today_stats}\n\n"
                f"💡 健康状态: {'✅ 健康' if self.redis and redis_available else '⚠️ 需要检查'}"
            )

            await event.send(MessageChain().message(status_msg))

        except Exception as e:
            self._log_error("检查插件状态失败: {}", str(e))
            await event.send(MessageChain().message("❌ 检查插件状态失败"))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("domain")
    async def limit_domain(self, event: AstrMessageEvent):
        """查看配置的域名和访问地址（仅管理员）"""
        try:
            # 获取域名配置
            web_config = self.config.get("web_server", {})
            domain = web_config.get("domain", "")
            host = web_config.get("host", "127.0.0.1")
            port = web_config.get("port", 10245)

            domain_msg = "🌐 域名配置信息\n"
            domain_msg += "═════════════\n"

            if domain:
                domain_msg += f"✅ 已配置自定义域名: {domain}\n"
                # 获取Web服务器的访问地址
                if self.web_server:
                    access_url = self.web_server.get_access_url()
                    domain_msg += f"🔗 访问地址: {access_url}\n"
                else:
                    domain_msg += f"🔗 访问地址: https://{domain}\n"
            else:
                domain_msg += "❌ 未配置自定义域名\n"
                domain_msg += f"🔗 当前访问地址: http://{host}:{port}\n"

            domain_msg += "\n💡 配置说明:\n"
            domain_msg += (
                "• 在配置文件的 web_server 部分添加 domain 字段来设置自定义域名\n"
            )
            domain_msg += '• 例如: "domain": "example.com"\n'
            domain_msg += "• 配置域名后，Web管理界面将使用该域名生成访问链接\n"

            await event.send(MessageChain().message(domain_msg))

        except Exception as e:
            self._log_error("获取域名配置失败: {}", str(e))
            await event.send(
                MessageChain().message("❌ 获取域名配置失败，请检查配置文件")
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("top")
    async def limit_top(self, event: AstrMessageEvent, count: int = 10):
        """显示使用次数排行榜"""
        if not self.redis:
            await event.send(MessageChain().message("❌ Redis未连接，无法获取排行榜"))
            return

        # 验证参数
        if count < 1 or count > 20:
            await event.send(MessageChain().message("❌ 排行榜数量应在1-20之间"))
            return

        try:
            # 获取今日的键模式 - 同时获取个人和群组键
            pattern = f"{self._get_today_key()}:*"

            keys = self.redis.keys(pattern)

            if not keys:
                await event.send(MessageChain().message("📊 今日暂无使用记录"))
                return

            # 获取所有键对应的使用次数，区分个人和群组
            user_usage_data = []
            group_usage_data = []

            for key in keys:
                usage = self.redis.get(key)
                if usage:
                    # 从键名中提取信息
                    parts = key.split(":")
                    if len(parts) >= 5:
                        # 判断是个人键还是群组键
                        if parts[-2] == "group":
                            # 群组键格式: astrbot:daily_limit:2025-01-23:group:群组ID
                            group_id = parts[-1]
                            group_usage_data.append(
                                {
                                    "group_id": group_id,
                                    "usage": int(usage),
                                    "type": "group",
                                }
                            )
                        else:
                            # 个人键格式: astrbot:daily_limit:2025-01-23:群组ID:用户ID
                            group_id = parts[-2]
                            user_id = parts[-1]
                            user_usage_data.append(
                                {
                                    "user_id": user_id,
                                    "group_id": group_id,
                                    "usage": int(usage),
                                    "type": "user",
                                }
                            )

            # 合并数据并按使用次数排序
            all_usage_data = user_usage_data + group_usage_data
            all_usage_data.sort(key=lambda x: x["usage"], reverse=True)

            # 取前count名
            top_entries = all_usage_data[:count]

            if not top_entries:
                await event.send(MessageChain().message("📊 今日暂无使用记录"))
                return

            # 构建排行榜消息
            leaderboard_msg = f"🏆 今日使用次数排行榜（前{len(top_entries)}名）\n\n"

            for i, entry_data in enumerate(top_entries, 1):
                if entry_data["type"] == "group":
                    # 群组条目
                    group_id = entry_data["group_id"]
                    usage = entry_data["usage"]

                    # 获取群组限制
                    limit = self._get_user_limit(
                        "dummy_user", group_id
                    )  # 使用虚拟用户ID获取群组限制

                    if limit == float("inf"):
                        limit_text = "无限制"
                    else:
                        limit_text = f"{limit}次"

                    leaderboard_msg += (
                        f"{i}. 群组 {group_id} - {usage}次 (限制: {limit_text})\n"
                    )
                else:
                    # 个人条目
                    user_id = entry_data["user_id"]
                    usage = entry_data["usage"]
                    group_id = entry_data["group_id"]

                    # 获取用户限制
                    limit = self._get_user_limit(user_id, group_id)

                    if limit == float("inf"):
                        limit_text = "无限制"
                    else:
                        limit_text = f"{limit}次"

                    leaderboard_msg += (
                        f"{i}. 用户 {user_id} - {usage}次 (限制: {limit_text})\n"
                    )

            await event.send(MessageChain().message(leaderboard_msg))

        except Exception as e:
            self._log_error("获取排行榜失败: {}", str(e))
            await event.send(MessageChain().message("❌ 获取排行榜失败，请稍后重试"))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("reset")
    async def limit_reset(self, event: AstrMessageEvent, user_id: str = None):
        """重置使用次数（仅管理员）"""
        if not self.redis:
            event.set_result(
                MessageEventResult().message("Redis未连接，无法重置使用次数")
            )
            return

        try:
            if user_id is None:
                # 显示重置帮助信息
                help_msg = (
                    "🔄 重置使用次数命令用法：\n"
                    "• /limit reset all - 重置所有使用记录（包括个人和群组）\n"
                    "• /limit reset <用户ID> - 重置特定用户的使用次数\n"
                    "• /limit reset group <群组ID> - 重置特定群组的使用次数\n"
                    "示例：\n"
                    "• /limit reset all - 重置所有使用记录\n"
                    "• /limit reset 123456 - 重置用户123456的使用次数\n"
                    "• /limit reset group 789012 - 重置群组789012的使用次数"
                )
                event.set_result(MessageEventResult().message(help_msg))
                return

            # 将user_id转换为字符串，防止整数类型导致lower()方法失败
            user_id_str = str(user_id)

            if user_id_str.lower() == "all":
                # 重置所有使用记录
                today_key = self._get_today_key()
                pattern = f"{today_key}:*"

                keys = self.redis.keys(pattern)

                if not keys:
                    event.set_result(
                        MessageEventResult().message("✅ 当前没有使用记录需要重置")
                    )
                    return

                deleted_count = 0
                for key in keys:
                    self.redis.delete(key)
                    deleted_count += 1

                event.set_result(
                    MessageEventResult().message(
                        f"✅ 已重置所有使用记录，共清理 {deleted_count} 条记录"
                    )
                )

            elif user_id_str.lower().startswith("group "):
                # 重置特定群组
                group_id = user_id_str[6:].strip()  # 移除"group "前缀

                # 验证群组ID格式
                if not group_id.isdigit():
                    event.set_result(
                        MessageEventResult().message("❌ 群组ID格式错误，请输入数字ID")
                    )
                    return

                # 查找并删除该群组的所有使用记录
                today_key = self._get_today_key()

                # 删除群组共享记录
                group_key = self._get_group_key(group_id)
                group_deleted = 0
                if self.redis.exists(group_key):
                    self.redis.delete(group_key)
                    group_deleted += 1

                # 删除该群组下所有用户的个人记录
                pattern = f"{today_key}:{group_id}:*"
                user_keys = self.redis.keys(pattern)
                user_deleted = 0
                for key in user_keys:
                    self.redis.delete(key)
                    user_deleted += 1

                total_deleted = group_deleted + user_deleted

                if total_deleted == 0:
                    event.set_result(
                        MessageEventResult().message(
                            f"❌ 未找到群组 {group_id} 的使用记录"
                        )
                    )
                else:
                    event.set_result(
                        MessageEventResult().message(
                            f"✅ 已重置群组 {group_id} 的使用次数，共清理 {total_deleted} 条记录（群组: {group_deleted}, 用户: {user_deleted}）"
                        )
                    )

            else:
                # 重置特定用户
                # 验证用户ID格式
                if not user_id_str.isdigit():
                    event.set_result(
                        MessageEventResult().message("❌ 用户ID格式错误，请输入数字ID")
                    )
                    return

                # 查找并删除该用户的所有使用记录
                today_key = self._get_today_key()
                pattern = f"{today_key}:*:{user_id_str}"

                keys = self.redis.keys(pattern)

                if not keys:
                    event.set_result(
                        MessageEventResult().message(
                            f"❌ 未找到用户 {user_id_str} 的使用记录"
                        )
                    )
                    return

                deleted_count = 0
                for key in keys:
                    self.redis.delete(key)
                    deleted_count += 1

                event.set_result(
                    MessageEventResult().message(
                        f"✅ 已重置用户 {user_id_str} 的使用次数，共清理 {deleted_count} 条记录"
                    )
                )

        except Exception as e:
            self._log_error("重置使用次数失败: {}", str(e))
            event.set_result(
                MessageEventResult().message("重置使用次数失败，请检查Redis连接")
            )

    async def terminate(self):
        """
        插件终止时的清理工作

        停止Web服务器并清理所有相关资源，确保状态正确清理。
        """
        # 停止Web服务器
        if self.web_server:
            try:
                self._log_info("正在停止Web服务器...")
                success = self.web_server.stop()

                if success:
                    self._log_info("Web服务器已停止")
                else:
                    self._log_warning("Web服务器停止失败")

            except Exception as e:
                self._log_error("停止Web服务器失败: {}", str(e))

        # 清理Web服务器线程
        if self.web_server_thread and self.web_server_thread.is_alive():
            try:
                self.web_server_thread.join(timeout=3)
                if self.web_server_thread.is_alive():
                    self._log_warning("Web服务器线程未在3秒内结束")
            except Exception as e:
                self._log_error("等待Web服务器线程结束时出错: {}", str(e))

        # 清理Web服务器实例和线程引用
        self.web_server = None
        self.web_server_thread = None

        # 停止版本检查任务
        if self.version_check_task and not self.version_check_task.done():
            self.version_check_task.cancel()
            try:
                await self.version_check_task
            except asyncio.CancelledError:
                pass
            self._log_info("版本检查任务已停止")

        self._log_info("日调用限制插件已终止")

    def _terminate_web_server(self):
        """
        专门用于停止Web服务器的方法（代理方法）

        返回：
            bool: 停止成功返回True，失败返回False
        """
        return self.web_manager.terminate_web_server()

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("timeperiod list")
    async def limit_timeperiod_list(self, event: AstrMessageEvent):
        """列出所有时间段限制配置（仅管理员）"""
        if not self.time_period_limits:
            event.set_result(MessageEventResult().message("当前没有设置任何时间段限制"))
            return

        timeperiod_msg = "⏰ 时间段限制配置列表：\n"
        for i, period in enumerate(self.time_period_limits, 1):
            status = "✅ 启用" if period["enabled"] else "❌ 禁用"
            timeperiod_msg += f"{i}. {period['start_time']} - {period['end_time']}: {period['limit']} 次 ({status})\n"

        event.set_result(MessageEventResult().message(timeperiod_msg))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("timeperiod add")
    async def limit_timeperiod_add(
        self,
        event: AstrMessageEvent,
        start_time: str = None,
        end_time: str = None,
        limit: int = None,
    ):
        """添加时间段限制（仅管理员）"""
        if not all([start_time, end_time, limit]):
            event.set_result(
                MessageEventResult().message(
                    "用法: /limit timeperiod add <开始时间> <结束时间> <限制次数>"
                )
            )
            return

        try:
            # 验证时间格式
            datetime.datetime.strptime(start_time, "%H:%M")
            datetime.datetime.strptime(end_time, "%H:%M")

            # 验证限制次数
            limit = int(limit)
            if limit < 1:
                event.set_result(MessageEventResult().message("限制次数必须大于0"))
                return

            # 添加时间段限制
            new_period = {
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
                "enabled": True,
            }

            self.time_period_limits.append(new_period)
            self._save_time_period_limits()

            event.set_result(
                MessageEventResult().message(
                    f"✅ 已添加时间段限制: {start_time} - {end_time}: {limit} 次"
                )
            )

        except ValueError as e:
            if "does not match format" in str(e):
                event.set_result(
                    MessageEventResult().message(
                        "时间格式错误，请使用 HH:MM 格式（如 09:00）"
                    )
                )
            else:
                event.set_result(MessageEventResult().message("限制次数必须为整数"))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("timeperiod remove")
    async def limit_timeperiod_remove(self, event: AstrMessageEvent, index: int = None):
        """删除时间段限制（仅管理员）"""
        if index is None:
            event.set_result(
                MessageEventResult().message("用法: /limit timeperiod remove <索引>")
            )
            return

        try:
            index = int(index) - 1  # 转换为0-based索引

            if index < 0 or index >= len(self.time_period_limits):
                event.set_result(
                    MessageEventResult().message(
                        f"索引无效，请使用 1-{len(self.time_period_limits)} 之间的数字"
                    )
                )
                return

            removed_period = self.time_period_limits.pop(index)
            self._save_time_period_limits()

            event.set_result(
                MessageEventResult().message(
                    f"✅ 已删除时间段限制: {removed_period['start_time']} - {removed_period['end_time']}"
                )
            )

        except ValueError:
            event.set_result(MessageEventResult().message("索引必须为整数"))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("timeperiod enable")
    async def limit_timeperiod_enable(self, event: AstrMessageEvent, index: int = None):
        """启用时间段限制（仅管理员）"""
        if index is None:
            event.set_result(
                MessageEventResult().message("用法: /limit timeperiod enable <索引>")
            )
            return

        try:
            index = int(index) - 1  # 转换为0-based索引

            if index < 0 or index >= len(self.time_period_limits):
                event.set_result(
                    MessageEventResult().message(
                        f"索引无效，请使用 1-{len(self.time_period_limits)} 之间的数字"
                    )
                )
                return

            self.time_period_limits[index]["enabled"] = True
            self._save_time_period_limits()

            period = self.time_period_limits[index]
            event.set_result(
                MessageEventResult().message(
                    f"✅ 已启用时间段限制: {period['start_time']} - {period['end_time']}"
                )
            )

        except ValueError:
            event.set_result(MessageEventResult().message("索引必须为整数"))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("timeperiod disable")
    async def limit_timeperiod_disable(
        self, event: AstrMessageEvent, index: int = None
    ):
        """禁用时间段限制（仅管理员）"""
        if index is None:
            event.set_result(
                MessageEventResult().message("用法: /limit timeperiod disable <索引>")
            )
            return

        try:
            index = int(index) - 1  # 转换为0-based索引

            if index < 0 or index >= len(self.time_period_limits):
                event.set_result(
                    MessageEventResult().message(
                        f"索引无效，请使用 1-{len(self.time_period_limits)} 之间的数字"
                    )
                )
                return

            self.time_period_limits[index]["enabled"] = False
            self._save_time_period_limits()

            period = self.time_period_limits[index]
            event.set_result(
                MessageEventResult().message(
                    f"✅ 已禁用时间段限制: {period['start_time']} - {period['end_time']}"
                )
            )

        except ValueError:
            event.set_result(MessageEventResult().message("索引必须为整数"))

    def _save_time_period_limits(self):
        """保存时间段限制配置到配置文件（新格式：开始时间-结束时间:限制次数:是否启用）"""
        try:
            # 构建新的文本格式配置
            lines = []
            for period in self.time_period_limits:
                line = f"{period['start_time']}-{period['end_time']}:{period['limit']}:{str(period['enabled']).lower()}"
                lines.append(line)

            # 更新配置对象
            self.config["limits"]["time_period_limits"] = "\n".join(lines)
            # 保存到配置文件
            self.config.save_config()
            self._log_info(
                "已保存时间段限制配置，共 {} 个时间段", len(self.time_period_limits)
            )
        except Exception as e:
            self._log_error("保存时间段限制配置失败: {}", str(e))

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("checkupdate")
    async def limit_checkupdate(self, event: AstrMessageEvent):
        """手动检查版本更新（仅管理员）"""
        try:
            # 检查版本检查功能是否启用
            if not self.config["version_check"].get("enabled", True):
                event.set_result(
                    MessageEventResult().message(
                        "❌ 版本检查功能已禁用，请在配置中启用"
                    )
                )
                return

            # 发送检查开始消息
            event.set_result(MessageEventResult().message("🔍 正在检查版本更新..."))

            # 执行版本检查
            await self.version_checker.check_version_update()

            # 检查是否有新版本
            current_version = self.config.get("version", "v2.8.7")
            if self.version_checker.last_checked_version:
                if (
                    self.version_checker._compare_versions(self.version_checker.last_checked_version, current_version)
                    > 0
                ):
                    # 有新版本
                    update_content = (
                        self.version_checker.last_checked_version_info.get("content", "暂无更新说明")
                        if hasattr(self.version_checker, "last_checked_version_info")
                        else "暂无更新说明"
                    )
                    event.set_result(
                        MessageEventResult().message(
                            f"AstrBot-每日限制插件 DailyLimit\n\n🎉 检测到新版本可用！\n"
                            f"📦 当前版本：{current_version}\n"
                            f"🆕 最新版本：{self.version_checker.last_checked_version}\n"
                            f"📝 更新内容：{update_content}\n"
                            f"🔗 下载地址：https://github.com/left666/astrbot_plugin_daily_limit"
                            f"\nCiallo～(∠・ω< )⌒★"
                        )
                    )
                else:
                    # 已是最新版本
                    event.set_result(
                        MessageEventResult().message(
                            f"✅ 当前已是最新版本：{current_version}\n"
                            f"📅 最后检查时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                    )
            else:
                # 检查失败
                event.set_result(
                    MessageEventResult().message("❌ 版本检查失败，请稍后重试")
                )

        except Exception as e:
            self._handle_error(e, "手动检查版本更新")
            event.set_result(
                MessageEventResult().message("❌ 版本检查过程中出现错误，请稍后重试")
            )

    @filter.permission_type(PermissionType.ADMIN)
    @limit_command_group.command("version")
    async def limit_version(self, event: AstrMessageEvent):
        """查看当前插件版本信息（仅管理员）"""
        try:
            current_version = self.config.get("version", "v2.8.7")

            # 构建版本信息消息
            version_msg = "📦 日调用限制插件版本信息\n"
            version_msg += "══════════════\n\n"
            version_msg += f"• 当前版本：{current_version}\n"
            version_msg += "• 作者：left666\n"
            version_msg += "• 改进：Sakura520222\n\n"

            # 添加版本检查状态
            if not self.config["version_check"].get("enabled", True):
                version_msg += "🔴 版本检查功能：已禁用\n"
            else:
                check_interval = self.config["version_check"].get("check_interval", 60)
                version_msg += (
                    f"🟢 版本检查功能：已启用（每 {check_interval} 分钟检查一次）\n"
                )

                if self.last_checked_version:
                    if (
                        self._compare_versions(
                            self.last_checked_version, current_version
                        )
                        > 0
                    ):
                        version_msg += f"🆕 检测到新版本：{self.last_checked_version}\n"
                    else:
                        version_msg += "✅ 当前已是最新版本\n"
                else:
                    version_msg += "⏳ 尚未进行版本检查\n"

            version_msg += "\n💡 使用 /limit checkupdate 手动检查更新"

            event.set_result(MessageEventResult().message(version_msg))

        except Exception as e:
            self._handle_error(e, "查看版本信息")
            event.set_result(MessageEventResult().message("❌ 获取版本信息失败"))

    # ASCII艺术字
    ASCII_ART = """
 ██████████     █████████   █████ █████       █████ █████    █████       █████ ██████   ██████ █████ ███████████
░░███░░░░███   ███░░░░░███ ░░███ ░░███       ░░███ ░░███    ░░███       ░░███ ░░██████ ██████ ░░███ ░█░░░███░░░█
 ░███   ░░███ ░███    ░███  ░███  ░███        ░░███ ███      ░███        ░███  ░███░█████░███  ░███ ░   ░███  ░ 
 ░███    ░███ ░███████████  ░███  ░███         ░░█████       ░███        ░███  ░███░░███ ░███  ░███     ░███    
 ░███    ░███ ░███░░░░░███  ░███  ░███          ░░███        ░███        ░███  ░███ ░░░  ░███  ░███     ░███    
 ░███    ███  ░███    ░███  ░███  ░███      █    ░███        ░███      █ ░███  ░███      ░███  ░███     ░███    
 ██████████   █████   █████ █████ ███████████    █████       ███████████ █████ █████     █████ █████    █████   
░░░░░░░░░░   ░░░░░   ░░░░░ ░░░░░ ░░░░░░░░░░░    ░░░░░       ░░░░░░░░░░░ ░░░░░ ░░░░░     ░░░░░ ░░░░░    ░░░░░    
                                                                                                                
                                                                                                                                                                                                      
                                       每日调用限制插件 v2.8.7                       
                                  作者: left666 & Sakura520222                  
    """

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        """AstrBot初始化完成时触发"""
        self._log_info("{}", self.ASCII_ART)
