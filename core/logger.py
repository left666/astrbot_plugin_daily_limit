"""
日志和错误处理模块

提供统一的日志记录和错误处理机制。
"""


class Logger:
    """统一的日志和错误处理类"""

    def __init__(self, plugin):
        """
        初始化日志模块

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin

    def log(self, level: str, message: str, *args) -> None:
        """
        统一的日志记录方法

        Args:
            level: 日志级别 ('info', 'warning', 'error')
            message: 日志消息模板
            *args: 格式化参数
        """
        # 延迟导入，避免模块级导入问题
        from astrbot.api import logger

        log_func = getattr(logger, level, logger.info)
        if args:
            log_func(message.format(*args))
        else:
            log_func(message)

    def log_warning(self, message, *args):
        """警告日志记录"""
        self.log("warning", message, *args)

    def log_error(self, message, *args):
        """错误日志记录"""
        self.log("error", message, *args)

    def log_info(self, message, *args):
        """信息日志记录"""
        self.log("info", message, *args)

    def handle_error(
        self, error: Exception, context: str = "", user_message: str = None
    ) -> None:
        """
        统一的错误处理方法

        提供统一的错误处理机制，包括：
        - 错误日志记录
        - 错误上下文追踪
        - 详细错误信息记录（包含堆栈跟踪）

        参数：
            error: 异常对象
            context: 错误上下文描述
            user_message: 返回给用户的友好错误消息（可选）
        """
        error_context = f"{context}: " if context else ""
        self.log_error("{}发生错误: {}", error_context, str(error))

        # 记录详细的错误信息用于调试
        if hasattr(error, "__traceback__"):
            import traceback

            error_details = traceback.format_exc()
            self.log_error("{}详细错误信息:\n{}", error_context, error_details)

    def safe_execute(
        self, func, *args, context: str = "", default_return=None, **kwargs
    ):
        """
        安全执行函数，捕获异常并记录

        Args:
            func: 要执行的函数
            *args: 函数参数
            context: 执行上下文描述
            default_return: 异常时的默认返回值
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果或默认返回值
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.handle_error(e, context)
            return default_return
