"""
Web服务器管理模块

负责Web服务器的初始化、启动、停止和状态管理。
"""


class WebManager:
    """Web服务器管理类"""

    def __init__(self, plugin):
        """
        初始化WebManager

        Args:
            plugin: 插件实例引用
        """
        self.plugin = plugin
        self.logger = plugin.logger
        self.config = plugin.config
        self.web_server = None

    def init_web_server(self):
        """
        初始化Web服务器

        创建并启动Web服务器实例，提供状态管理和错误处理。

        返回：
            bool: 初始化成功返回True，失败返回False
        """
        # 从主插件获取WebServer类
        WebServer = self.plugin.__class__.__dict__.get("_web_server_class")
        if WebServer is None:
            # 尝试从模块导入
            try:
                from web_server import WebServer as _WebServer
                WebServer = _WebServer
            except ImportError:
                self.logger.log_warning("Web服务器模块不可用，跳过Web服务器初始化")
                return False

        try:
            # 检查Web服务器是否已经在运行
            if self.is_web_server_running():
                self.logger.log_info("Web服务器已经在运行中")
                return True

            # 获取Web服务器配置并创建实例
            self.web_server = self.create_web_server_instance(WebServer)

            # 启动Web服务器
            success = self.start_web_server()

            if success:
                self.handle_web_server_start_success()
            else:
                self.handle_web_server_start_failure()

            return success

        except Exception as e:
            self.handle_web_server_init_error(e)
            return False

    def create_web_server_instance(self, WebServer):
        """
        创建Web服务器实例

        Args:
            WebServer: WebServer类

        返回：
            WebServer实例
        """
        web_config = self.config.get("web_server", {})
        host = web_config.get("host", "127.0.0.1")
        port = web_config.get("port", 10245)
        domain = web_config.get("domain", "")

        return WebServer(self.plugin, host=host, port=port, domain=domain)

    def start_web_server(self):
        """
        启动Web服务器

        返回：
            bool: 启动成功返回True，失败返回False
        """
        return self.web_server.start_async()

    def handle_web_server_start_success(self):
        """处理Web服务器启动成功的情况"""
        # 更新线程引用
        self.plugin.web_server_thread = self.web_server._server_thread

        # 记录访问地址
        self.log_web_server_access_url()

        # 记录服务器状态
        self.logger.log_info("Web服务器状态: {}", self.get_web_server_status())

    def log_web_server_access_url(self):
        """记录Web服务器访问地址"""
        web_config = self.config.get("web_server", {})
        domain = web_config.get("domain", "")

        if domain:
            access_url = self.web_server.get_access_url()
            self.logger.log_info("Web管理界面已启动，访问地址: {}", access_url)
        else:
            actual_port = self.web_server.port
            host = web_config.get("host", "127.0.0.1")
            self.logger.log_info(
                "Web管理界面已启动，访问地址: http://{}:{}", host, actual_port
            )

    def handle_web_server_start_failure(self):
        """处理Web服务器启动失败的情况"""
        error_msg = "Web服务器启动失败"
        if self.web_server._last_error:
            error_msg += f": {self.web_server._last_error}"
        self.logger.log_error(error_msg)
        self.web_server = None

    def handle_web_server_init_error(self, error):
        """
        处理Web服务器初始化错误

        Args:
            error: 异常对象
        """
        error_msg = f"Web服务器初始化失败: {str(error)}"
        self.logger.log_error(error_msg)
        self.web_server = None

    def is_web_server_running(self):
        """
        检查Web服务器是否正在运行

        返回：
            bool: Web服务器是否正在运行
        """
        if hasattr(self.plugin, "web_server") and self.plugin.web_server:
            return self.plugin.web_server.is_running()
        return False

    def get_web_server_status(self):
        """
        获取Web服务器状态信息

        返回：
            dict: Web服务器状态信息字典，如果未启动则返回None
        """
        if hasattr(self.plugin, "web_server") and self.plugin.web_server:
            return self.plugin.web_server.get_status()
        return None

    def terminate_web_server(self):
        """
        停止Web服务器

        返回：
            bool: 停止成功返回True，失败返回False
        """
        if not self.is_web_server_running():
            self.logger.log_info("Web服务器未运行，无需停止")
            return True

        try:
            self.logger.log_info("正在停止Web服务器...")

            # 记录停止前的状态
            self.get_web_server_status()

            # 停止Web服务器
            success = self.web_server.stop()

            if success:
                self.logger.log_info("Web服务器已停止")
                # 清理引用
                self.web_server = None
                self.plugin.web_server = None
                self.plugin.web_server_thread = None
                return True
            else:
                self.logger.log_warning("Web服务器停止失败")
                return False

        except Exception as e:
            error_msg = f"停止Web服务器失败: {str(e)}"
            self.logger.log_error(error_msg)
            return False
