import aiohttp
import asyncio
from astrbot.api.all import *

FIRST_API_URL = "http://api.ocoa.cn/api/cyw.php"
SECOND_API_URL = "http://api.ocoa.cn/api/cyw.php"

@register("business_query", "查业务", "业务查询插件", "1.0")
class BusinessQueryPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        msg = event.message_str.strip()
        if msg not in ["查业务", "业务查询"]:
            return

        # 第一步：调用第一个接口
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(FIRST_API_URL) as resp:
                    if resp.status != 200:
                        yield event.chain_result([Plain(text="❌ 获取二维码失败，请稍后再试。")])
                        return
                    first_data = await resp.json()
        except Exception as e:
            self.context.logger.error(f"First API error: {e}")
            yield event.chain_result([Plain(text="❌ 网络请求异常，请稍后再试。")])
            return

        # 检查必要字段
        qr_image = first_data.get("qr_image")
        verify = first_data.get("verify")
        tip_msg = first_data.get("msg", "请扫码")

        if not qr_image or not verify:
            yield event.chain_result([Plain(text="❌ 返回数据缺失，无法继续查询。")])
            return

        # 发送二维码 + 提示
        yield event.chain_result([
            Plain(text=f"{tip_msg}\n（15秒后自动返回查询结果）\n"),
            Image.fromURL(qr_image)
        ])

        # 等待15秒
        await asyncio.sleep(15)

        # 第二步：带 verify 调用第二个接口，返回原始内容
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{SECOND_API_URL}?verify={verify}") as resp:
                    raw_text = await resp.text()
                    # 直接返回原始响应文本（可能是 JSON 字符串）
                    yield event.chain_result([Plain(text=raw_text)])
        except Exception as e:
            self.context.logger.error(f"Second API error: {e}")
            yield event.chain_result([Plain(text="❌ 查询结果获取失败。")])
