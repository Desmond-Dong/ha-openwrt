#!/usr/bin/env python3
"""
OpenWrt Ubus API 调试工具 - 针对OpenWrt 24.10+优化
用于测试OpenWrt路由器的Ubus API可用性和数据结构
"""

import json
import asyncio
import aiohttp
import ssl
import sys
import argparse
from typing import Optional

class OpenWrtAPIDebugger:
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.session_id = None
        self._session = None

    async def __aenter__(self):
        # 创建SSL上下文，忽略自签名证书错误
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 创建连接器，支持HTTP和HTTPS
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self._session = aiohttp.ClientSession(connector=connector)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def _ubus_login(self, protocol):
        """尝试指定协议的Ubus登录"""
        try:
            url = f"{protocol}://{self.host}/ubus"
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "call",
                "params": [
                    "00000000000000000000000000000000",
                    "session",
                    "login",
                    {
                        "username": self.username,
                        "password": self.password
                    }
                ]
            }
            
            print(f"🔐 尝试 {protocol.upper()} Ubus登录: {url}")
            
            async with self._session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    print(f"❌ {protocol.upper()} Ubus登录失败，状态码: {resp.status}")
                    return False
                data = await resp.json()
                if "result" in data and len(data["result"]) > 1:
                    self.session_id = data["result"][1]["ubus_rpc_session"]
                    print(f"✅ {protocol.upper()} Ubus登录成功，Session ID: {self.session_id}")
                    return True
                else:
                    print(f"❌ {protocol.upper()} Ubus登录响应无效")
                    return False
        except Exception as e:
            print(f"❌ {protocol.upper()} Ubus登录异常: {e}")
            return False

    async def _login(self):
        """尝试登录，支持HTTPS/HTTP"""
        print(f"\n🔐 尝试登录OpenWrt: {self.host}")
        print("=" * 60)
        
        # 首先尝试HTTPS Ubus登录
        if await self._ubus_login("https"):
            return True
        
        # 如果HTTPS失败，尝试HTTP Ubus登录
        print("🔄 HTTPS Ubus登录失败，尝试HTTP Ubus登录...")
        if await self._ubus_login("http"):
            return True
        
        print("❌ 所有登录方法失败")
        return False

    async def _ubus_call(self, namespace, method, params=None):
        """调用OpenWrt Ubus API"""
        if not self.session_id:
            return None
        # Try HTTPS then HTTP, with optional retries per protocol
        protocols = ["https", "http"]
        timeout = getattr(self, "_call_timeout", 10)
        retries = getattr(self, "_call_retries", 1)

        for protocol in protocols:
            url = f"{protocol}://{self.host}/ubus"
            payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "call",
                "params": [
                    self.session_id,
                    namespace,
                    method,
                    params or {}
                ]
            }

            attempt = 0
            while attempt <= retries:
                try:
                    async with self._session.post(url, json=payload, timeout=timeout) as resp:
                        if resp.status != 200:
                            attempt += 1
                            continue
                        data = await resp.json()
                        if "result" in data and len(data["result"]) > 1:
                            return data["result"][1]
                        else:
                            attempt += 1
                            continue
                except Exception:
                    attempt += 1
                    await asyncio.sleep(0.1)
                    continue

        return None

    async def test_ubus_services(self):
        """测试Ubus服务列表"""
        print("\n🔧 可用Ubus服务列表:")
        print("-" * 40)
        
        try:
            services = await self._ubus_call("ubus", "list")
            if services:
                print("✅ 获取服务列表成功")
                if isinstance(services, dict) and "services" in services:
                    service_list = services["services"]
                    if isinstance(service_list, list):
                        print(f"📋 发现 {len(service_list)} 个服务:")
                        for service in service_list:
                            print(f"   • {service}")
                    else:
                        print(f"📋 服务列表格式: {type(service_list)}")
                        print(f"   内容: {service_list}")
                else:
                    print(f"📋 服务数据结构: {services}")
            else:
                print("❌ 无法获取服务列表")
        except Exception as e:
            print(f"❌ 测试服务列表时出错: {e}")

    async def test_key_apis(self):
        """测试关键API - 针对OpenWrt 24.10+优化"""
        print("\n🎯 开始测试关键 API 列表")
        print("=" * 60)

        # 定义要测试的API - OpenWrt 24.10+支持的接口
        test_apis = [
            # 系统信息
            ("system", "board", "系统板信息"),
            ("system", "info", "系统信息"),
            ("system", "processes", "系统进程"),
            ("system", "uptime", "系统运行时间"),
            ("system", "load", "系统负载"),
            ("system", "memory", "系统内存"),
            ("system", "swap", "交换分区"),
            ("system", "cpu", "CPU信息"),

            # 网络信息
            ("network.interface", "dump", "网络接口信息"),
            ("network.device", "status", "网络设备状态"),
            ("network.wireless", "status", "无线网络状态"),
            ("network", "status", "网络状态"),

            # 服务信息
            ("service", "list", "服务列表"),
            ("service", "running", "运行中服务"),

            # 系统状态
            ("log", "read", "系统日志"),
            ("ubus", "list", "Ubus服务列表"),

            # OpenWrt 24.10+ 新增接口
            ("system", "led", "LED状态"),
            ("system", "watchdog", "看门狗状态"),
            ("system", "sysupgrade", "系统升级检查"),
            ("system", "upgrade", "升级状态"),

            # 网络高级功能
            ("network", "dump", "网络配置转储"),
            ("network", "reload", "网络重载状态"),
            ("network.interface", "status", "接口状态"),
            ("network.device", "dump", "设备配置转储"),

            # 防火墙和DHCP
            ("firewall", "status", "防火墙状态"),
            ("firewall", "dump", "防火墙规则转储"),
            ("dhcp", "status", "DHCP状态"),
            ("dhcp", "leases", "DHCP租约"),
            # LuCI RPC (useful for DHCP lease lists)
            ("luci-rpc", "getDHCPLeases", "LuCI RPC: DHCP 租约（getDHCPLeases）"),

            # 无线高级功能
            ("network.wireless", "dump", "无线配置转储"),
            ("network.wireless", "reload", "无线重载状态"),

            # 系统监控
            ("system", "monitor", "系统监控"),
            ("system", "stats", "系统统计"),
        ]

        results = {}
        success = 0
        fail = 0

        for namespace, method, description in test_apis:
            print(f"\n🔍 获取{description}:")
            print(f"   API: {namespace}.{method}")

            try:
                result = await self._ubus_call(namespace, method)
                if result is not None:
                    print(f"✅ 数据获取成功")
                    results[f"{namespace}.{method}"] = result
                    success += 1
                else:
                    print(f"❌ 数据获取失败")
                    results[f"{namespace}.{method}"] = None
                    fail += 1
            except Exception as e:
                print(f"❌ 调用异常: {e}")
                results[f"{namespace}.{method}"] = None
                fail += 1

        print("\n🔚 API 测试完成 —— 总结:")
        print(f"   成功: {success}, 失败: {fail}, 总计: {len(test_apis)}")
        return results

    async def show_detailed_info(self, results):
        """显示详细信息"""
        print("\n📊 获取关键信息详情:")
        print("=" * 60)
        
        # 显示系统板信息
        if results.get("system.board"):
            print("\n🔍 获取Ubus API system.board 的详细信息:")
            print("✅ 数据获取成功")
            print(json.dumps(results["system.board"], indent=2, ensure_ascii=False))
        
        # 显示系统信息
        if results.get("system.info"):
            print("\n🔍 获取Ubus API system.info 的详细信息:")
            print("✅ 数据获取成功")
            print(json.dumps(results["system.info"], indent=2, ensure_ascii=False))
        
        # 显示网络接口信息
        if results.get("network.interface.dump"):
            print("\n🔍 获取Ubus API network.interface.dump 的详细信息:")
            print("✅ 数据获取成功")
            print(json.dumps(results["network.interface.dump"], indent=2, ensure_ascii=False))
        
        # 显示OpenWrt 24.10+ 新增功能
        if results.get("system.led"):
            print("\n🔍 获取Ubus API system.led 的详细信息:")
            print("✅ 数据获取成功")
            print(json.dumps(results["system.led"], indent=2, ensure_ascii=False))
        
        if results.get("system.watchdog"):
            print("\n🔍 获取Ubus API system.watchdog 的详细信息:")
            print("✅ 数据获取成功")
            print(json.dumps(results["system.watchdog"], indent=2, ensure_ascii=False))
        
        if results.get("system.sysupgrade"):
            print("\n🔍 获取Ubus API system.sysupgrade 的详细信息:")
            print("✅ 数据获取成功")
            print(json.dumps(results["system.sysupgrade"], indent=2, ensure_ascii=False))

        # 显示 luci-rpc getDHCPLeases 输出（如果可用）
        if results.get("luci-rpc.getDHCPLeases"):
            print("\n🔍 获取 LuCI RPC getDHCPLeases 的详细信息:")
            print("✅ 数据获取成功")
            try:
                print(json.dumps(results["luci-rpc.getDHCPLeases"], indent=2, ensure_ascii=False))
            except Exception:
                print(results["luci-rpc.getDHCPLeases"])

    async def test_dhcp_leases(self) -> Optional[dict]:
        """调用 luci-rpc getDHCPLeases 并统计 IPv4/IPv6 租约数量"""
        print("\n📡 测试 DHCP 租约（luci-rpc getDHCPLeases）")
        try:
            res = await self._ubus_call("luci-rpc", "getDHCPLeases")
            if not res:
                print("❌ 未能获取 DHCP 租约（返回空）")
                return None

            # res 结构不固定：可能是 dict 包含 'data' 或直接为列表
            leases = None
            if isinstance(res, dict):
                # 常见返回可能在 'data' 或 'leases' 下
                if "data" in res and isinstance(res["data"], list):
                    leases = res["data"]
                elif "leases" in res and isinstance(res["leases"], list):
                    leases = res["leases"]
                else:
                    # 如果 dict 本身就是单一租约或键为索引
                    # 尝试把可迭代的 values 收集为列表
                    vals = [v for v in res.values() if isinstance(v, (list, dict))]
                    if vals and isinstance(vals[0], list):
                        leases = vals[0]
                    else:
                        # 无法识别结构，打印并返回
                        print("📋 无法解析返回结构，原始数据:")
                        print(json.dumps(res, indent=2, ensure_ascii=False))
                        return None
            elif isinstance(res, list):
                leases = res

            if leases is None:
                print("📋 未找到可解析的租约列表")
                return None

            ipv4_count = 0
            ipv6_count = 0
            total = 0
            seen_ips = set()

            for item in leases:
                # item 可能是 dict 或简单字符串
                ip_candidates = []
                if isinstance(item, str):
                    ip_candidates.append(item)
                elif isinstance(item, dict):
                    # 常见字段名：ip, ipaddr, address, ipv6, mac
                    for k in ("ip", "ipaddr", "address", "ipv4", "ipv6", "lease"):
                        v = item.get(k) if isinstance(item.get(k), str) else None
                        if v:
                            ip_candidates.append(v)
                    # 有些结构在 nested 字段中
                    if not ip_candidates:
                        for v in item.values():
                            if isinstance(v, str) and ('.' in v or ':' in v):
                                ip_candidates.append(v)

                counted = False
                for ip in ip_candidates:
                    # 简单判断 IPv6 (包含 :)，否则视为 IPv4
                    if ip in seen_ips:
                        continue
                    if ":" in ip:
                        ipv6_count += 1
                        seen_ips.add(ip)
                        counted = True
                    elif "." in ip:
                        ipv4_count += 1
                        seen_ips.add(ip)
                        counted = True
                if counted:
                    total += 1

            print(f"✅ 解析完成：IPv4={ipv4_count}, IPv6={ipv6_count}, 唯一地址数={len(seen_ips)}, 条目计数={total}")
            return {"ipv4": ipv4_count, "ipv6": ipv6_count, "total": len(seen_ips)}
        except Exception as e:
            print(f"❌ 获取或解析 DHCP 租约时出错: {e}")
            return None

    # 如果需要将所有结果导出（包括空结果），由调用者控制

