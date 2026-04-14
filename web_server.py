"""
Web管理界面服务器
提供可视化界面查看使用统计和配置管理

本模块实现了一个基于Flask的Web服务器，用于展示AstrBot插件的使用统计信息。
主要功能包括：
- 用户和群组使用数据的可视化展示
- 实时统计信息监控
- 密码保护的安全访问

版本: v2.8.9
作者: Sakura520222
"""

import datetime
import json
import os
import random
import socket
import threading
import time
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS


class TrendDataStorage:
    """
    趋势数据本地存储管理类

    负责管理使用趋势历史数据的持久化存储，包括：
    - 每日使用统计数据的存储和读取
    - 历史趋势数据的管理
    - 数据的归档和清理
    - 多线程安全的读写操作

    属性：
        storage_dir (str): 存储目录路径
        max_days (int): 最大保留天数
        _lock (threading.Lock): 线程锁，确保数据一致性
    """

    def __init__(self, storage_dir: str = "data/trend_data", max_days: int = 365):
        """
        初始化趋势数据存储管理器

        参数：
            storage_dir: 存储目录路径
            max_days: 最大保留天数，超过此期限的数据将被自动清理
        """
        self.storage_dir = storage_dir
        self.max_days = max_days
        self._lock = threading.Lock()

        # 确保存储目录存在
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        """确保存储目录存在"""
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
        except Exception as e:
            print(f"创建趋势数据存储目录失败: {e}")

    def _get_date_key(self, date_obj: datetime.datetime) -> str:
        """获取日期键"""
        return date_obj.strftime("%Y-%m-%d")

    def _get_file_path(self, date_key: str) -> str:
        """获取数据文件路径"""
        return os.path.join(self.storage_dir, f"{date_key}.json")

    def save_daily_stats(
        self, date_obj: datetime.datetime, stats_data: dict[str, Any]
    ) -> bool:
        """
        保存每日统计数据

        参数：
            date_obj: 日期对象
            stats_data: 统计数据字典

        返回：
            bool: 保存成功返回True，失败返回False
        """
        if not stats_data or not isinstance(stats_data, dict):
            return False

        date_key = self._get_date_key(date_obj)
        file_path = self._get_file_path(date_key)

        with self._lock:
            try:
                # 读取现有数据
                existing_data = self._load_json_file(file_path)

                # 合并数据
                if existing_data:
                    existing_data.update(stats_data)
                    stats_data = existing_data

                # 添加元数据
                stats_data["date"] = date_key
                stats_data["saved_at"] = datetime.datetime.now().isoformat()

                # 保存数据
                return self._save_json_file(file_path, stats_data)

            except Exception as e:
                print(f"保存每日统计数据失败 ({date_key}): {e}")
                return False

    def load_daily_stats(self, date_obj: datetime.datetime) -> dict[str, Any] | None:
        """
        加载每日统计数据

        参数：
            date_obj: 日期对象

        返回：
            Dict[str, Any]: 统计数据字典，如果文件不存在返回None
        """
        date_key = self._get_date_key(date_obj)
        file_path = self._get_file_path(date_key)

        with self._lock:
            return self._load_json_file(file_path)

    def load_history_stats(self, days: int = 30) -> list[dict[str, Any]]:
        """
        加载历史统计数据

        参数：
            days: 要加载的天数

        返回：
            List[Dict[str, Any]]: 历史统计数据列表，按日期排序
        """
        history_data = []
        today = datetime.datetime.now()

        with self._lock:
            for i in range(days):
                date = today - datetime.timedelta(days=i)
                date_key = self._get_date_key(date)
                file_path = self._get_file_path(date_key)

                data = self._load_json_file(file_path)
                if data:
                    history_data.append(data)

        # 按日期排序（从早到晚）
        history_data.sort(key=lambda x: x.get("date", ""))
        return history_data

    def get_trend_data(self, period: str = "week") -> list[dict[str, Any]]:
        """
        获取趋势数据

        参数：
            period: 时间周期 ('day', 'week', 'month')

        返回：
            List[Dict[str, Any]]: 趋势数据列表
        """
        # 根据周期确定天数
        period_days_map = {"day": 7, "week": 28, "month": 90}
        days = period_days_map.get(period, 28)

        # 加载历史数据
        history_data = self.load_history_stats(days)

        # 如果有历史数据，返回历史数据
        if history_data:
            return history_data

        # 如果没有历史数据，返回空列表（前端会处理）
        return []

    def _extract_date_from_filename(self, filename: str) -> datetime.datetime | None:
        """
        从文件名中提取日期

        参数：
            filename: 文件名

        返回：
            datetime.datetime: 提取的日期对象，失败则返回None
        """
        if not filename.endswith(".json"):
            return None

        # 移除.json扩展名
        date_str = filename[:-5]

        # 处理带后缀的文件名（如：2025-11-22_trend_data_recent -> 2025-11-22）
        if "_" in date_str:
            date_str = date_str.split("_")[0]  # 取第一部分作为日期

        try:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None

    def _should_delete_file(
        self, file_date: datetime.datetime, cutoff_date: datetime.datetime
    ) -> bool:
        """
        判断文件是否应该被删除

        参数：
            file_date: 文件日期
            cutoff_date: 截止日期

        返回：
            bool: 是否应该删除
        """
        return file_date < cutoff_date

    def cleanup_old_data(self, max_days: int | None = None) -> int:
        """
        清理过旧数据

        参数：
            max_days: 最大保留天数，如果为None则使用初始化时的值

        返回：
            int: 清理的文件数量
        """
        if max_days is None:
            max_days = self.max_days

        cleaned_count = 0
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=max_days)

        with self._lock:
            try:
                # 获取存储目录中的所有文件
                if not os.path.exists(self.storage_dir):
                    return 0

                for filename in os.listdir(self.storage_dir):
                    file_path = os.path.join(self.storage_dir, filename)

                    # 从文件名提取日期
                    file_date = self._extract_date_from_filename(filename)
                    if file_date is None:
                        continue

                    # 判断是否应该删除
                    if self._should_delete_file(file_date, cutoff_date):
                        os.remove(file_path)
                        cleaned_count += 1

            except Exception as e:
                print(f"清理过旧趋势数据失败: {e}")

        return cleaned_count

    def _load_json_file(self, file_path: str) -> dict[str, Any] | None:
        """
        安全地加载JSON文件

        参数：
            file_path: 文件路径

        返回：
            Dict[str, Any]: 文件内容，如果加载失败返回None
        """
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载JSON文件失败 ({file_path}): {e}")
            return None

    def _save_json_file(self, file_path: str, data: dict[str, Any]) -> bool:
        """
        安全地保存JSON文件

        参数：
            file_path: 文件路径
            data: 要保存的数据

        返回：
            bool: 保存成功返回True，失败返回False
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 原子性写入：先写入临时文件，再重命名
            temp_file = f"{file_path}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            os.replace(temp_file, file_path)
            return True

        except Exception as e:
            print(f"保存JSON文件失败 ({file_path}): {e}")
            # 清理可能存在的临时文件
            temp_file = f"{file_path}.tmp"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            return False


class WebServer:
    """
    Web服务器类

    负责管理插件的Web界面，提供用户友好的统计信息展示和配置管理功能。

    主要特性：
    - 自动端口检测和调整
    - 会话管理和密码保护
    - 实时数据统计和可视化
    - 响应式Web界面设计
    - 错误处理和日志记录

    属性：
        host (str): 服务器监听地址
        port (int): 服务器监听端口
        plugin: 主插件实例引用
        app (Flask): Flask应用实例
        _server_running (bool): 服务器运行状态标志
        _server_thread (Thread): 服务器运行线程
    """

    def __init__(self, daily_limit_plugin, host="127.0.0.1", port=10245, domain=""):
        self.plugin = daily_limit_plugin
        self.host = host
        self.original_port = port  # 保存原始端口配置
        self.port = port
        self.domain = domain

        # 初始化趋势数据本地存储管理器
        self.trend_storage = TrendDataStorage(
            storage_dir="data/trend_data",
            max_days=365,  # 保存一年的数据
        )

        # 初始化数据清理相关变量
        self._cleanup_thread = None
        self._cleanup_running = False

        self.app = Flask(__name__)

        # 设置会话密钥
        self.app.secret_key = os.urandom(24)
        CORS(self.app)

        # 设置模板和静态文件目录
        self.app.template_folder = "templates"
        self.app.static_folder = "static"

        # Web服务器控制变量
        self._server_thread = None
        self._server_running = False
        self._server_instance = None
        self._last_error = None  # 记录最后一次错误信息
        self._start_time = None  # 服务器启动时间

        # 检查端口占用并自动切换
        self._check_and_adjust_port()

        self._setup_routes()

    def _log(self, message):
        """日志记录方法"""
        if self.plugin and hasattr(self.plugin, "_log_info"):
            self.plugin._log_info("{}", message)
        else:
            print(f"[WebServer] {message}")

    def _is_port_available(self, port):
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex((self.host, port))
                return result != 0  # 如果连接失败，说明端口可用
        except Exception:
            return False

    def _find_available_port(self, start_port=None):
        """查找可用的端口"""
        if start_port is None:
            start_port = self.original_port

        # 从原始端口开始，尝试100个端口范围
        for port in range(start_port, start_port + 100):
            if self._is_port_available(port):
                return port

        # 如果指定范围内没有找到，随机尝试
        for _ in range(10):
            port = random.randint(10000, 65535)
            if self._is_port_available(port):
                return port

        return None  # 没有找到可用端口

    def _check_and_adjust_port(self):
        """检查端口占用并自动调整"""
        # 检查原始端口是否可用
        if self._is_port_available(self.original_port):
            self.port = self.original_port
            self._log(f"Web管理界面将使用默认端口: {self.port}")
            return

        # 端口被占用，查找可用端口
        available_port = self._find_available_port()
        if available_port:
            self.port = available_port
            self._log(
                f"警告: 默认端口 {self.original_port} 被占用，已自动切换到端口: {self.port}"
            )

            # 保存新端口到配置
            self._save_port_to_config(available_port)
        else:
            # 没有找到可用端口，使用原始端口（可能会启动失败）
            self.port = self.original_port
            self._log(
                f"警告: 无法找到可用端口，将尝试使用端口: {self.port}（可能会启动失败）"
            )

    def _force_release_port(self, port):
        """强制释放指定端口的占用"""
        try:
            # 尝试创建socket并绑定到指定端口，然后立即关闭
            # 这有助于释放可能处于TIME_WAIT状态的端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, port))
            sock.close()
            self._log(f"尝试释放端口 {port} 完成")
        except Exception as e:
            self._log(f"尝试释放端口 {port} 失败: {e}")

    def _save_port_to_config(self, port):
        """保存端口到配置文件"""
        try:
            if self.plugin and hasattr(self.plugin, "config"):
                # 更新配置中的端口
                if "web_server" not in self.plugin.config:
                    self.plugin.config["web_server"] = {}

                self.plugin.config["web_server"]["port"] = port

                # 保存配置
                if hasattr(self.plugin.config, "save_config"):
                    self.plugin.config.save_config()
                    print(f"已保存新端口 {port} 到配置文件")
                else:
                    print("警告: 无法保存端口到配置文件，配置对象缺少save_config方法")
        except Exception as e:
            print(f"保存端口到配置时出错: {e}")

    def _setup_routes(self):
        """设置路由"""
        # 设置认证相关的辅助函数
        self._setup_auth_helpers()

        # 设置认证路由
        self._setup_auth_routes()

        # 设置页面路由
        self._setup_page_routes()

        # 设置API路由
        self._setup_api_routes()

    def _setup_auth_helpers(self):
        """设置认证相关的辅助函数"""

        def check_auth():
            """检查用户是否已登录"""
            # 如果未设置密码，则无需验证
            if not self._get_web_password():
                return True

            # 检查会话中是否有登录标记
            return session.get("logged_in", False)

        def require_auth(f):
            """需要认证的装饰器"""

            def decorated_function(*args, **kwargs):
                if not check_auth():
                    return redirect(url_for("login"))
                return f(*args, **kwargs)

            decorated_function.__name__ = f.__name__
            return decorated_function

        # 将装饰器保存为实例变量，供其他方法使用
        self.require_auth = require_auth

    def _setup_auth_routes(self):
        """设置认证路由"""

        @self.app.route("/login", methods=["GET", "POST"])
        def login():
            """登录页面"""
            # 如果未设置密码，直接重定向到首页
            web_password = self._get_web_password()
            if not web_password:
                session["logged_in"] = True
                return redirect(url_for("index"))

            if request.method == "POST":
                password = request.form.get("password", "")
                if password == web_password:
                    session["logged_in"] = True
                    return redirect(url_for("index"))
                else:
                    return render_template("login.html", error="密码错误")

            return render_template("login.html")

        @self.app.route("/logout")
        def logout():
            """登出"""
            session.pop("logged_in", None)
            return redirect(url_for("login"))

    def _setup_page_routes(self):
        """设置页面路由"""

        @self.app.route("/")
        @self.require_auth
        def index():
            """主页面"""
            return render_template("index.html")

    def _setup_api_routes(self):
        """设置API路由"""
        self._setup_stats_api()
        self._setup_config_api()
        self._setup_users_api()
        self._setup_groups_api()
        self._setup_trends_api()

    def _setup_stats_api(self):
        """设置统计API路由"""

        @self.app.route("/api/stats")
        @self.require_auth
        def get_stats():
            """获取统计信息"""
            return self._handle_api_request(self._get_usage_stats)

    def _setup_config_api(self):
        """设置配置API路由"""

        @self.app.route("/api/config")
        @self.require_auth
        def get_config():
            """获取配置信息"""
            return self._handle_api_request(self._get_config_data)

        @self.app.route("/api/config", methods=["POST"])
        @self.require_auth
        def update_config():
            """更新配置"""
            try:
                config_data = request.get_json()
                result = self._update_config(config_data)
                return jsonify({"success": True, "data": result})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500

    def _setup_users_api(self):
        """设置用户API路由"""

        @self.app.route("/api/users")
        @self.require_auth
        def get_users():
            """获取用户使用情况"""
            return self._handle_api_request(self._get_users_data)

    def _setup_groups_api(self):
        """设置群组API路由"""

        @self.app.route("/api/groups")
        @self.require_auth
        def get_groups():
            """获取群组使用情况"""
            return self._handle_api_request(self._get_groups_data)

    def _setup_trends_api(self):
        """设置趋势分析API路由"""

        @self.app.route("/api/trends")
        @self.require_auth
        def get_trends():
            """获取趋势分析数据"""
            try:
                period = request.args.get("period", "week")
                data = self._get_trends_data(period)
                return jsonify({"success": True, "data": data})
            except Exception as e:
                if self.plugin:
                    self.plugin._log_error("获取趋势分析数据失败: {}", str(e))
                else:
                    print(f"获取趋势分析数据失败: {e}")

                return jsonify({"success": False, "error": "获取趋势分析数据失败"}), 500

    def _handle_api_request(self, api_function):
        """处理API请求的通用方法"""
        try:
            data = api_function()
            return jsonify({"success": True, "data": data})
        except Exception as e:
            # 记录错误日志
            if self.plugin:
                self.plugin._log_error("Web API请求处理失败: {}", str(e))
            else:
                print(f"Web API请求处理失败: {e}")

            return jsonify(
                {"success": False, "error": "服务器内部错误，请稍后重试"}
            ), 500

    def _get_usage_stats(self):
        """
        获取使用统计信息

        从Redis中获取活跃用户数、活跃群组数和总请求数等关键统计指标，
        包括平均请求数、峰值请求数、峰值小时等扩展指标。

        返回：
            dict: 包含统计信息的字典
        """
        if not self.plugin.redis:
            return {}

        # 使用与主插件相同的日期计算逻辑
        today = self.plugin._get_reset_period_date()
        stats = self._initialize_stats_dict(today)

        # 获取活跃用户数和总请求数
        self._update_active_users_stats(stats, today)

        # 获取活跃群组数
        self._update_active_groups_stats(stats, today)

        # 获取峰值小时数据
        self._update_peak_hour_stats(stats)

        # 保存每日统计数据到本地存储
        self._save_daily_stats(stats)

        return stats

    def _update_active_users_stats(self, stats, today):
        """更新活跃用户统计信息"""
        user_keys = self._get_user_keys_for_date(today)
        stats["active_users"] = len(user_keys)

        # 计算总请求数和平均请求数
        total_requests = self._calculate_total_requests(user_keys)
        stats["total_requests"] = total_requests

        if stats["active_users"] > 0:
            stats["avg_requests_per_user"] = round(
                total_requests / stats["active_users"], 2
            )
        else:
            stats["avg_requests_per_user"] = 0

    def _update_active_groups_stats(self, stats, today):
        """更新活跃群组统计信息"""
        group_keys = self._get_group_keys_for_date(today)
        stats["active_groups"] = len(group_keys)

    def _update_peak_hour_stats(self, stats):
        """更新峰值小时统计信息"""
        today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        peak_hour_data = self._get_today_peak_hour(today_date)
        stats["peak_hour_requests"] = peak_hour_data["peak_requests"]
        stats["peak_hour"] = peak_hour_data["peak_hour"]

    def _save_daily_stats(self, stats):
        """
        保存每日统计数据到本地存储

        参数：
            stats (dict): 统计数据字典
        """
        if not stats or not isinstance(stats, dict):
            return False

        try:
            # 获取日期对象
            date_str = stats.get("date")
            if not date_str:
                return False

            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")

            # 保存到本地存储
            return self.trend_storage.save_daily_stats(date_obj, stats)
        except Exception as e:
            if self.plugin:
                self.plugin._log_error("保存每日统计数据失败: {}", str(e))
            else:
                print(f"保存每日统计数据失败: {e}")
            return False

    def _initialize_stats_dict(self, date_str):
        """初始化统计字典"""
        return {
            "total_requests": 0,
            "active_users": 0,
            "active_groups": 0,
            "date": date_str,
            "avg_requests_per_user": 0,
            "peak_hour_requests": 0,
            "peak_hour": "",
            "total_users": 0,
            "total_groups": 0,
        }

    def _get_today_peak_hour(self, today_date):
        """
        获取今日的峰值小时数据

        参数：
            today_date (str): 今日日期，格式为YYYY-MM-DD

        返回：
            dict: 包含峰值请求数和峰值小时的字典
        """
        peak_requests = 0
        peak_hour = ""

        try:
            # 遍历今日所有小时（00-23）
            for hour in range(24):
                hour_str = f"{hour:02d}"
                hour_key = f"astrbot:trend_stats:hourly:{today_date}-{hour_str}"

                # 获取该小时的请求数
                request_count = self.plugin.redis.hget(hour_key, "total_requests")
                if request_count:
                    request_count = int(request_count)
                    if request_count > peak_requests:
                        peak_requests = request_count
                        peak_hour = hour_str
        except Exception as e:
            if self.plugin:
                self.plugin._log_error("获取峰值小时数据失败: {}", str(e))
            else:
                print(f"获取峰值小时数据失败: {e}")

        return {"peak_requests": peak_requests, "peak_hour": peak_hour}

    def _get_user_keys_for_date(self, date_str):
        """获取指定日期的用户键"""
        user_pattern = f"astrbot:daily_limit:{date_str}:*:*"
        return self.plugin.redis.keys(user_pattern)

    def _get_group_keys_for_date(self, date_str):
        """获取指定日期的群组键"""
        group_pattern = f"astrbot:daily_limit:{date_str}:group:*"
        return self.plugin.redis.keys(group_pattern)

    def _calculate_total_requests(self, user_keys):
        """计算总请求数"""
        total_requests = 0
        for key in user_keys:
            usage = self.plugin.redis.get(key)
            if usage:
                total_requests += int(usage)
        return total_requests

    def _get_config_data(self):
        """获取配置数据"""
        config = self.plugin.config

        return {
            "default_daily_limit": config["limits"]["default_daily_limit"],
            "exempt_users": config["limits"]["exempt_users"],
            "priority_users": config["limits"].get(
                "priority_users", []
            ),  # 添加优先级用户字段
            "group_limits": config["limits"]["group_limits"],
            "user_limits": config["limits"]["user_limits"],
            "group_mode_settings": config["limits"]["group_mode_settings"],
            "time_period_limits": config["limits"]["time_period_limits"],
            "skip_patterns": config["limits"]["skip_patterns"],
            "custom_messages": config["limits"].get("custom_messages", {}),
            "redis_config": config["redis"],
        }

    def _validate_config_data(self, config_data):
        """
        验证配置数据格式

        参数：
            config_data (dict): 配置数据

        异常：
            ValueError: 配置数据格式错误时抛出
        """
        if not isinstance(config_data, dict):
            raise ValueError("配置数据格式错误")

    def _update_default_daily_limit(self, config_data):
        """
        更新默认每日限制

        参数：
            config_data (dict): 配置数据

        异常：
            ValueError: 配置值无效时抛出
        """
        if "default_daily_limit" in config_data:
            new_limit = config_data["default_daily_limit"]
            if isinstance(new_limit, int) and new_limit > 0:
                self.plugin.config["limits"]["default_daily_limit"] = new_limit
            else:
                raise ValueError("默认每日限制必须是大于0的整数")

    def _update_user_list(self, config_data, list_name, config_key):
        """
        更新用户列表（豁免用户或优先级用户）

        参数：
            config_data (dict): 配置数据
            list_name (str): 配置数据中的列表名称
            config_key (str): 配置文件中的键名

        异常：
            ValueError: 配置值无效时抛出
        """
        if list_name in config_data:
            user_list = config_data[list_name]
            if isinstance(user_list, list):
                # 验证并清理每个用户ID
                valid_users = []
                for user_id in user_list:
                    if isinstance(user_id, str) and user_id.strip():
                        valid_users.append(user_id.strip())
                self.plugin.config["limits"][config_key] = valid_users
            else:
                raise ValueError(f"{list_name}必须是字符串列表")

    def _update_list_config(self, config_data, config_key):
        """更新列表类型的配置"""
        if config_key in config_data:
            value = config_data[config_key]
            if isinstance(value, list):
                valid_items = [str(item).strip() for item in value if str(item).strip()]
                self.plugin.config["limits"][config_key] = valid_items
            else:
                raise ValueError(f"{config_key}必须是列表格式")

    def _update_string_config(self, config_data, config_key):
        """
        更新字符串类型的配置

        参数：
            config_data (dict): 配置数据
            config_key (str): 配置键名

        异常：
            ValueError: 配置值无效时抛出
        """
        if config_key in config_data:
            value = config_data[config_key]
            if isinstance(value, str):
                self.plugin.config["limits"][config_key] = value
            else:
                raise ValueError(f"{config_key}必须是字符串格式")

    def _update_custom_messages(self, config_data):
        """
        更新自定义消息

        参数：
            config_data (dict): 配置数据

        异常：
            ValueError: 配置值无效时抛出
        """
        if "custom_messages" in config_data:
            custom_messages = config_data["custom_messages"]
            if isinstance(custom_messages, dict):
                # 合并自定义消息，保留原有配置
                current_messages = self.plugin.config["limits"].get(
                    "custom_messages", {}
                )
                current_messages.update(custom_messages)
                self.plugin.config["limits"]["custom_messages"] = current_messages
            else:
                raise ValueError("自定义消息必须是字典格式")

    def _update_redis_config(self, config_data):
        """
        更新Redis配置

        参数：
            config_data (dict): 配置数据

        异常：
            ValueError: 配置值无效时抛出
        """
        if "redis_config" in config_data:
            redis_config = config_data["redis_config"]
            if isinstance(redis_config, dict):
                # 验证Redis配置字段
                required_fields = ["host", "port", "db", "password"]
                for field in required_fields:
                    if field not in redis_config:
                        raise ValueError(f"Redis配置缺少必要字段: {field}")

                # 更新Redis配置
                self.plugin.config["redis"] = redis_config

                # 重新初始化Redis连接
                self.plugin._init_redis()
            else:
                raise ValueError("Redis配置必须是字典格式")

    def _finalize_config_update(self):
        """
        完成配置更新的最终操作
        """
        # 保存配置到文件
        self.plugin.config.save_config()

        # 重新加载插件配置
        self.plugin._load_limits_from_config()

        # 记录配置更新日志
        if self.plugin:
            self.plugin._log_info("通过Web界面更新配置成功")

    def _update_config(self, config_data):
        """
        更新配置数据

        参数：
            config_data (dict): 新的配置数据

        返回：
            dict: 更新后的配置数据
        """
        try:
            # 验证配置数据
            self._validate_config_data(config_data)

            # 更新各项配置
            self._update_limits_config(config_data)
            self._update_redis_config(config_data)

            # 完成配置更新
            self._finalize_config_update()

            # 返回更新后的配置数据
            return self._get_config_data()

        except Exception as e:
            # 记录错误日志
            if self.plugin:
                self.plugin._log_error("更新配置失败: {}", str(e))
            else:
                print(f"更新配置失败: {e}")

            # 重新抛出异常，让调用者处理
            raise

    def _update_limits_config(self, config_data):
        """
        更新限制相关配置

        参数：
            config_data (dict): 新的配置数据
        """
        # 更新默认每日限制
        self._update_default_daily_limit(config_data)

        # 更新用户列表
        self._update_user_list(config_data, "exempt_users", "exempt_users")
        self._update_user_list(config_data, "priority_users", "priority_users")

        # 更新字符串类型的配置
        string_configs = [
            "group_limits",
            "user_limits",
            "group_mode_settings",
            "time_period_limits",
        ]
        for config_key in string_configs:
            self._update_string_config(config_data, config_key)

        # 更新列表类型的配置
        self._update_list_config(config_data, "skip_patterns")

        # 更新自定义消息
        self._update_custom_messages(config_data)

    def _get_users_data(self):
        """
        获取用户使用数据

        从Redis中获取所有用户的使用统计信息，包括使用次数、限制和剩余次数。

        返回：
            list: 用户数据列表，每个元素为字典格式：
                {
                    'user_id': str,      # 用户ID
                    'usage_count': int,  # 使用次数
                    'limit': int,       # 限制次数
                    'remaining': int,    # 剩余次数
                    'group_id': str,    # 群组ID（如果有）
                    'group_name': str   # 群组名称（如果有）
                }
        """
        if not self.plugin or not self.plugin.redis:
            return []

        try:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            user_keys = self._get_user_keys(today)

            users_data = []
            for key in user_keys:
                user_data = self._parse_user_key_data(key)
                if user_data:
                    users_data.append(user_data)

            return self._sort_users_data(users_data)
        except Exception as e:
            if self.plugin:
                self.plugin._log_error("获取用户数据失败: {}", str(e))
            else:
                print(f"获取用户数据失败: {e}")
            return []

    def _get_user_keys(self, date_str):
        """
        获取用户相关的Redis键

        根据日期模式从Redis中获取所有用户相关的键名，用于用户数据统计。

        参数：
            date_str (str): 日期字符串，格式为YYYY-MM-DD

        返回：
            list: 用户键列表，格式为 ['astrbot:daily_limit:2024-01-01:group_id:user_id', ...]
        """
        if not self.plugin or not self.plugin.redis:
            return []

        try:
            user_pattern = f"astrbot:daily_limit:{date_str}:*:*"
            return self.plugin.redis.keys(user_pattern)
        except Exception as e:
            if self.plugin:
                self.plugin._log_error("获取用户键列表失败: {}", str(e))
            else:
                print(f"获取用户键列表失败: {e}")
            return []

    def _parse_user_key_data(self, key):
        """解析用户键数据"""
        # 从key中提取用户ID和群组ID
        user_id, group_id = self._extract_ids_from_key(key)
        if not user_id or not group_id:
            return None

        # 跳过群组键（群组键格式不同）
        if group_id == "group":
            return None

        # 获取使用次数
        usage = self._get_usage_from_key(key)
        if not usage:
            return None

        # 获取用户限制
        user_limit = self.plugin._get_user_limit(user_id, group_id)

        return {
            "user_id": user_id,
            "group_id": group_id,
            "usage_count": int(usage),
            "limit": user_limit,
            "remaining": max(0, user_limit - int(usage)),
        }

    def _extract_ids_from_key(self, key):
        """从Redis键中提取用户ID和群组ID"""
        parts = key.split(":")
        if len(parts) >= 5:
            return parts[-1], parts[-2]
        return None, None

    def _get_usage_from_key(self, key):
        """从Redis键获取使用次数"""
        return self.plugin.redis.get(key)

    def _sort_users_data(self, users_data):
        """对用户数据进行排序"""
        users_data.sort(key=lambda x: x["usage_count"], reverse=True)
        return users_data

    def _get_period_days(self, period):
        """根据周期类型获取分析天数

        参数：
            period (str): 分析周期，支持 'day', 'week', 'month'

        返回：
            int: 分析天数
        """
        period_days_map = {
            "day": 7,  # 最近7天
            "week": 28,  # 最近4周
            "month": 90,  # 最近3个月
        }
        return period_days_map.get(period, 28)  # 默认最近4周

    def _get_data_point_from_historical(self, date, date_str):
        """
        从历史数据获取数据点

        参数：
            date: 日期对象
            date_str: 日期字符串

        返回：
            dict: 数据点字典，失败返回None
        """
        historical_data = self.trend_storage.load_daily_stats(date)
        if historical_data:
            return {
                "date": date_str,
                "total_requests": historical_data.get("total_requests", 0),
                "active_users": historical_data.get("active_users", 0),
                "active_groups": historical_data.get("active_groups", 0),
                "source": "historical",
            }
        return None

    def _get_data_point_from_redis(self, date, date_str):
        """
        从Redis获取数据点

        参数：
            date: 日期对象
            date_str: 日期字符串

        返回：
            dict: 数据点字典，失败返回None
        """
        if self.plugin and self.plugin.redis:
            stats = self._get_daily_stats_from_redis(date_str)
            # 保存到本地存储以供将来使用
            self.trend_storage.save_daily_stats(date, stats)
            return {
                "date": date_str,
                "total_requests": stats["total_requests"],
                "active_users": stats["active_users"],
                "active_groups": stats["active_groups"],
                "source": "redis",
            }
        return None

    def _get_default_data_point(self, date_str):
        """
        获取默认数据点

        参数：
            date_str: 日期字符串

        返回：
            dict: 默认数据点字典
        """
        return {
            "date": date_str,
            "total_requests": 0,
            "active_users": 0,
            "active_groups": 0,
            "source": "default",
        }

    def _generate_trends_data_points(self, days):
        """
        生成趋势数据点（整合历史数据存储）

        参数：
            days (int): 分析天数

        返回：
            list: 趋势数据点列表
        """
        trends_data = []
        today = datetime.datetime.now()

        for i in range(days):
            # 计算日期
            date = today - datetime.timedelta(days=i)
            date_str = self._get_reset_period_date_for_date(date)

            # 优先从历史数据获取
            data_point = self._get_data_point_from_historical(date, date_str)
            if data_point:
                trends_data.append(data_point)
                continue

            # 其次从Redis获取
            data_point = self._get_data_point_from_redis(date, date_str)
            if data_point:
                trends_data.append(data_point)
                continue

            # 最后使用默认数据
            trends_data.append(self._get_default_data_point(date_str))

        # 按日期排序（从早到晚）
        trends_data.sort(key=lambda x: x["date"])
        return trends_data

    def _get_reset_period_date_for_date(self, date_obj):
        """
        获取指定日期对象对应的重置周期日期

        参数：
            date_obj: 日期对象

        返回：
            str: 重置周期日期字符串
        """
        # 获取配置的重置时间
        reset_time_str = self.plugin.config["limits"].get("daily_reset_time", "00:00")

        # 解析重置时间
        try:
            reset_hour, reset_minute = map(int, reset_time_str.split(":"))
            if not (0 <= reset_hour <= 23 and 0 <= reset_minute <= 59):
                raise ValueError("重置时间格式错误")
        except (ValueError, AttributeError):
            # 如果配置格式错误，使用默认的00:00
            reset_hour, reset_minute = 0, 0

        # 构建当前日期的重置时间
        current_reset_time = date_obj.replace(
            hour=reset_hour, minute=reset_minute, second=0, microsecond=0
        )

        # 如果当前时间已到达或超过重置时间，使用今天的日期
        # 否则使用昨天的日期
        if date_obj >= current_reset_time:
            return date_obj.strftime("%Y-%m-%d")
        else:
            yesterday = date_obj - datetime.timedelta(days=1)
            return yesterday.strftime("%Y-%m-%d")

    def _convert_historical_data(self, historical_trends):
        """
        转换历史数据格式以保持兼容性

        参数：
            historical_trends (list): 历史趋势数据列表

        返回：
            list: 转换后的数据列表
        """
        trends_data = []
        for data in historical_trends:
            trends_data.append(
                {
                    "date": data.get("date", ""),
                    "total_requests": data.get("total_requests", 0),
                    "active_users": data.get("active_users", 0),
                    "active_groups": data.get("active_groups", 0),
                    "source": "historical",
                }
            )
        return trends_data

    def _merge_trends_data(self, trends_data, days):
        """
        合并趋势数据，确保数据点数量足够

        参数：
            trends_data (list): 当前趋势数据列表
            days (int): 需要的数据点数量

        返回：
            list: 合并后的数据列表
        """
        if len(trends_data) < days:
            missing_days = days - len(trends_data)
            additional_data = self._generate_trends_data_points(missing_days)
            trends_data.extend(additional_data)
            # 按日期排序
            trends_data.sort(key=lambda x: x["date"])
        return trends_data

    def _get_trends_data(self, period="week"):
        """
        获取趋势分析数据（使用历史数据存储）

        参数：
            period (str): 分析周期，支持 'day', 'week', 'month'

        返回：
            dict: 趋势分析数据，包含日期、总请求数、活跃用户数、活跃群组数等
        """
        try:
            # 根据周期确定分析天数
            days = self._get_period_days(period)

            # 获取趋势数据
            trends_data, has_historical_data = self._fetch_trends_data(period, days)

            # 计算统计指标
            stats_summary = self._calculate_trends_summary(trends_data)

            return {
                "period": period,
                "days": days,
                "data": trends_data,
                "has_historical_data": has_historical_data,
                "summary": stats_summary,
            }

        except Exception as e:
            if self.plugin:
                self.plugin._log_error("获取趋势分析数据失败: {}", str(e))
            else:
                print(f"获取趋势分析数据失败: {e}")
            return {}

    def _fetch_trends_data(self, period, days):
        """
        获取趋势数据，优先使用历史存储，否则生成新数据

        参数：
            period (str): 分析周期
            days (int): 分析天数

        返回：
            tuple: (趋势数据列表, 是否有历史数据)
        """
        # 优先从本地存储获取历史趋势数据
        historical_trends = self.trend_storage.get_trend_data(period)
        has_historical_data = len(historical_trends) > 0

        if has_historical_data:
            # 转换历史数据格式
            trends_data = self._convert_historical_data(historical_trends)
            # 合并数据确保数量足够
            trends_data = self._merge_trends_data(trends_data, days)
        else:
            # 生成新的趋势数据
            trends_data = self._generate_trends_data_points(days)

        return trends_data, has_historical_data

    def _calculate_stats(self, data_list):
        """
        计算单个数据列表的统计指标

        参数：
            data_list (list): 数据列表

        返回：
            dict: 统计指标字典
        """
        if not data_list:
            return {"average": 0, "peak": 0, "min": 0, "total": 0}

        average = sum(data_list) / len(data_list)
        peak = max(data_list)
        min_val = min(data_list)
        total = sum(data_list)

        return {
            "average": round(average, 2),
            "peak": peak,
            "min": min_val,
            "total": total,
        }

    def _calculate_trends_summary(self, trends_data):
        """
        计算趋势数据的统计摘要

        参数：
            trends_data (list): 趋势数据列表

        返回：
            dict: 统计摘要数据
        """
        if not trends_data:
            return {}

        # 提取数据
        def get_data(key):
            return [item[key] for item in trends_data if key in item]

        total_requests = get_data("total_requests")
        active_users = get_data("active_users")
        active_groups = get_data("active_groups")

        # 计算各指标的统计数据
        return {
            "total_requests": self._calculate_stats(total_requests),
            "active_users": self._calculate_stats(active_users),
            "active_groups": self._calculate_stats(active_groups),
            "days_count": len(trends_data),
        }

    def _get_daily_stats_from_redis(self, date_str):
        """从Redis获取指定日期的统计数据"""
        stats = self._initialize_stats_dict(date_str)

        # 获取活跃用户数
        user_keys = self._get_user_keys_for_date(date_str)
        stats["active_users"] = len(user_keys)

        # 获取活跃群组数
        group_keys = self._get_group_keys_for_date(date_str)
        stats["active_groups"] = len(group_keys)

        # 计算总请求数
        stats["total_requests"] = self._calculate_total_requests(user_keys)

        return stats

    def _get_groups_data(self):
        """
        获取群组使用数据

        从Redis中获取所有群组的使用统计信息，包括群组模式、使用次数和限制。

        返回：
            list: 群组数据列表，每个元素为字典格式：
                {
                    'group_id': str,      # 群组ID
                    'usage_count': int,   # 使用次数
                    'limit': int,        # 限制次数
                    'remaining': int,     # 剩余次数
                    'mode': str          # 群组模式（shared/individual）
                }
        """
        if not self.plugin or not self.plugin.redis:
            return []

        try:
            # 使用与主插件相同的日期计算逻辑
            today = self.plugin._get_reset_period_date()
            group_keys = self._get_group_keys_for_date(today)

            groups_data = self._process_group_keys(group_keys)

            # 按使用量排序
            groups_data.sort(key=lambda x: x["usage_count"], reverse=True)
            return groups_data
        except Exception as e:
            self._log_group_data_error("获取群组数据失败", e)
            return []

    def _process_group_keys(self, group_keys):
        """处理群组键列表，返回群组数据"""
        groups_data = []
        for key in group_keys:
            group_data = self._process_single_group_key(key)
            if group_data:
                groups_data.append(group_data)
        return groups_data

    def _process_single_group_key(self, key):
        """处理单个群组键，返回群组数据"""
        try:
            # 从key中提取群组ID
            group_id = self._extract_group_id_from_key(key)
            if not group_id:
                return None

            # 获取使用次数
            usage = self.plugin.redis.get(key)
            if not usage:
                return None

            # 获取群组限制和模式
            group_limit = self.plugin._get_user_limit("dummy_user", group_id)
            group_mode = self.plugin._get_group_mode(group_id)

            return {
                "group_id": group_id,
                "usage_count": int(usage),
                "limit": group_limit,
                "remaining": max(0, group_limit - int(usage)),
                "mode": group_mode,
            }
        except Exception as e:
            self._log_group_data_error(f"处理群组数据失败 (键: {key})", e)
            return None

    def _extract_group_id_from_key(self, key):
        """从Redis键中提取群组ID"""
        parts = key.split(":")
        if len(parts) >= 5:
            return parts[-1]
        return None

    def _log_group_data_error(self, message, error):
        """记录群组数据错误日志"""
        if self.plugin:
            self.plugin._log_warning("{}: {}", message, str(error))
        else:
            print(f"{message}: {error}")

    def _get_web_password(self):
        """获取Web管理界面密码"""
        if not self.plugin or not self.plugin.config:
            return "limit"  # 默认密码

        # 从配置中获取密码
        web_config = self.plugin.config.get("web_server", {})
        password = web_config.get("password", "limit")

        # 如果密码为空字符串，返回None表示无需密码
        if password == "":
            return None

        return password

    def get_access_url(self):
        """获取访问链接"""
        if self.domain:
            # 如果有自定义域名，使用域名
            if self.domain.startswith(("http://", "https://")):
                return self.domain
            else:
                return f"http://{self.domain}"
        else:
            # 如果没有域名，使用IP和端口
            return f"http://{self.host}:{self.port}"

    def start(self):
        """
        启动Web服务器

        启动Flask应用并开始监听指定端口。如果端口被占用，会自动调整端口。

        返回：
            bool: 启动成功返回True，失败返回False
        """
        try:
            self._server_running = True
            self.app.run(host=self.host, port=self.port, debug=False)
            return True
        except Exception as e:
            error_msg = f"Web服务器启动失败: {e}"
            if self.plugin:
                self.plugin._log_error("{}", error_msg)
            else:
                print(error_msg)
            return False

    def start_async(self):
        """
        异步启动Web服务器

        启动Flask应用并返回服务器线程。

        返回：
            bool: 启动成功返回True，失败返回False
        """
        try:
            # 检查是否已经在运行
            if self.is_running():
                self._log("Web服务器已经在运行中")
                return True

            # 清理之前的错误信息
            self._last_error = None

            # 检查并调整端口
            self._adjust_port_if_needed()

            # 启动数据清理线程
            self._start_cleanup_thread()

            # 启动服务器线程
            self._start_server_thread()

            # 等待服务器启动并检查状态
            return self._wait_for_server_start()

        except Exception as e:
            self._handle_start_async_error(e)
            return False

    def _start_cleanup_thread(self):
        """启动数据清理线程"""
        try:
            self._cleanup_running = True
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_worker, daemon=True
            )
            self._cleanup_thread.start()
            self._log("数据清理线程已启动")
        except Exception as e:
            self._log(f"启动数据清理线程失败: {e}")

    def _cleanup_worker(self):
        """
        数据清理工作线程
        """
        self._log("数据清理工作线程已启动")

        # 启动时立即执行一次数据清理和统计保存
        self._perform_cleanup()
        self._save_current_stats()

        # 每小时执行一次数据清理和统计保存
        cleanup_interval = 3600  # 1小时

        while self._cleanup_running:
            try:
                time.sleep(cleanup_interval)
                if self._cleanup_running:
                    self._perform_cleanup()
                    self._save_current_stats()
            except Exception as e:
                self._log(f"数据清理过程中出现错误: {e}")

        self._log("数据清理工作线程已停止")

    def _save_current_stats(self):
        """
        保存当前统计数据到本地存储
        """
        try:
            # 获取当前统计数据
            stats = self._get_usage_stats()
            if stats and stats.get("date"):
                # 获取日期对象
                date_str = stats.get("date")
                date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")

                # 保存到本地存储
                if self.trend_storage.save_daily_stats(date_obj, stats):
                    self._log(f"已保存当前统计数据到本地存储: {date_str}")
                else:
                    self._log(f"保存当前统计数据失败: {date_str}")
        except Exception as e:
            self._log(f"保存当前统计数据过程中出现错误: {e}")

    def _perform_cleanup(self):
        """执行数据清理任务"""
        try:
            cleaned_count = self.trend_storage.cleanup_old_data()
            if cleaned_count > 0:
                self._log(f"数据清理完成，清理了 {cleaned_count} 个过期文件")
            else:
                self._log("数据清理完成，无需清理的数据")
        except Exception as e:
            self._log(f"执行数据清理任务失败: {e}")

    def _adjust_port_if_needed(self):
        """检查并调整端口"""
        # 首先尝试强制释放端口
        self._force_release_port(self.port)

        # 再次检查端口是否可用
        if not self._is_port_available(self.port):
            self.port = self._find_available_port()
            self._log(f"端口被占用，自动切换到端口: {self.port}")

    def _start_server_thread(self):
        """启动服务器线程"""

        def run_server():
            try:
                self._server_running = True
                self._start_time = time.time()
                from werkzeug.serving import make_server

                self._server_instance = make_server(self.host, self.port, self.app)
                self._log(f"Web服务器启动成功: http://{self.host}:{self.port}")
                self._server_instance.serve_forever()
            except Exception as e:
                self._handle_server_thread_error(e)

        self._server_thread = threading.Thread(target=run_server, daemon=False)
        self._server_thread.start()

    def _handle_server_thread_error(self, error):
        """处理服务器线程错误"""
        self._server_running = False
        error_msg = f"Web服务器运行失败: {str(error)}"
        self._last_error = error_msg
        if self.plugin:
            self.plugin._log_error(error_msg)
        else:
            print(error_msg)

    def _wait_for_server_start(self):
        """等待服务器启动并检查状态"""
        for _ in range(10):  # 最多等待5秒
            time.sleep(0.5)
            if self.is_running():
                self._log(f"Web服务器启动完成，状态: {self.get_status()}")
                return True

        # 启动超时
        self._handle_start_timeout()
        return False

    def _handle_start_timeout(self):
        """处理启动超时"""
        error_msg = "Web服务器启动超时"
        self._last_error = error_msg
        if self.plugin:
            self.plugin._log_error(error_msg)
        else:
            print(error_msg)

    def _handle_start_async_error(self, error):
        """处理异步启动错误"""
        error_msg = f"Web服务器启动失败: {str(error)}"
        self._last_error = error_msg
        if self.plugin:
            self.plugin._log_error(error_msg)
        else:
            print(error_msg)

    def get_status(self):
        """
        获取Web服务器状态信息

        返回：
            dict: 包含服务器状态信息的字典
        """
        return {
            "running": self._server_running,
            "thread_alive": self._server_thread and self._server_thread.is_alive()
            if self._server_thread
            else False,
            "port": self.port,
            "host": self.host,
            "start_time": self._start_time,
            "last_error": self._last_error,
            "instance_exists": self._server_instance is not None,
        }

    def is_running(self):
        """
        检查Web服务器是否正在运行

        返回：
            bool: 服务器是否正在运行
        """
        status = self.get_status()
        return status["running"] and status["thread_alive"]

    def stop(self):
        """
        停止Web服务器

        停止Flask应用并等待服务器线程结束。

        返回：
            bool: 停止成功返回True，失败返回False
        """
        try:
            self._log("开始停止Web服务器...")

            # 记录停止前的状态
            previous_status = self.get_status()
            self._log(f"停止前服务器状态: {previous_status}")

            # 设置停止标志
            self._server_running = False

            # 停止数据清理线程
            self._stop_cleanup_thread()

            # 执行停止流程
            self._stop_server_instance()
            self._wait_for_thread_termination()
            self._release_port()
            self._cleanup_resources()

            self._log("Web服务器已停止")
            return True

        except Exception as e:
            self._handle_stop_error(e)
            return False

    def _stop_cleanup_thread(self):
        """停止数据清理线程"""
        if not self._cleanup_thread or not self._cleanup_thread.is_alive():
            return

        self._log("正在停止数据清理线程...")
        self._cleanup_running = False

        # 等待线程结束
        self._cleanup_thread.join(timeout=5)

        if self._cleanup_thread.is_alive():
            self._log("警告: 数据清理线程未能在超时时间内结束")
        else:
            self._log("数据清理线程已停止")

    def _stop_server_instance(self):
        """
        优雅停止服务器实例

        负责关闭服务器实例，处理可能的异常情况。
        """
        if not self._server_instance:
            return

        self._log("正在关闭服务器实例...")
        try:
            self._server_instance.shutdown()
            self._log("服务器实例已关闭")
        except Exception as e:
            self._log(f"关闭服务器实例时出现异常: {e}")

    def _wait_for_thread_termination(self):
        """
        等待服务器线程结束

        负责等待线程正常结束，处理超时情况。
        """
        if not self._server_thread or not self._server_thread.is_alive():
            return

        self._log("正在等待服务器线程结束...")
        self._server_thread.join(timeout=10)  # 超时时间10秒

        if self._server_thread.is_alive():
            self._log("警告: 服务器线程未能在超时时间内结束")
        else:
            self._log("服务器线程已结束")

    def _release_port(self):
        """
        强制释放端口

        负责释放被占用的端口资源。
        """
        try:
            self._force_release_port(self.port)
        except Exception as e:
            self._log(f"释放端口时出现异常: {e}")

    def _cleanup_resources(self):
        """
        清理资源

        负责清理所有相关资源，重置状态。
        """
        self._server_instance = None
        self._server_thread = None
        self._start_time = None

    def _handle_stop_error(self, error):
        """
        处理停止过程中的错误

        负责记录错误信息并通知相关组件。

        参数：
            error (Exception): 发生的异常
        """
        error_msg = f"停止Web服务器失败: {str(error)}"
        self._last_error = error_msg
        if self.plugin:
            self.plugin._log_error(error_msg)
        else:
            print(error_msg)


if __name__ == "__main__":
    # 测试用
    server = WebServer(None)
    server.start()
