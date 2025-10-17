import aiohttp
import asyncio
from astrbot.api.all import *

FIRST_API_URL = "http://api.ocoa.cn/api/cyw.php"
SECOND_API_URL = "http://api.ocoa.cn/api/cyw.php"

@register("business_query", "查业务", "业务查询插件", "1.0")
class BusinessQueryPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    def _format_result(self, raw_result: str) -> str:
        """格式化 result：替换符号 + 去掉分隔线 + 用空行分隔业务"""
        if not raw_result:
            return "⚠️ 未返回有效数据。"
        
        # 替换自动续费符号
        text = raw_result.replace("✓", "✅").replace("X", "❌")
        
        # 按原始分隔线切分，过滤空块
        blocks = [block.strip() for block in text.split("-----------------------------") if block.strip()]
        
        # 用两个换行符（\n\n）连接每个业务块，形成空行分隔
        return "\n\n".join(blocks)

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        msg = event.message_str.strip()
        if msg not in ["查业务", "业务查询"]:
            return

        # 第一步：获取二维码
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

        qr_image = first_data.get("qr_image")
        verify = first_data.get("verify")
        tip_msg = first_data.get("msg", "请扫码")

        if not qr_image or not verify:
            yield event.chain_result([Plain(text="❌ 返回数据不完整，无法继续查询。")])
            return

        yield event.chain_result([
            Plain(text=f"{tip_msg}\n（15秒后自动返回查询结果）\n"),
            Image.fromURL(qr_image)
        ])

        await asyncio.sleep(15)

        # 第二步：带 verify 查询结果
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{SECOND_API_URL}?verify={verify}") as resp:
                    second_data = await resp.json()
        except Exception as e:
            self.context.logger.error(f"Second API error: {e}")
            yield event.chain_result([Plain(text="❌ 查询结果获取失败。")])
            return

        # 检查是否成功
        if second_data.get("code") != 0:
            error_msg = second_data.get("msg", "未知错误")
            yield event.chain_result([Plain(text=f"❌ 查询失败：{error_msg}")])
            return

        result_text = second_data.get("result", "").strip()
        if not result_text:
            yield event.chain_result([Plain(text="⚠️ 查询成功，但未返回业务数据。")])
            return

        formatted = self._format_result(result_text)
        yield event.chain_result([Plain(text=formatted)])
