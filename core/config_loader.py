"""
配置加载和解析模块

负责从配置文件加载和解析所有限制相关设置。
"""


class ConfigLoader:
    """配置加载器类"""

    def __init__(self, plugin):
        """
        初始化ConfigLoader

        Args:
            plugin: 插件实例引用
        """
        self.plugin = plugin
        self.config = plugin.config
        self.logger = plugin.logger

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

        返回：
            bool: 加载成功返回True，失败返回False
        """
        self.parse_group_limits()
        self.parse_user_limits()
        self.parse_group_modes()
        self.parse_time_period_limits()
        self.load_skip_patterns()
        self.validate_daily_reset_time()

        self.logger.log_info(
            "已加载 {} 个群组限制、{} 个用户限制、{} 个群组模式配置、{} 个时间段限制和{} 个忽略模式",
            len(self.plugin.group_limits),
            len(self.plugin.user_limits),
            len(self.plugin.group_modes),
            len(self.plugin.time_period_limits),
            len(self.plugin.skip_patterns),
        )

        # 加载安全配置
        self.load_security_config()

    def parse_limits_config(
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
            self.parse_limit_line(line, limits_dict, limit_type)

    def parse_group_limits(self):
        """解析群组特定限制配置"""
        self.parse_limits_config("group_limits", self.plugin.group_limits, "群组")

    def parse_user_limits(self):
        """解析用户特定限制配置"""
        self.parse_limits_config("user_limits", self.plugin.user_limits, "用户")

    def parse_config_lines(self, config_text, parser_func):
        """
        通用配置行解析器

        Args:
            config_text: 配置文本（字符串或列表）
            parser_func: 解析函数
        """
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

    def validate_config_structure(self) -> bool:
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
            self.plugin._handle_error(e, "配置结构验证")
            return False

    def safe_parse_int(self, value_str, default=None):
        """
        安全解析整数，避免重复的异常处理

        Args:
            value_str: 要解析的值
            default: 解析失败时的默认值

        Returns:
            int or None: 解析成功返回整数，失败返回默认值
        """
        try:
            return int(value_str)
        except (ValueError, TypeError):
            return default

    def validate_config_line(self, line, required_separator=":", min_parts=2):
        """
        验证配置行格式

        Args:
            line: 配置行
            required_separator: 必需的分隔符
            min_parts: 最小部分数

        Returns:
            list or None: 验证成功返回分割后的列表，失败返回None
        """
        line = line.strip()
        if not line or required_separator not in line:
            return None

        parts = line.split(required_separator, min_parts - 1)
        if len(parts) < min_parts:
            return None

        return parts

    def parse_limit_line(self, line, limits_dict, limit_type):
        """
        解析单行限制配置

        Args:
            line: 配置行
            limits_dict: 目标限制字典
            limit_type: 限制类型描述
        """
        parts = self.validate_config_line(line)
        if not parts:
            return

        entity_id = parts[0].strip()
        limit_str = parts[1].strip()

        limit = self.safe_parse_int(limit_str)
        if entity_id and limit is not None:
            limits_dict[entity_id] = limit
        else:
            self.logger.log_warning("{}限制配置格式错误: {}", limit_type, line)

    def parse_group_modes(self):
        """解析群组模式配置"""
        group_mode_text = self.config["limits"].get("group_mode_settings", "")
        self.parse_config_lines(group_mode_text, self.parse_group_mode_line)

    def parse_group_mode_line(self, line):
        """
        解析单行群组模式配置

        Args:
            line: 配置行
        """
        parts = self.validate_config_line(line)
        if not parts:
            return

        group_id = parts[0].strip()
        mode = parts[1].strip()

        if group_id and mode in ["shared", "individual"]:
            self.plugin.group_modes[group_id] = mode
        else:
            self.logger.log_warning("群组模式配置格式错误: {}", line)

    def parse_time_period_limits(self):
        """解析时间段限制配置"""
        if hasattr(self.plugin, "time_period_mgr"):
            self.plugin.time_period_mgr.parse_time_period_limits()
        else:
            # 兼容旧代码：直接在插件中处理
            time_period_config = self.config["limits"].get("time_period_limits", [])
            self.plugin.time_period_limits = []

            if isinstance(time_period_config, str):
                lines = [
                    line.strip()
                    for line in time_period_config.strip().split("\n")
                    if line.strip()
                ]
            elif isinstance(time_period_config, list):
                lines = [str(line).strip() for line in time_period_config if str(line).strip()]
            else:
                lines = []

            for line in lines:
                parts = line.split("|")
                if len(parts) >= 3:
                    try:
                        start_time = parts[0].strip()
                        end_time = parts[1].strip()
                        limit = int(parts[2].strip())
                        self.plugin.time_period_limits.append({
                            "start_time": start_time,
                            "end_time": end_time,
                            "limit": limit
                        })
                    except (ValueError, IndexError):
                        self.logger.log_warning("时间段限制配置格式错误: {}", line)

    def load_skip_patterns(self):
        """加载忽略模式配置"""
        self.plugin.skip_patterns = self.config["limits"].get("skip_patterns", ["#", "*"])

    def load_security_config(self):
        """加载安全配置"""
        try:
            security_config = self.config.get("security", {})

            # 加载基础配置
            self.load_basic_security_config(security_config)

            # 加载检测阈值配置
            self.load_detection_thresholds(security_config)

            # 加载自动限制配置
            self.load_auto_block_config(security_config)

            # 加载通知配置
            self.load_notification_config(security_config)

            # 初始化通知记录
            self.init_notification_records()

            self.logger.log_info(
                "安全配置加载完成，防刷机制{}",
                "已启用" if self.plugin.anti_abuse_enabled else "未启用",
            )

        except Exception as e:
            self.logger.log_error("加载安全配置失败: {}", str(e))
            # 使用默认值
            self.set_default_security_config()

    def load_basic_security_config(self, security_config):
        """
        加载基础安全配置

        Args:
            security_config: 安全配置字典
        """
        self.plugin.anti_abuse_enabled = security_config.get("anti_abuse_enabled", False)

    def load_detection_thresholds(self, security_config):
        """
        加载检测阈值配置

        Args:
            security_config: 安全配置字典
        """
        self.plugin.rapid_request_threshold = security_config.get(
            "rapid_request_threshold", 10
        )  # 10秒内请求次数
        self.plugin.rapid_request_window = security_config.get(
            "rapid_request_window", 10
        )  # 时间窗口（秒）
        self.plugin.consecutive_request_threshold = security_config.get(
            "consecutive_request_threshold", 5
        )  # 连续请求次数
        self.plugin.consecutive_request_window = security_config.get(
            "consecutive_request_window", 30
        )  # 时间窗口（秒）

    def load_auto_block_config(self, security_config):
        """
        加载自动限制配置

        Args:
            security_config: 安全配置字典
        """
        self.plugin.auto_block_duration = security_config.get(
            "auto_block_duration", 300
        )  # 自动限制时长（秒）
        self.plugin.block_notification_template = security_config.get(
            "block_notification_template",
            "检测到异常使用行为，您已被临时限制使用{auto_block_duration}秒",
        )

    def load_notification_config(self, security_config):
        """
        加载通知配置

        Args:
            security_config: 安全配置字典
        """
        self.plugin.admin_notification_enabled = security_config.get(
            "admin_notification_enabled", True
        )

        # 处理admin_users配置，兼容字符串和列表两种格式
        admin_users = security_config.get("admin_users", [])
        if isinstance(admin_users, str):
            # 如果是字符串，按换行符分割并过滤空值
            self.plugin.admin_users = [
                user.strip() for user in admin_users.split("\n") if user.strip()
            ]
        else:
            # 如果是列表或其他可迭代类型，直接使用并确保所有元素都是字符串
            self.plugin.admin_users = [
                str(user).strip() for user in admin_users if str(user).strip()
            ]

        self.plugin.notification_cooldown = security_config.get(
            "notification_cooldown", 300
        )  # 通知冷却时间（秒）

    def init_notification_records(self):
        """初始化通知记录"""
        self.plugin.notified_users = {}  # 已通知用户记录
        self.plugin.notified_admins = {}  # 已通知管理员记录

    def set_default_security_config(self):
        """设置默认安全配置"""
        self.plugin.anti_abuse_enabled = False
        self.plugin.rapid_request_threshold = 10
        self.plugin.rapid_request_window = 10
        self.plugin.consecutive_request_threshold = 5
        self.plugin.consecutive_request_window = 30
        self.plugin.auto_block_duration = 300
        self.plugin.block_notification_template = (
            "检测到异常使用行为，您已被临时限制使用{auto_block_duration}秒"
        )
        self.plugin.admin_notification_enabled = True
        self.plugin.admin_users = []
        self.plugin.notification_cooldown = 300
        self.plugin.notified_users = {}
        self.plugin.notified_admins = {}

    def validate_daily_reset_time(self):
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
