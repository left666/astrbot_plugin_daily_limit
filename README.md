# AstrBot 日调用限制插件(重构版)

<div align="center">

![Version](https://img.shields.io/badge/版本-v2.8.9-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-3.5.1%2B-green)
![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)
![License](https://img.shields.io/badge/License-MIT-orange)
![Status](https://img.shields.io/badge/Web功能-正式发布-green)
![Bug](https://img.shields.io/badge/已知Bug-无-green)
![Trends](https://img.shields.io/badge/趋势分析-已集成-green)

![GitHub Stars](https://img.shields.io/github/stars/Sakura520222/astrbot_plugin_DailyLimit?style=for-the-badge&logo=github&label=Stars&color=yellow)
![GitHub Forks](https://img.shields.io/github/forks/Sakura520222/astrbot_plugin_DailyLimit?style=for-the-badge&logo=github&label=Forks&color=blue)
![GitHub Issues](https://img.shields.io/github/issues/Sakura520222/astrbot_plugin_DailyLimit?style=for-the-badge&logo=github&label=Issues&color=green)

![GitHub Last Commit](https://img.shields.io/github/last-commit/Sakura520222/astrbot_plugin_DailyLimit?style=for-the-badge&logo=git&label=最后提交)
![GitHub Release](https://img.shields.io/github/v/release/Sakura520222/astrbot_plugin_DailyLimit?style=for-the-badge&logo=github&label=最新版本)

---

**智能管理AI资源使用，防止滥用，提升用户体验**

</div>


> ✅ **重要提示：Web管理界面功能已正式发布**
> 
> 请注意，自v2.5.1版本起，Web管理界面功能已正式发布并稳定运行。我们已经解决了之前版本中存在的bug，并对系统进行了全面优化和测试，确保在生产环境中的稳定性和可靠性。

> ⚠️ **重要提醒：
> 本项目为维护重构版，原项目地址：https://github.com/left666/astrbot_plugin_daily_limit

## 简介

AstrBot 日调用限制插件是专为AstrBot设计的AI资源管理工具，通过智能的每日调用限制机制，有效防止大模型API滥用，确保AI服务的稳定性和公平性。

## 版本更新

### v2.8.9（2026.04.08）
#### Bug修复与文档更新
- **修正skip_patterns配置更新逻辑** - 修复Web管理界面中skip_patterns配置保存失败的问题
- **更新插件作者信息** - 更新metadata中的作者信息

### v2.8.8（2026.03.26 - 2026.04.01）
#### 核心架构重构
##### 模块化架构重构（五阶段）
- **第一阶段** - 拆分日志模块（logger）和Redis客户端（redis_client）到core目录
- **第二阶段** - 拆分配置管理（config_manager）和限制逻辑（limiter）到core目录
- **第三阶段** - 拆分使用记录统计（usage_tracker、stats_analyzer）和安全检测（security）到core目录
- **第四阶段** - 拆分消息构建器（message_builder）和版本检查（version_checker）到core目录
- **第五阶段** - 拆分高级辅助模块（help_manager、security_handler、messages_handler、time_period_manager、web_manager）到core目录

##### 新增模块
- **config_loader** - 独立配置加载模块，优化配置初始化流程
- **redis_keys** - Redis键名管理模块，统一键名规范

##### WebUI重构
- **重构WebUI界面** - 优化Web管理界面布局和交互体验

##### 修复问题
- **修复limit help命令装饰器问题** - 修复命令缺少装饰器导致的注册失败
- **修复核心模块导入问题** - 使用importlib从特定路径加载核心模块，解决模块级导入依赖
- **修复异步方法兼容性** - 将_build_basic_management_help改为异步方法

### v2.8.7（2026.03.26）
#### 请求处理逻辑优化
- **优化豁免用户检查顺序** - 调整豁免用户检查顺序，提升请求处理效率
- **移除不必要的 stop_event 调用** - 移除请求处理中的 stop_event 调用，简化代码逻辑

### v2.8.6（2026.01.06）
#### 指令冲突问题修复
##### 修复时间段限制指令冲突
- **修复指令注册方式** - 将时间段限制相关指令的注册方式从两个参数改为单个完整字符串，解决了指令冲突问题
- **解决别名解析错误** - 修复了add等后缀被识别为"别名"，且每个字母被拆开单独视为一个别名的问题
- **确保重启后保持正确** - 修复了手动改正后重启插件，指令名会重新加载成错误形式的问题

[更新日志](./CHANGELOG.md)

---

## 核心特性

### 智能限制系统
- 多级权限管理：用户、群组、豁免用户三级权限体系
- 时间段限制：支持按时间段设置不同的调用限制
- 优先级规则：豁免用户 > 时间段限制 > 用户限制 > 群组限制 > 默认限制

### 群组协作模式
- 共享模式：群组成员共享使用次数（默认）
- 独立模式：群组内每个成员独立计数（v2.2重加）
- 智能切换：自动识别消息类型，无缝切换计数模式

### 数据监控分析
- 实时监控：使用统计、排行榜和状态监控
- 使用记录：详细记录每次调用，支持历史查询
- 多维度分析：用户、群组、全局等多维度统计分析

### 灵活管理
- 重置机制：支持用户、群组或全部记录的重置
- 配置管理：灵活的配置系统，支持个性化设置
- Redis支持：基于Redis的高性能数据存储

### 忽略模式 (v2.4+)
- 智能消息过滤：支持自定义忽略的消息前缀
- 动态配置：支持通过配置文件或管理员命令动态管理忽略模式
- 向后兼容：默认保持与原有硬编码逻辑的兼容性

### 密码保护 (v2.5.0+)
- 安全访问控制：Web管理界面支持密码验证，防止未授权访问
- 会话管理：安全的登录状态保持机制
- 灵活配置：支持自定义密码或禁用密码验证
- 精美界面：樱花主题登录页面，支持移动端适配

### 版本检查功能 (v2.7.0+)
- 自动更新检测：定时检查插件新版本，及时获取最新功能
- 智能通知：检测到新版本时自动通知管理员用户
- 灵活配置：可自定义检查间隔、管理员列表和通知消息模板
- 手动检查命令：支持管理员手动触发版本检查

### 防刷功能增强 (v2.7.1+)
- 智能防刷机制：增强防刷检测功能，支持快速请求检测和连续请求异常检测
- 自动限制机制：检测到异常行为时自动限制用户，防止恶意刷屏
- 管理员通知：防刷限制触发时自动向管理员发送通知，便于及时处理
- 限制时长配置：支持自定义防刷限制时长，灵活应对不同场景
- 防重复通知：新增防重复通知功能，避免同一用户重复触发限制时重复发送提醒消息

### 趋势分析功能 (v2.7.3+)
- 多周期趋势分析：支持日、周、月三种时间维度的使用趋势分析
- 多指标统计：提供用户活跃度、使用频率、使用量分布等多维度指标
- Web界面集成：在Web管理界面中集成趋势分析图表，支持Chart.js可视化
- API接口支持：提供`/api/trends`接口，支持不同时间周期的趋势数据查询
- 认证机制：趋势分析API受密码保护，确保数据安全访问
- 错误处理：完善的参数验证和异常处理机制

---

## 优先级规则

限制规则的优先级从高到低依次为：

1. 时间段限制 - 优先级最高
2. 豁免用户 - 完全不受限制
3. 用户特定限制 - 针对单个用户
4. 群组特定限制 - 针对整个群组
5. 默认限制 - 全局默认设置

---

## 快速开始

### 系统要求
- AstrBot版本: v3.5.1+
- Python版本: 3.10+
- Redis服务器: 必须配置

### 安装步骤

1. **安装Redis依赖**
   ```bash
   pip install redis>=4.5.0
   ```

2. **配置Redis服务器**
   - 确保Redis服务正常运行
   - 记录Redis连接信息（主机、端口、密码等）

3. **安装插件**
   - 将插件文件放置到AstrBot插件目录
   - 重启AstrBot服务

4. **验证安装**
   - 给机器人发送 `/limit_status` 命令
   - 如果收到回复，说明插件安装成功

### 基础配置

创建配置文件 `astrbot_plugin_dailylimit_config.json`：

```json
{
  "redis": {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": ""
  },
  "limits": {
    "default_daily_limit": 20,
    "exempt_users": [],
    "group_limits": "",
    "user_limits": "",
    "group_mode_settings": "",
    "time_period_limits": ""
  },
  "web_server": {
    "host": "127.0.0.1",
    "port": 10245,
    "debug": true,
    "domain": "",
    "password": "limit"
  }
}
```

---

## 详细配置

### Redis服务器配置

Redis是插件的数据存储后端，必须正确配置才能正常运行。

```json
"redis": {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": ""
}
```

**配置说明：**
- host: Redis服务器地址（默认：localhost）
- port: Redis服务器端口（默认：6379）
- db: Redis数据库编号（默认：0）
- password: Redis访问密码（默认：空）

### 限制规则配置

#### 默认限制设置
- `default_daily_limit`: 默认每日调用次数（默认：20次）

#### 豁免用户列表
- `exempt_users`: 不受限制的用户ID列表（JSON数组格式）

### 文本格式配置（v2.6.5+）

**自v2.6.5版本起，以下配置项使用文本格式，每行一个配置项：**

#### 用户限制配置
**格式：** `用户ID:限制次数`
```text
123456:10
789012:20
345678:15
```

#### 群组限制配置
**格式：** `群组ID:限制次数`
```text
100001:15
100002:30
100003:25
```

#### 群组模式配置
**格式：** `群组ID:模式类型`
**模式类型：**
- `shared` - 共享模式（群组成员共享使用次数）
- `individual` - 独立模式（群组内每个成员独立计数）

```text
100001:shared
100002:individual
100003:shared
```

#### 时间段限制配置
**格式：** `开始时间-结束时间:限制次数:是否启用`
**时间格式：** HH:MM（24小时制）
**启用状态：** `true`（启用）或 `false`（禁用）

```text
09:00-18:00:10:true    # 工作日时段限制10次
19:00-22:00:5:true     # 晚间时段限制5次
08:00-17:00:15:false   # 配置但未启用
```

**文本格式配置注意事项：**
- 每行一个配置项，支持空行和注释（以#开头）
- 配置项顺序不影响优先级
- 在Web管理界面中可以直观地编辑这些配置

### 高级功能配置

#### 忽略模式配置 (v2.4+)
```json
"skip_patterns": ["#", "*"]
```
**功能：** 定义需要忽略的消息前缀
**默认值：** `"#", "*"`（保持向后兼容）
**示例：** 设置`"!", "/"`可忽略以!或/开头的消息

#### 重置时间配置 (v2.6.7+)
```json
"daily_reset_time": "00:00"
```
**功能：** 自定义每日使用次数重置时间
**默认值：** `"00:00"`（凌晨0点）
**时间格式：** HH:MM（24小时制），如 `"06:00"`、`"12:30"`、`"23:59"`
**验证机制：** 自动验证时间格式有效性，无效格式将使用默认值

#### Web服务器配置 (v2.4.4+)
```json
"web_server": {
    "host": "127.0.0.1",
    "port": 10245,
    "debug": true,
    "domain": "",
    "password": "limit"
}
```
**配置说明：**
- host: Web服务器绑定的主机地址（默认：127.0.0.1）
- port: Web服务器端口（默认：10245）
- debug: 调试模式开关（默认：true）
- domain: 自定义域名（用于生成访问链接）
- password: Web管理界面访问密码（默认："limit"，留空表示无需密码）

#### 版本检查配置 (v2.7.0+)
```json
"version_check": {
    "enabled": true,
    "check_interval": 60,
    "admin_users": [123456789],
    "repeat_notification": false,
    "notification_message": "检测到新版本可用！\n当前版本：{current_version}\n最新版本：{new_version}\n更新内容：{update_content}\n下载地址：{download_url}"
}
```
**配置说明：**
- enabled: 版本检查功能开关（默认：true）
- check_interval: 检查间隔（分钟，默认：60分钟）
- admin_users: 管理员用户ID列表，用于接收版本更新通知
- repeat_notification: 是否对同一版本重复发送通知（默认：false）
- notification_message: 通知消息模板，支持占位符：
  - `{current_version}` - 当前版本号
  - `{new_version}` - 最新版本号
  - `{update_content}` - 更新内容说明
  - `{download_url}` - 下载地址

#### 防刷功能配置 (v2.7.1+)
```json
"security": {
    "anti_abuse_enabled": false,
    "fast_request_threshold": 5,
    "fast_request_window": 10,
    "consecutive_request_threshold": 10,
    "consecutive_request_window": 60,
    "auto_block_duration": 300,
    "admin_notification_enabled": true,
    "admin_users": [123456789],
    "block_notification_template": "检测到异常行为，您已被限制使用 {auto_block_duration} 秒",
    "notification_cooldown": 300
}
```
**配置说明：**
- anti_abuse_enabled: 防刷功能开关（默认：false）
- fast_request_threshold: 快速请求阈值（默认：5次）
- fast_request_window: 快速请求检测窗口（秒，默认：10秒）
- consecutive_request_threshold: 连续请求阈值（默认：10次）
- consecutive_request_window: 连续请求检测窗口（秒，默认：60秒）
- auto_block_duration: 自动限制时长（秒，默认：300秒）
- admin_notification_enabled: 管理员通知开关（默认：true）
- admin_users: 管理员用户ID列表，用于接收防刷通知
- block_notification_template: 用户限制通知模板，支持占位符：
  - `{duration}` - 限制时长（秒）
- notification_cooldown: 通知冷却时间（秒，默认：300秒），同一用户重复触发限制时，在此时间内不会重复发送通知

---

## 使用指南

### 用户命令

| 命令            | 功能             | 示例            |
| --------------- | ---------------- | --------------- |
| `/limit_status` | 查看个人使用情况 | `/limit_status` |
| `/限制帮助`     | 显示所有可用命令 | `/限制帮助`     |

### 管理员命令

#### 基础配置管理
| 命令                         | 功能         | 示例                   |
| ---------------------------- | ------------ | ---------------------- |
| `/limit help`                | 显示详细帮助 | `/limit help`          |
| `/limit set <用户ID> <次数>` | 设置用户限制 | `/limit set 123456 50` |
| `/limit setgroup <次数>`     | 设置群组限制 | `/limit setgroup 30`   |
| `/limit setmode <shared      | individual>` | 设置群组模式           | `/limit setmode shared` |
| `/limit getmode`             | 查看群组模式 | `/limit getmode`       |

#### 豁免用户管理
| 命令                       | 功能         | 示例                     |
| -------------------------- | ------------ | ------------------------ |
| `/limit exempt <用户ID>`   | 添加豁免用户 | `/limit exempt 123456`   |
| `/limit unexempt <用户ID>` | 移除豁免用户 | `/limit unexempt 123456` |

#### 时间段限制管理
| 命令                                         | 功能           | 示例                                   |
| -------------------------------------------- | -------------- | -------------------------------------- |
| `/limit timeperiod list`                     | 列出时间段限制 | `/limit timeperiod list`               |
| `/limit timeperiod add <开始> <结束> <次数>` | 添加时间段     | `/limit timeperiod add 09:00 18:00 10` |
| `/limit timeperiod remove <索引>`            | 删除时间段     | `/limit timeperiod remove 1`           |
| `/limit timeperiod enable <索引>`            | 启用时间段     | `/limit timeperiod enable 1`           |
| `/limit timeperiod disable <索引>`           | 禁用时间段     | `/limit timeperiod disable 1`          |

#### 查询功能
| 命令                             | 功能                    | 示例                          |
| -------------------------------- | ----------------------- | ----------------------------- |
| `/limit list_user`               | 列出用户限制            | `/limit list_user`            |
| `/limit list_group`              | 列出群组限制            | `/limit list_group`           |
| `/limit stats`                   | 查看今日统计            | `/limit stats`                |
| `/limit history [用户ID] [天数]` | 查询使用历史            | `/limit history 123456 7`     |
| `/limit analytics [日期]`        | 多维度分析              | `/limit analytics 2025-01-23` |
| `/limit top [数量]`              | 显示排行榜              | `/limit top 5`                |
| `/limit status`                  | 查看插件状态            | `/limit status`               |
| `/limit domain`                  | 查看Web管理界面域名配置 | `/limit domain`               |

#### 重置功能
| 命令                          | 功能         | 示例                        |
| ----------------------------- | ------------ | --------------------------- |
| `/limit reset all`            | 重置所有记录 | `/limit reset all`          |
| `/limit reset <用户ID>`       | 重置特定用户 | `/limit reset 123456`       |
| `/limit reset group <群组ID>` | 重置特定群组 | `/limit reset group 789012` |

#### 重置时间配置 (v2.6.7+)
| 命令                          | 功能                    | 示例                         |
| ----------------------------- | ----------------------- | ---------------------------- |
| `/limit resettime get`        | 查看当前重置时间配置    | `/limit resettime get`       |
| `/limit resettime set <时间>` | 设置自定义重置时间      | `/limit resettime set 06:00` |
| `/limit resettime reset`      | 重置为默认时间（00:00） | `/limit resettime reset`     |

#### 忽略模式管理 (v2.4+)
| 命令                                 | 功能             | 示例                            |
| ------------------------------------ | ---------------- | ------------------------------- |
| `/limit skip_patterns`               | 查看当前忽略模式 | `/limit skip_patterns`          |
| `/limit skip_patterns add <模式>`    | 添加忽略模式     | `/limit skip_patterns add !`    |
| `/limit skip_patterns remove <模式>` | 移除忽略模式     | `/limit skip_patterns remove #` |
| `/limit skip_patterns reset`         | 重置为默认模式   | `/limit skip_patterns reset`    |

#### 消息自定义管理 (v2.6.0+)
| 命令                                       | 功能                       | 示例                                                |
| ------------------------------------------ | -------------------------- | --------------------------------------------------- |
| `/limit messages list`                     | 查看所有可自定义的消息类型 | `/limit messages list`                              |
| `/limit messages set <类型> <消息>`        | 设置特定类型的自定义消息   | `/limit messages set private 今日次数已用完`        |
| `/limit messages reset <类型>`             | 重置指定类型的消息为默认   | `/limit messages reset private`                     |
| `/limit messages reset_all`                | 重置所有消息为默认         | `/limit messages reset_all`                         |
| `/limit custom_messages get`               | 查看当前自定义消息配置     | `/limit custom_messages get`                        |
| `/limit custom_messages set <类型> <消息>` | 设置特定类型的自定义消息   | `/limit custom_messages set private 今日次数已用完` |
| `/limit custom_messages reset`             | 重置为默认消息             | `/limit custom_messages reset`                      |

#### 版本检查管理 (v2.7.0+)
| 命令                 | 功能                 | 示例                 |
| -------------------- | -------------------- | -------------------- |
| `/limit checkupdate` | 手动检查版本更新     | `/limit checkupdate` |
| `/limit version`     | 查看当前插件版本信息 | `/limit version`     |

#### 防刷功能管理 (v2.7.1+)
| 命令                               | 功能                   | 示例                             |
| ---------------------------------- | ---------------------- | -------------------------------- |
| `/limit security status`           | 查看防刷功能状态       | `/limit security status`         |
| `/limit security enable`           | 启用防刷功能           | `/limit security enable`         |
| `/limit security disable`          | 禁用防刷功能           | `/limit security disable`        |
| `/limit security config`           | 查看防刷配置详情       | `/limit security config`         |
| `/limit security unblock <用户ID>` | 解除用户限制           | `/limit security unblock 123456` |
| `/limit security blocklist`        | 查看当前被限制用户列表 | `/limit security blocklist`      |

#### 趋势分析功能 (v2.7.3+)
| 命令                       | 功能                            | 示例                     |
| -------------------------- | ------------------------------- | ------------------------ |
| `/limit trends`            | 查看趋势分析Web管理界面访问地址 | `/limit trends`          |
| `/limit trends_api <周期>` | 获取趋势分析API数据             | `/limit trends_api week` |

**趋势分析功能说明：**
- Web界面访问：通过`/limit trends`命令获取Web管理界面地址，登录后可查看趋势分析图表
- API数据获取：通过`/limit trends_api <周期>`命令直接获取趋势分析数据，支持`day`、`week`、`month`三种周期
- 多维度分析：提供用户活跃度、使用频率、使用量分布等多维度趋势数据

## 贡献指南

我们欢迎社区贡献！请遵循以下指南：

### 如何贡献
1. Fork 仓库 - fork 这个仓库到您的账户
2. 创建分支 - 为功能或修复创建新分支
3. 提交更改 - 提交清晰的提交信息
4. 创建 Pull Request - 提交PR并描述更改

### 贡献规范
- 确保代码符合项目编码风格
- 添加适当的测试用例
- 更新相关文档
- 确保所有测试通过

## 技术支持

### 问题反馈
如遇到任何问题，请通过以下方式联系：
- Telegram: [@TamakiSakura520](https://t.me/TamakiSakura520)
- Issues: [GitHub Issues](https://github.com/Sakura520222/astrbot_plugin_DailyLimit/issues)
- QQ群: 922321912 (可以反馈也可以来玩耍，不点Star不给进)

> **📌 维护说明**
>
> 原作者 [left666](https://github.com/left666) 已不再维护此项目。
> 目前由 [Sakura520222](https://github.com/Sakura520222) 接手维护，所有更新和发布均在 [Fork 仓库](https://github.com/Sakura520222/astrbot_plugin_DailyLimit) 进行。
>
> 如需提交 Issue 或 PR，请前往新仓库：**https://github.com/Sakura520222/astrbot_plugin_DailyLimit**

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

<div align="center">

**如果这个插件对你有帮助，请给个Star支持一下！**

</div>

## 贡献者

感谢所有为这个项目做出贡献的开发者！

### 项目作者
- [left666](https://github.com/left666)

### 主要贡献者
- [Sakura520222](https://github.com/Sakura520222)

*感谢所有参与测试、反馈和贡献的社区成员！*

## 常见问题与故障排除

### 常见问题

#### Q: 插件安装后无法正常工作怎么办？
A: 请检查以下几点：
- 确保Redis服务正常运行
- 检查配置文件中的Redis连接信息是否正确
- 确保AstrBot版本符合要求（v3.5.1+）
- 查看AstrBot日志，检查是否有相关错误信息

#### Q: 如何查看插件的运行状态？
A: 管理员可以发送 `/limit status` 命令查看插件的运行状态，包括Redis连接状态、当前配置等信息。

#### Q: 如何修改Web管理界面的密码？
A: 可以通过修改配置文件中的 `web_server.password` 字段来更改Web管理界面的密码，修改后需要重启插件或AstrBot。

#### Q: 为什么我的自定义重置时间没有生效？
A: 请检查时间格式是否正确（HH:MM），插件会自动验证时间格式的有效性，无效格式将使用默认值（00:00）。

#### Q: 如何查看用户的使用历史？
A: 管理员可以发送 `/limit history <用户ID> <天数>` 命令查看指定用户在指定天数内的使用历史。

### 故障排除

#### 1. Redis连接失败
- 检查Redis服务是否正在运行
- 检查配置文件中的Redis连接信息（主机、端口、密码）是否正确
- 确保Redis服务器允许远程连接（如果Redis不在本地）
- 检查防火墙设置，确保Redis端口（默认6379）已开放

#### 2. Web管理界面无法访问
- 检查配置文件中的 `web_server.host` 和 `web_server.port` 配置是否正确
- 确保防火墙已开放Web服务器端口（默认10245）
- 检查AstrBot日志，查看是否有Web服务器启动失败的错误信息

#### 3. 调用限制不生效
- 检查用户是否在豁免用户列表中
- 检查是否有适用的时间段限制
- 检查用户限制和群组限制的配置是否正确
- 查看AstrBot日志，检查是否有相关错误信息

#### 4. 防刷功能不生效
- 检查配置文件中的 `security.anti_abuse_enabled` 是否设置为 `true`
- 检查防刷阈值和窗口配置是否合理
- 查看AstrBot日志，检查是否有防刷功能相关的错误信息

---

<div align="center">

**您的每一个Star都是对我们最大的支持！**

[![Star History Chart](https://api.star-history.com/svg?repos=Sakura520222/astrbot_plugin_DailyLimit&type=Date)](https://star-history.com/#Sakura520222/astrbot_plugin_DailyLimit&Date)

</div>