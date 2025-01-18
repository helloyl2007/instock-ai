from openai import OpenAI
import asyncio
import aiohttp
import json
from datetime import datetime

class AIChat:
    def __init__(self):
        self.client = OpenAI(
            api_key="sk-xxxxxxx", # 请替换为您的API Key
            base_url="your api url" # 请替换为您的API URL
        )
        self.current_conversation = [
            {"role": "system", "content": """你是一个专业的股票投资专家。请提取内容中包含的股票名称或代码，请严格按以下规则输出。
规则：
1. 如果提到股票名称或代码，包括有近拟的取近拟的股票名称或代码，请提取补全并放入JSON中,不要多余的回答。
2. 不管有没有股票名称或代码，请按以下JSON式标准输出。
3. JSON格式标准如下：
{
    "contains_stock": true/false,
    "codes": ["股票代码"],
    "names": ["股票标准名称"]
}"""}
        ]
        self.MAX_CONVERSATION_LENGTH = 10  # 设置最大对话历史长度

    async def _get_last_trade_date(self):
        """获取最新的交易日期"""
        base_url = "http://localhost:9988/instock/api_data"
        params = {
            "name": "cn_stock_selection",
            "get_last_date": "1"  # 添加一个标识，表示只获取最新日期
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                data = await response.json()
                if data and len(data) > 0:
                    return data[0].get('date')
                return datetime.now().strftime('%Y-%m-%d')

    async def _get_stock_data(self, code=None, stock_name=None):
        """获取股票数据"""
        trade_date = await self._get_last_trade_date()
        base_url = "http://localhost:9988/instock/api_data"
        params = {
            "name": "cn_stock_selection",
            "date": trade_date
        }
        if code:
            params["code"] = code
        if stock_name:
            params["stock_name"] = stock_name

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                return await response.json()

    async def _analyze_stock_info(self, message):
        """分析用户消息中的股票信息"""
        analyze_conversation = [
            {"role": "system", "content": """请提取文本中的股票信息，仅返回JSON格式数据：
{
    "contains_stock": true/false,
    "codes": ["股票代码"],
    "names": ["股票标准名称"]
}"""},
            {"role": "user", "content": message}
        ]
        
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4",# 换成你的模型名称
                messages=analyze_conversation,
                temperature=0,
                response_format={ "type": "json_object" } 
            )
            
            content = response.choices[0].message.content
            try:
                result = json.loads(content)
                if all(k in result for k in ['contains_stock', 'codes', 'names']):
                    if result["codes"] or result["names"]:
                        result["contains_stock"] = True
                    return result
            except json.JSONDecodeError:
                pass
            return {"contains_stock": False, "codes": [], "names": []}
            
        except Exception as e:
            print(f"分析股票信息时发生错误: {str(e)}")
            return {"contains_stock": False, "codes": [], "names": []}

    async def _get_ai_analysis(self, message, stock_data):
        """获取AI对股票数据的分析"""
        prompt = f"""
用户问题：{message}
股票数据：{json.dumps(stock_data, ensure_ascii=False)}
请给出专业的投资建议。"""
        
        analysis_conversation = [
            {"role": "system", "content": "你是一个专业的股票投资顾问，请基于你获得的数据给出专业的建议。回答规则：要说明根据xx年xx月xx日（日期）数据，先简单总结当天的基本数据包括开盘价，收盘价，最高价，最低价，涨跌幅，交易量，交易金额，换手率等，分析是否活跃。再把值为“是”的技术面数据进行分析，依次为：技术指标、K线形态、选股策略、人气分析、概念题材等方面，如果没有命中就不需要提及，最后总结建议。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model="gpt-4",# 换成你的模型名称
            messages=analysis_conversation,
            stream=True
        )
        
        return response

    async def get_stream_response(self, message):
        try:
            # 1. 分析是否包含股票信息
            stock_info = await self._analyze_stock_info(message)
            
            if not stock_info.get("contains_stock", False) or (not stock_info.get("codes", []) and not stock_info.get("names", [])):
                # 构建包含历史对话的临时会话列表
                temp_conversation = []
                
                # 添加系统角色提示
                temp_conversation.append({
                    "role": "system",
                    "content": "你是一个专业的股票投资顾问，请基于你的专业知识回答用户的问题。"
                })
                
                # 添加历史对话记录
                if len(self.current_conversation) > 1:  # 如果有历史对话(排除系统提示)
                    history = self.current_conversation[1:]  # 排除原始的system消息
                    # 只保留最近的对话
                    start_idx = max(0, len(history) - (self.MAX_CONVERSATION_LENGTH - 1))
                    temp_conversation.extend(history[start_idx:])
                
                # 添加当前用户消息
                temp_conversation.append({"role": "user", "content": message})
                
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="gpt-4",# 换成你的模型名称
                    messages=temp_conversation,
                    stream=True
                )

                # 处理普通对话响应
                ai_response = ""
                async for chunk in AsyncIterator(response):
                    if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        ai_response += content
                        yield content

                # 保存对话历史并维护长度
                self.current_conversation.append({"role": "user", "content": message})
                self.current_conversation.append({"role": "assistant", "content": ai_response})
                if len(self.current_conversation) > self.MAX_CONVERSATION_LENGTH + 1:
                    self.current_conversation = [self.current_conversation[0]] + self.current_conversation[-(self.MAX_CONVERSATION_LENGTH):]
            else:
                # 2. 获取股票数据
                stock_data = []
                has_valid_data = False
                
                # 尝试通过代码获取数据
                for code in stock_info["codes"]:
                    data = await self._get_stock_data(code=code)
                    if data and len(data) > 0:
                        stock_data.extend(data)
                        has_valid_data = True
                
                # 如果代码没有获取到数据，尝试通过名称获取
                if not has_valid_data:
                    for name in stock_info["names"]:
                        data = await self._get_stock_data(stock_name=name)
                        if data and len(data) > 0:
                            stock_data.extend(data)
                            has_valid_data = True
                
                # 如果没有获取到任何数据，返回提示信息
                if not has_valid_data:
                    no_data_msg = "目前我还没有这只股票的信息，请用股票全称或代码试试，或者你可以再问其它的股票。"
                    yield no_data_msg
                    # 保存对话历史
                    self.current_conversation.append({"role": "user", "content": message})
                    self.current_conversation.append({"role": "assistant", "content": no_data_msg})
                    return
                else:
                    # 3. 获取AI分析结果
                    response = await self._get_ai_analysis(message, stock_data)
                    ai_response = ""
                    async for chunk in AsyncIterator(response):
                        if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            ai_response += content
                            yield content
                    
                    # 保存对话历史并维护长度
                    self.current_conversation.append({"role": "user", "content": message})
                    self.current_conversation.append({"role": "assistant", "content": ai_response})
                    if len(self.current_conversation) > self.MAX_CONVERSATION_LENGTH + 1:
                        self.current_conversation = [self.current_conversation[0]] + self.current_conversation[-(self.MAX_CONVERSATION_LENGTH):]

        except Exception as e:
            error_msg = f"AI服务调用失败: {str(e)}"
            yield error_msg
            self.current_conversation.append({"role": "assistant", "content": error_msg})

class AsyncIterator:
    def __init__(self, sync_iter):
        self.sync_iter = sync_iter

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.sync_iter)
        except StopIteration:
            raise StopAsyncIteration
