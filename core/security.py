"""
安全/滥用检测模块

负责检测和处理用户滥用行为，包括：
- 快速请求检测
- 连续请求检测
- 用户限制管理
- 异常行为记录
"""

import time


class Security:
    """安全/滥用检测类"""

    def __init__(self, plugin):
        """
        初始化安全模块

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.config_mgr = plugin.config_mgr

        # 安全配置（从 config_mgr 获取）
        self.anti_abuse_enabled = False
        self.rapid_request_threshold = 10
        self.rapid_request_window = 10
        self.consecutive_request_threshold = 5
        self.consecutive_request_window = 30
        self.auto_block_duration = 3600  # 默认1小时

        # 异常行为记录
        self.abuse_records = {}  # {"user_id": [timestamp1, timestamp2, ...]}
        self.blocked_users = {}  # {"user_id": {"block_until": timestamp, "reason": str}}
        self.abuse_stats = {}  # {"user_id": {"last_request_time": timestamp, "consecutive_count": int, "rapid_count": int}}

        # 通知相关
        self.notified_users = {}  # {"user_id": timestamp}
        self.notified_admins = {}  # {"admin_id": timestamp}

    def load_security_config(self):
        """从配置管理器加载安全配置"""
        if self.config_mgr:
            self.anti_abuse_enabled = self.config_mgr.anti_abuse_enabled
            self.rapid_request_threshold = self.config_mgr.rapid_request_threshold
            self.rapid_request_window = self.config_mgr.rapid_request_window
            self.consecutive_request_threshold = self.config_mgr.consecutive_request_threshold
            self.consecutive_request_window = self.config_mgr.consecutive_request_window
        else:
            # 默认值
            self.anti_abuse_enabled = False
            self.rapid_request_threshold = 10
            self.rapid_request_window = 10
            self.consecutive_request_threshold = 5
            self.consecutive_request_window = 30

    def detect_abuse_behavior(self, user_id, timestamp=None):
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
        if not self.anti_abuse_enabled:
            return {"is_abuse": False, "reason": "防刷机制未启用"}

        try:
            return self._execute_abuse_detection_pipeline(user_id, timestamp)
        except Exception as e:
            self.logger.log_error("检测异常使用行为失败: {}", str(e))
            return {"is_abuse": False, "reason": "检测失败"}

    def _execute_abuse_detection_pipeline(self, user_id, timestamp):
        """执行异常检测流水线"""
        user_id = str(user_id)
        current_time = timestamp or time.time()

        try:
            # 执行异常检测流程
            return self._run_abuse_detection_flow(user_id, current_time)
        except Exception as e:
            self.logger.log_error("异常检测流水线执行失败 - 用户 {}: {}", user_id, str(e))
            return {"is_abuse": False, "reason": "检测过程异常，允许使用"}

    def _run_abuse_detection_flow(self, user_id, current_time):
        """执行异常检测流程"""
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
        """执行异常检测规则"""
        try:
            # 检测快速请求异常
            rapid_request_result = self._detect_rapid_requests(user_id, current_time)
            if rapid_request_result["is_abuse"]:
                return rapid_request_result

            # 检测连续请求异常
            consecutive_request_result = self._detect_consecutive_requests(user_id, current_time)
            if consecutive_request_result["is_abuse"]:
                return consecutive_request_result

            return {"is_abuse": False, "reason": "所有检测规则通过"}
        except Exception as e:
            self.logger.log_error("异常检测规则执行失败 - 用户 {}: {}", user_id, str(e))
            return {"is_abuse": False, "reason": "规则检测异常，允许使用"}

    def _cleanup_expired_notifications(self, current_time):
        """清理过期通知记录（保留最近24小时的数据）"""
        try:
            notification_cutoff_time = current_time - 86400  # 24小时
            self.notified_users = {
                uid: t for uid, t in self.notified_users.items() if t > notification_cutoff_time
            }
            self.notified_admins = {
                uid: t for uid, t in self.notified_admins.items() if t > notification_cutoff_time
            }
        except Exception as e:
            self.logger.log_error("清理过期通知记录失败: {}", str(e))

    def _check_user_block_status(self, user_id, current_time):
        """检查用户是否已被限制"""
        try:
            if user_id in self.blocked_users:
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
            self.logger.log_error("检查用户限制状态失败 - 用户 {}: {}", user_id, str(e))
            return {"is_abuse": False, "reason": "限制状态检查异常，允许使用"}

    def _cleanup_expired_block(self, user_id):
        """清理过期的用户限制记录"""
        if user_id in self.blocked_users:
            del self.blocked_users[user_id]
        if user_id in self.abuse_records:
            del self.abuse_records[user_id]
        if user_id in self.abuse_stats:
            del self.abuse_stats[user_id]

    def _init_user_records(self, user_id):
        """初始化用户记录"""
        try:
            if user_id not in self.abuse_records:
                self.abuse_records[user_id] = []
            if user_id not in self.abuse_stats:
                self.abuse_stats[user_id] = {
                    "last_request_time": 0,
                    "consecutive_count": 0,
                    "rapid_count": 0,
                }
        except Exception as e:
            self.logger.log_error("初始化用户记录失败 - 用户 {}: {}", user_id, str(e))

    def _record_user_request(self, user_id, current_time):
        """记录用户请求并清理过期记录"""
        try:
            # 确保记录字典存在
            if user_id not in self.abuse_records:
                self._init_user_records(user_id)

            # 记录当前请求
            self.abuse_records[user_id].append(current_time)

            # 清理过期记录（保留最近1小时的数据）
            cutoff_time = current_time - 3600
            self.abuse_records[user_id] = [
                t for t in self.abuse_records[user_id] if t > cutoff_time
            ]
        except Exception as e:
            self.logger.log_error("记录用户请求失败 - 用户 {}: {}", user_id, str(e))

    def _detect_rapid_requests(self, user_id, current_time):
        """检测快速请求异常"""
        recent_requests = [
            t for t in self.abuse_records[user_id]
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

    async def block_user_for_abuse(self, user_id, reason, duration=None):
        """限制用户使用

        参数:
            user_id: 用户ID
            reason: 限制原因
            duration: 限制时长（秒），默认使用配置值

        返回:
            dict: 包含限制信息的字典
        """
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

            self.logger.log_warning(
                "用户 {} 因 {} 被限制使用 {} 秒", user_id, reason, block_duration
            )

            return block_info
        except Exception as e:
            self.logger.log_error("限制用户失败: {}", str(e))
            return None

    def is_user_blocked(self, user_id):
        """检查用户是否被限制"""
        current_time = time.time()
        if user_id in self.blocked_users:
            block_info = self.blocked_users[user_id]
            if current_time < block_info["block_until"]:
                return True
            else:
                # 限制已过期，移除记录
                self._cleanup_expired_block(user_id)
        return False
