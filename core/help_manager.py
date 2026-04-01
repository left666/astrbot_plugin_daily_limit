"""
帮助管理模块

负责生成和管理插件的帮助文档，包括：
- 基础管理命令帮助
- 时间段限制帮助
- 重置时间管理帮助
- 忽略模式管理帮助
- 查询统计帮助
- 重置命令帮助
- 安全命令帮助
- 版本检查帮助
- 优先级规则帮助
- 使用模式说明帮助
- 功能特性帮助
- 使用提示帮助
- 版本信息帮助
"""


class HelpManager:
    """帮助管理类"""

    def __init__(self, plugin):
        """
        初始化帮助管理器

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.config = plugin.config

    def build_basic_management_help(self) -> str:
        """构建基础管理命令帮助信息"""
        return (
            "📋 基础管理命令：\n"
            "├── /limit help - 显示此帮助信息\n"
            "├── /limit set <用户ID> <次数> - 设置特定用户的每日限制次数\n"
            "│   示例：/limit set 123456 50 - 设置用户123456的每日限制为50次\n"
            "├── /limit setgroup <次数> - 设置当前群组的每日限制次数\n"
            "│   示例：/limit setgroup 30 - 设置当前群组的每日限制为30次\n"
            "├── /limit setmode <shared|individual> - 设置当前群组使用模式\n"
            "│   示例：/limit setmode shared - 设置为共享模式\n"
            "├── /limit getmode - 查看当前群组使用模式\n"
            "├── /limit exempt <用户ID> - 将用户添加到豁免列表（不受限制）\n"
            "│   示例：/limit exempt 123456 - 豁免用户123456\n"
            "├── /limit unexempt <用户ID> - 将用户从豁免列表移除\n"
            "│   示例：/limit unexempt 123456 - 取消用户123456的豁免\n"
            "├── /limit list_user - 列出所有用户特定限制\n"
            "└── /limit list_group - 列出所有群组特定限制\n"
        )

    def build_time_period_help(self) -> str:
        """构建时间段限制命令帮助信息"""
        return (
            "\n⏰ 时间段限制命令：\n"
            "├── /limit timeperiod list - 列出所有时间段限制配置\n"
            "├── /limit timeperiod add <开始时间> <结束时间> <限制次数> - 添加时间段限制\n"
            "│   示例：/limit timeperiod add 09:00 18:00 10 - 添加9:00-18:00时间段限制10次\n"
            "├── /limit timeperiod remove <索引> - 删除时间段限制\n"
            "│   示例：/limit timeperiod remove 1 - 删除第1个时间段限制\n"
            "├── /limit timeperiod enable <索引> - 启用时间段限制\n"
            "│   示例：/limit timeperiod enable 1 - 启用第1个时间段限制\n"
            "└── /limit timeperiod disable <索引> - 禁用时间段限制\n"
            "    示例：/limit timeperiod disable 1 - 禁用第1个时间段限制\n"
        )

    def build_reset_time_help(self) -> str:
        """构建重置时间管理命令帮助信息"""
        return (
            "\n🕐 重置时间管理命令：\n"
            "├── /limit resettime get - 查看当前重置时间\n"
            "├── /limit resettime set <时间> - 设置每日重置时间\n"
            "│   示例：/limit resettime set 06:00 - 设置为早上6点重置\n"
            "└── /limit resettime reset - 重置为默认时间（00:00）\n"
        )

    def build_skip_patterns_help(self) -> str:
        """构建忽略模式管理命令帮助信息"""
        return (
            "\n🔧 忽略模式管理命令：\n"
            "├── /limit skip_patterns list - 查看当前忽略模式\n"
            "├── /limit skip_patterns add <模式> - 添加忽略模式\n"
            "│   示例：/limit skip_patterns add ! - 添加!为忽略模式\n"
            "├── /limit skip_patterns remove <模式> - 移除忽略模式\n"
            "│   示例：/limit skip_patterns remove # - 移除#忽略模式\n"
            "└── /limit skip_patterns reset - 重置为默认模式\n"
            "    示例：/limit skip_patterns reset - 重置为默认模式[@所有人, #]\n"
        )

    def build_query_stats_help(self) -> str:
        """构建查询统计命令帮助信息"""
        return (
            "\n📊 查询统计命令：\n"
            "├── /limit stats - 查看今日使用统计信息\n"
            "├── /limit history [用户ID] [天数] - 查询使用历史记录\n"
            "│   示例：/limit history 123456 7 - 查询用户123456最近7天的使用记录\n"
            "├── /limit trends [周期] - 使用趋势分析（日/周/月）\n"
            "│   示例：/limit trends week - 查看最近4周的使用趋势\n"
            "├── /limit analytics [日期] - 多维度统计分析\n"
            "│   示例：/limit analytics 2025-01-23 - 分析2025年1月23日的使用数据\n"
            "├── /limit top [数量] - 查看使用次数排行榜\n"
            "│   示例：/limit top 10 - 查看今日使用次数前10名\n"
            "├── /limit status - 检查插件状态和健康状态\n"
            "└── /limit domain - 查看Web管理界面域名配置和访问地址\n"
        )

    def build_reset_commands_help(self) -> str:
        """构建重置命令帮助信息"""
        return (
            "\n🔄 重置命令：\n"
            "├── /limit reset all - 重置所有使用记录（包括个人和群组）\n"
            "├── /limit reset <用户ID> - 重置特定用户的使用次数\n"
            "│   示例：/limit reset 123456 - 重置用户123456的使用次数\n"
            "└── /limit reset group <群组ID> - 重置特定群组的使用次数\n"
            "    示例：/limit reset group 789012 - 重置群组789012的使用次数\n"
        )

    def build_security_commands_help(self) -> str:
        """构建安全命令帮助信息"""
        return (
            "\n🛡️ 安全命令：\n"
            "├── /limit security status - 查看防刷机制状态和统计信息\n"
            "├── /limit security enable - 启用防刷机制\n"
            "├── /limit security disable - 禁用防刷机制\n"
            "├── /limit security config - 查看当前安全配置\n"
            "├── /limit security blocklist - 查看当前被限制的用户列表\n"
            "├── /limit security unblock <用户ID> - 解除对用户的限制\n"
            "│   示例：/limit security unblock 123456 - 解除用户123456的限制\n"
            "└── /limit security stats <用户ID> - 查看用户的异常行为统计\n"
            "    示例：/limit security stats 123456 - 查看用户123456的异常行为统计\n"
        )

    def build_version_check_help(self) -> str:
        """构建版本检查命令帮助信息"""
        return (
            "\n🔍 版本检查命令：\n"
            "├── /limit checkupdate - 手动检查版本更新\n"
            "│   示例：/limit checkupdate - 立即检查是否有新版本\n"
            "└── /limit version - 查看当前插件版本信息\n"
            "    示例：/limit version - 显示当前版本和检查状态\n"
        )

    def build_priority_rules_help(self) -> str:
        """构建优先级规则帮助信息"""
        return (
            "\n🎯 优先级规则（从高到低）：\n"
            "1️⃣ ⏰ 时间段限制 - 优先级最高（特定时间段内的限制）\n"
            "2️⃣ 🏆 豁免用户 - 完全不受限制（白名单用户）\n"
            "3️⃣ 👤 用户特定限制 - 针对单个用户的个性化设置\n"
            "4️⃣ 👥 群组特定限制 - 针对整个群组的统一设置\n"
            "5️⃣ ⚙️ 默认限制 - 全局默认设置（兜底规则）\n"
        )

    def build_usage_modes_help(self) -> str:
        """构建使用模式说明帮助信息"""
        return (
            "\n📊 使用模式说明：\n"
            "• 🔄 共享模式：群组内所有成员共享使用次数（默认模式）\n"
            "   └── 适合小型团队协作，统一管理使用次数\n"
            "• 👤 独立模式：群组内每个成员有独立的使用次数\n"
            "   └── 适合大型团队，成员间互不影响\n"
        )

    def build_features_help(self) -> str:
        """构建功能特性帮助信息"""
        return (
            "\n💡 功能特性：\n"
            "✅ 智能限制系统：多级权限管理，支持用户、群组、豁免用户三级体系\n"
            "✅ 时间段限制：支持按时间段设置不同的调用限制（优先级最高）\n"
            "✅ 自定义重置时间：支持设置每日重置时间（默认00:00）\n"
            "✅ 群组协作模式：支持共享模式（群组共享次数）和独立模式（成员独立次数）\n"
            "✅ 数据监控分析：实时监控、使用统计、排行榜和状态监控\n"
            "✅ 使用趋势分析：支持日/周/月多维度使用趋势分析\n"
            "✅ 使用记录：详细记录每次调用，支持历史查询和统计分析\n"
            "✅ 自定义忽略模式：可配置需要忽略处理的消息前缀\n"
            "✅ 智能提醒：剩余次数提醒和使用状态监控\n"
        )

    def build_usage_tips_help(self) -> str:
        """构建使用提示帮助信息"""
        return (
            "\n📝 使用提示：\n"
            "• 所有命令都需要管理员权限才能使用\n"
            "• 时间段限制优先级最高，会覆盖其他限制规则\n"
            "• 豁免用户不受任何限制规则约束\n"
            "• 默认忽略模式：#、*（可自定义添加）\n"
            "• 重置时间设置后，所有用户和群组的使用次数将在指定时间重置\n"
        )

    def build_version_info_help(self) -> str:
        """构建版本信息帮助信息"""
        return (
            "\n📝 版本信息：v2.8.7 | 作者：left666 | 改进：Sakura520222\n"
            "═════════════════════════"
        )

    def build_full_help(self) -> str:
        """构建完整的帮助信息"""
        help_msg = "🚀 日调用限制插件 v2.8.7 - 管理员详细帮助\n"
        help_msg += "═════════════════════════\n\n"

        # 组合所有帮助信息
        help_msg += self.build_basic_management_help()
        help_msg += self.build_time_period_help()
        help_msg += self.build_reset_time_help()
        help_msg += self.build_skip_patterns_help()
        help_msg += self.build_query_stats_help()
        help_msg += self.build_reset_commands_help()
        help_msg += self.build_security_commands_help()
        help_msg += self.build_version_check_help()
        help_msg += self.build_priority_rules_help()
        help_msg += self.build_usage_modes_help()
        help_msg += self.build_features_help()
        help_msg += self.build_usage_tips_help()
        help_msg += self.build_version_info_help()

        return help_msg
