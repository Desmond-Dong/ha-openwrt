import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
import aiohttp
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        super().__init__()
        self._data = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """第一步：用户输入连接信息"""
        errors = {}
        
        if user_input is not None:
            try:
                # 测试连接
                await self._test_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD]
                )
                
                # 检查是否已配置
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=f"OpenWrt {user_input[CONF_HOST]}", 
                    data=user_input
                )
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=self._data.get(CONF_HOST, "")): str,
                vol.Required(CONF_USERNAME, default=self._data.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=self._data.get(CONF_PASSWORD, "")): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=300)
                ),
            }),
            errors=errors,
        )

    async def _test_connection(self, host, username, password):
        """测试OpenWrt连接"""
        try:
            async with aiohttp.ClientSession() as session:
                # 测试登录
                url = f"http://{host}/ubus"
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "call",
                    "params": [
                        "00000000000000000000000000000000",
                        "session",
                        "login",
                        {
                            "username": username,
                            "password": password
                        }
                    ]
                }
                
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status != 200:
                        raise CannotConnect()
                    
                    data = await resp.json()
                    if "result" not in data or len(data["result"]) < 2:
                        raise InvalidAuth()
                    
                    # 测试基本API调用
                    session_id = data["result"][1]["ubus_rpc_session"]
                    test_payload = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "call",
                        "params": [
                            session_id,
                            "system",
                            "board",
                            {}
                        ]
                    }
                    
                    async with session.post(url, json=test_payload, timeout=10) as test_resp:
                        if test_resp.status != 200:
                            raise CannotConnect()
                        
                        test_data = await test_resp.json()
                        if "result" not in test_data:
                            raise CannotConnect()
                            
        except aiohttp.ClientError:
            raise CannotConnect()
        except asyncio.TimeoutError:
            raise CannotConnect()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """配置选项"""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL, 
                    default=self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            }),
            errors=errors,
        )
