"""
配置管理模块

负责加载、解析和验证插件配置，包括：
- 群组和用户限制配置
- 群组模式配置
- 时间段限制配置
- 忽略模式配置
- 安全配置
"""

import datetime


class ConfigManager:
    """配置管理类"""

    def __init__(self, plugin):
        """
        初始化配置管理器

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.config = plugin.config

        # 配置数据存储
        self.group_limits = {}  # 群组特定限制 {"group_id": limit_count}
        self.user_limits = {}  # 用户特定限制 {"user_id": limit_count}
        self.group_modes = {}  # 群组模式配置 {"group_id": "shared"或"individual"}
        self.time_period_limits = []  # 时间段限制配置
        self.skip_patterns = []  # 忽略处理的模式列表

        # 安全配置
        self.anti_abuse_enabled = False
        self.rapid_request_threshold = 10
        self.rapid_request_window = 10
        self.consecutive_request_threshold = 5
        self.consecutive_request_window = 30

    def load_limits_from_config(self):
        """
        从配置文件加载群组和用户特定限制

        从插件的配置文件中加载所有限制相关设置，包括：
        - 群组限制配置
        - 用户限制配置
        - 群组模式配置
        - 时间段限制配置
        - 忽略模式配置
        - 每日重置时间验证
        """
        self._parse_group_limits()
        self._parse_user_limits()
        self._parse_group_modes()
        self._parse_time_period_limits()
        self._load_skip_patterns()
        self._validate_daily_reset_time()

        self.logger.log_info(
            "已加载 {} 个群组限制、{} 个用户限制、{} 个群组模式配置、{} 个时间段限制和{} 个忽略模式",
            len(self.group_limits),
            len(self.user_limits),
            len(self.group_modes),
            len(self.time_period_limits),
            len(self.skip_patterns),
        )

        # 加载安全配置
        self._load_security_config()

    def _parse_limits_config(
        self, config_key: str, limits_dict: dict, limit_type: str
    ) -> None:
        """
        通用限制配置解析方法

        Args:
            config_key: 配置键名
            limits_dict: 目标限制字典
            limit_type: 限制类型描述
        """
        config_value = self.config["limits"].get(config_key, "")

        # 处理配置值，兼容字符串和列表两种格式
        if isinstance(config_value, str):
            # 如果是字符串，按换行符分割并过滤空值
            lines = [
                line.strip()
                for line in config_value.strip().split("\n")
                if line.strip()
            ]
        elif isinstance(config_value, list):
            # 如果是列表，确保所有元素都是字符串并过滤空值
            lines = [str(line).strip() for line in config_value if str(line).strip()]
        else:
            # 其他类型，转换为字符串处理
            lines = [str(config_value).strip()]

        for line in lines:
            self._parse_limit_line(line, limits_dict, limit_type)

    def _parse_group_limits(self):
        """解析群组特定限制配置"""
        self._parse_limits_config("group_limits", self.group_limits, "群组")

    def _parse_user_limits(self):
        """解析用户特定限制配置"""
        self._parse_limits_config("user_limits", self.user_limits, "用户")

    def _parse_config_lines(self, config_text, parser_func):
        """通用配置行解析器"""
        if not config_text:
            return

        # 处理配置文本，兼容字符串和列表两种格式
        if isinstance(config_text, str):
            # 如果是字符串，按换行符分割并过滤空值
            lines = [
                line.strip() for line in config_text.strip().split("\n") if line.strip()
            ]
        elif isinstance(config_text, list):
            # 如果是列表，确保所有元素都是字符串并过滤空值
            lines = [str(line).strip() for line in config_text if str(line).strip()]
        else:
            # 其他类型，转换为字符串处理
            lines = [str(config_text).strip()]

        for line in lines:
            parser_func(line)

    def _validate_config_structure(self) -> bool:
        """
        验证配置结构完整性

        Returns:
            bool: 配置结构是否完整
        """
        required_sections = ["limits", "redis"]
        required_limits_fields = [
            "default_daily_limit",
            "exempt_users",
            "group_limits",
            "user_limits",
        ]

        try:
            # 检查必需配置段
            for section in required_sections:
                if section not in self.config:
                    self.logger.log_error("配置缺少必需段: {}", section)
                    return False

            # 检查limits段必需字段
            for field in required_limits_fields:
                if field not in self.config["limits"]:
                    self.logger.log_error("limits配置缺少必需字段: {}", field)
                    return False

            return True
        except Exception as e:
            self.logger.handle_error(e, "配置结构验证")
            return False

    def _safe_parse_int(self, value_str, default=None):
        """安全解析整数，避免重复的异常处理"""
        try:
            return int(value_str)
        except (ValueError, TypeError):
            return default

    def _validate_config_line(self, line, required_separator=":", min_parts=2):
        """验证配置行格式"""
        line = line.strip()
        if not line or required_separator not in line:
            return None

        parts = line.split(required_separator, min_parts - 1)
        if len(parts) < min_parts:
            return None

        return parts

    def _parse_limit_line(self, line, limits_dict, limit_type):
        """解析单行限制配置"""
        parts = self._validate_config_line(line)
        if not parts:
            return

        entity_id = parts[0].strip()
        limit_str = parts[1].strip()

        limit = self._safe_parse_int(limit_str)
        if entity_id and limit is not None:
            limits_dict[entity_id] = limit
        else:
            self.logger.log_warning("{}限制配置格式错误: {}", limit_type, line)

    def _parse_group_modes(self):
        """解析群组模式配置"""
        group_mode_text = self.config["limits"].get("group_mode_settings", "")
        self._parse_config_lines(group_mode_text, self._parse_group_mode_line)

    def _parse_group_mode_line(self, line):
        """解析单行群组模式配置"""
        parts = self._validate_config_line(line)
        if not parts:
            return

        group_id = parts[0].strip()
        mode = parts[1].strip()

        if group_id and mode in ["shared", "individual"]:
            self.group_modes[group_id] = mode
        else:
            self.logger.log_warning("群组模式配置格式错误: {}", line)

    def _parse_time_period_limits(self):
        """解析时间段限制配置"""
        time_period_value = self.config["limits"].get("time_period_limits", "")

        # 处理配置值，兼容字符串和列表两种格式
        if isinstance(time_period_value, str):
            # 如果是字符串，按换行符分割并过滤空值
            lines = [
                line.strip()
                for line in time_period_value.strip().split("\n")
                if line.strip()
            ]
        elif isinstance(time_period_value, list):
            # 如果是列表，确保所有元素都是字符串并过滤空值
            lines = [
                str(line).strip() for line in time_period_value if str(line).strip()
            ]
        else:
            # 其他类型，转换为字符串处理
            lines = [str(time_period_value).strip()]

        for line in lines:
            self._parse_time_period_line(line)

    def _parse_time_period_line(self, line):
        """解析单行时间段限制配置"""
        # 解析时间范围部分
        time_range_data = self._parse_time_range_from_line(line)
        if not time_range_data:
            return

        # 解析限制次数
        limit_data = self._parse_limit_from_line(line)
        if not limit_data:
            return

        # 解析启用标志
        enabled = self._parse_enabled_flag_from_line(line)

        # 如果启用，则添加到限制列表
        if enabled:
            self.time_period_limits.append(
                {
                    "start_time": time_range_data["start_time"],
                    "end_time": time_range_data["end_time"],
                    "limit": limit_data,
                }
            )

    def _parse_time_range_from_line(self, line):
        """从配置行中解析时间范围"""
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
        if not self._validate_time_format(start_time) or not self._validate_time_format(
            end_time
        ):
            self.logger.log_warning("时间段限制时间格式错误: {}", line)
            return None

        return {"start_time": start_time, "end_time": end_time}

    def _parse_limit_from_line(self, line):
        """从配置行中解析限制次数"""
        parts = self._validate_config_line(line, ":", 2)
        if not parts:
            return None

        limit = self._safe_parse_int(parts[1].strip())
        if limit is not None:
            return limit
        else:
            self.logger.log_warning("时间段限制次数格式错误: {}", line)
            return None

    def _parse_enabled_flag_from_line(self, line):
        """从配置行中解析启用标志"""
        line = line.strip()
        parts = line.split(":", 2)

        if len(parts) >= 3:
            return self._parse_enabled_flag(parts[2])
        return True

    def _validate_time_format(self, time_str):
        """验证时间格式"""
        try:
            datetime.datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    def _parse_enabled_flag(self, enabled_str):
        """解析启用标志"""
        if enabled_str is None:
            return True

        enabled_str = enabled_str.strip().lower()
        return enabled_str in ["true", "1", "yes", "y"]

    def _load_skip_patterns(self):
        """加载忽略模式配置"""
        self.skip_patterns = self.config["limits"].get("skip_patterns", ["#", "*"])

    def _load_security_config(self):
        """加载安全配置"""
        try:
            security_config = self.config.get("security", {})

            # 加载基础配置
            self._load_basic_security_config(security_config)

            # 加载检测阈值配置
            self._load_detection_thresholds(security_config)

            # 加载自动限制配置
            self._load_auto_block_config(security_config)

            # 加载通知配置
            self._load_notification_config(security_config)

            # 初始化通知记录
            self._init_notification_records()

            self.logger.log_info(
                "安全配置加载完成，防刷机制{}",
                "已启用" if self.anti_abuse_enabled else "未启用",
            )

        except Exception as e:
            self.logger.log_error("加载安全配置失败: {}", str(e))
            # 使用默认值
            self._set_default_security_config()

    def _load_basic_security_config(self, security_config):
        """加载基础安全配置"""
        self.anti_abuse_enabled = security_config.get("anti_abuse_enabled", False)

    def _load_detection_thresholds(self, security_config):
        """加载检测阈值配置"""
        self.rapid_request_threshold = security_config.get(
            "rapid_request_threshold", 10
        )  # 10秒内请求次数
        self.rapid_request_window = security_config.get(
            "rapid_request_window", 10
        )  # 时间窗口（秒）
        self.consecutive_request_threshold = security_config.get(
            "consecutive_request_threshold", 5
        )  # 连续请求次数
        self.consecutive_request_window = security_config.get(
            "consecutive_request_window", 30
        )  # 时间窗口（秒）

    def _load_auto_block_config(self, security_config):
        """加载自动限制配置"""
        # 自动限制相关配置可以在这里添加
        pass

    def _load_notification_config(self, security_config):
        """加载通知配置"""
        # 通知相关配置可以在这里添加
        pass

    def _init_notification_records(self):
        """初始化通知记录"""
        # 通知记录初始化可以在这里添加
        pass

    def _set_default_security_config(self):
        """设置默认安全配置"""
        self.anti_abuse_enabled = False
        self.rapid_request_threshold = 10
        self.rapid_request_window = 10
        self.consecutive_request_threshold = 5
        self.consecutive_request_window = 30

    def _validate_daily_reset_time(self):
        """验证每日重置时间配置"""
        reset_time_str = self.config["limits"].get("daily_reset_time", "00:00")

        # 验证重置时间格式
        try:
            reset_hour, reset_minute = map(int, reset_time_str.split(":"))
            if not (0 <= reset_hour <= 23 and 0 <= reset_minute <= 59):
                raise ValueError("重置时间格式错误")
            self.logger.log_info("重置时间配置验证通过: {}", reset_time_str)
        except (ValueError, AttributeError) as e:
            # 如果配置格式错误，记录警告并使用默认值
            self.logger.log_warning(
                "重置时间配置格式错误: {}，错误: {}，使用默认值00:00", reset_time_str, e
            )
            # 自动修复为默认值
            self.config["limits"]["daily_reset_time"] = "00:00"
            try:
                self.config.save_config()
                self.logger.log_info("已自动修复重置时间配置为默认值00:00")
            except Exception as save_error:
                self.logger.log_error("保存重置时间配置失败: {}", save_error)

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
