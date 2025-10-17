import os
import aiohttp
import asyncio
import json
from astrbot.api.all import *

PLUGIN_DIR = os.path.join('data', 'plugins', 'astrbot_plugin_businessquery')

# 新的接口地址（明文，无需 base64）
FIRST_API_URL = "http://api.ocoa.cn/api/cyw.php"
SECOND_API_URL_TEMPLATE = "http://api.ocoa.cn/api/cyw.php?verify={verify}"

@register("business_query", "查业务", "查询业务信息的插件", "1.0")
class BusinessQueryPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    async def _fetch_first_step(self):
        """调用第一个接口，获取二维码和 verify"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(FIRST_API_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        self.context.logger.error(f"First API returned status {response.status}")
                        return None
        except Exception as e:
            self.context.logger.error(f"First API request failed: {str(e)}")
            return None

    async def _fetch_second_step(self, verify: str):
        """用 verify 调用第二个接口，获取最终结果"""
        url = SECOND_API_URL_TEMPLATE.format(verify=verify)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        self.context.logger.error(f"Second API returned status {response.status}")
                        return None
        except Exception as e:
            self.context.logger.error(f"Second API request failed: {str(e)}")
            return None

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        msg = event.message_str.strip()
        
        if msg in ["查业务", "业务查询"]:
            # 第一步：获取二维码
            first_data = await self._fetch_first_step()
            
            if not first_data or first_data.get("code") != 0:
                yield event.chain_result([Plain(text="获取业务查询二维码失败，请稍后再试。")])
                return

            qr_image = first_data.get("qr_image")
            verify = first_data.get("verify")
            msg_tip = first_data.get("msg", "请扫码完成验证")

            if not qr_image or not verify:
                yield event.chain_result([Plain(text="返回数据不完整，缺少二维码或验证参数。")])
                return

            # 发送二维码图片 + 提示
            yield event.chain_result([
                Plain(text=f"{msg_tip}\n（系统将在15秒后自动查询结果，请勿重复发送指令）\n"),
                Image(url=qr_image)
            ])

            # 等待15秒
            await asyncio.sleep(15)

            # 第二步：用 verify 查询结果
            second_data = await self._fetch_second_step(verify)

            if not second_data:
                yield event.chain_result([Plain(text="查询超时或验证失败，请重新尝试。")])
                return

            # 根据返回内容决定如何展示
            # 假设最终结果在 msg 或其他字段，这里做通用处理
            if second_data.get("code") == 0:
                # 如果返回了新的二维码（比如需要二次扫码），也可以处理
                if "qr_image" in second_data:
                    # 可能需要再次扫码？但你没说明，这里按最终结果处理
                    final_msg = second_data.get("msg", "操作成功")
                    final_img = second_data.get("qr_image")
                    if final_img:
                        yield event.chain_result([
                            Plain(text=f"后续操作：{final_msg}\n"),
                            Image(url=final_img)
                        ])
                    else:
                        yield event.chain_result([Plain(text=final_msg)])
                else:
                    # 假设是纯文本结果
                    result_text = json.dumps(second_data, ensure_ascii=False, indent=2)
                    yield event.chain_result([Plain(text=f"查询结果：\n{result_text}")])
            else:
                error_msg = second_data.get("msg", "未知错误")
                yield event.chain_result([Plain(text=f"查询失败：{error_msg}")])