async def main():
    parser = argparse.ArgumentParser(description="OpenWrt Ubus API 调试工具 - OpenWrt 24.10+版本")
    parser.add_argument("--host", required=True, help="OpenWrt路由器IP地址")
    parser.add_argument("--username", required=True, help="用户名")
    parser.add_argument("--password", required=True, help="密码")
    
    args = parser.parse_args()
    
    print("🚀 OpenWrt Ubus API 调试工具 - OpenWrt 24.10+版本")
    print("=" * 60)
    
    async with OpenWrtAPIDebugger(args.host, args.username, args.password) as debugger:
        # 尝试登录
        if not await debugger._login():
            print("\n❌ 登录失败，无法继续测试")
            return
        
        # 测试Ubus服务
        await debugger.test_ubus_services()
        
        # 测试关键API
        results = await debugger.test_key_apis()
        
        # 显示详细信息
        await debugger.show_detailed_info(results)
        # 如果可用，调用 luci-rpc getDHCPLeases 并打印统计
        try:
            dhcp_counts = await debugger.test_dhcp_leases()
            if dhcp_counts is not None:
                print(f"\n📌 DHCP 租约统计: IPv4={dhcp_counts.get('ipv4',0)}, IPv6={dhcp_counts.get('ipv6',0)}, 总计={dhcp_counts.get('total',0)}")
        except Exception:
            # 不要让此步骤阻塞主要流程
            pass
        
        print("\n✨ 调试完成!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        sys.exit(1)
