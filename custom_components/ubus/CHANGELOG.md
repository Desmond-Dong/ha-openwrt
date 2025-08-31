# OpenWrt Monitor 更新日志

## v0.0.1

### 功能特性
- 重新设计为纯Ubus API集成
- 移除LuCI依赖
- 基本系统监控功能
- Ubus API支持

## 技术说明

### API策略
- **主要数据源**: Ubus API（32个接口）
- **协议支持**: HTTPS和HTTP自动切换
- **证书处理**: 忽略SSL证书错误
- **连接重试**: 自动重试失败的连接

### 数据处理
- **单位转换**: 字节→MB，负载→百分比
- **并行调用**: 同时调用32个API
- **错误处理**: 优雅处理API失败
- **数据缓存**: 智能缓存机制

### 兼容性
- **推荐版本**: OpenWrt 24.10+
- **Home Assistant**: 2025.8.0+
- **网络协议**: HTTP/HTTPS
- **认证方式**: 用户名/密码

### OpenWrt 24.10+ 新接口支持
- `system.led` - LED状态监控
- `system.watchdog` - 看门狗监控
- `system.sysupgrade` - 系统升级检查
- `system.upgrade` - 升级状态
- `system.monitor` - 系统监控
- `system.stats` - 系统统计
- `network.dump` - 网络配置转储
- `network.reload` - 网络重载状态
- `firewall.dump` - 防火墙规则转储
- `dhcp.leases` - DHCP租约信息
- `service.running` - 运行中服务
- 更多高级网络和系统接口
