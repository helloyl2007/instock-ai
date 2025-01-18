#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import os.path
import sys
from abc import ABC

import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
from tornado import gen

# 首先设置路径
cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)

# 然后进行所有导入
import instock.lib.torndb as torndb
import instock.lib.database as mdb
import instock.lib.version as version
import instock.web.dataTableHandler as dataTableHandler
import instock.web.dataIndicatorsHandler as dataIndicatorsHandler
import instock.web.base as webBase
from instock.core.llm_setting.chat_handler import AIChat

__author__ = 'myh '
__date__ = '2023/3/10 '


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            # 设置路由
            (r"/", AIChatHandler),  
            (r"/usage", UsageHandler),  
            (r"/instock/", InstockHandler),
            (r"/instock/api_data", dataTableHandler.GetStockDataHandler),
            (r"/instock/data", StockHtmlHandler),
            (r"/instock/data/indicators", dataIndicatorsHandler.GetDataIndicatorsHandler),
            (r"/instock/control/attention", dataIndicatorsHandler.AttentionHandler),
            (r"/instock/my_attention", MyAttentionHandler),
            (r"/instock/ai_chat", AIChatHandler),
            (r"/instock/ai_chat/clear", AIChatClearHandler),
        ]

        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=False,
            cookie_secret="027bb1b670eddf0392cdda8709268a17b58b7",
            debug=True,
        )
        super(Application, self).__init__(handlers, **settings)
        self.db = torndb.Connection(**mdb.MYSQL_CONN_TORNDB)

# InstockHandler
class InstockHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        self.render("stock_web.html",
                   stockVersion=version.__version__,
                   leftMenu=webBase.GetLeftMenu(self.request.uri))

# 修改认证类为普通类
class StockHtmlHandler(dataTableHandler.GetStockHtmlHandler):
    @gen.coroutine
    def get(self):
        super(StockHtmlHandler, self).get()

# AIChatHandler
class AIChatHandler(webBase.BaseHandler, ABC):
    _chat_instance = AIChat()  # 使用单个全局实例

    def initialize(self):
        self.ai_chat = self._chat_instance

    @gen.coroutine
    def get(self):
        chat_history = self.ai_chat.current_conversation[1:]
        self.render("ai_chat.html",
                   stockVersion=version.__version__,
                   leftMenu=webBase.GetLeftMenu(self.request.uri),
                   chat_history=chat_history)
    
    async def post(self):
        message = self.get_argument("message", "")
        if not message:
            self.write({"status": "error", "message": "消息不能为空"})
            return
            
        try:
            self.set_header('Content-Type', 'text/event-stream')
            self.set_header('Cache-Control', 'no-cache')
            self.set_header('Connection', 'keep-alive')
            
            async for chunk in self.ai_chat.get_stream_response(message):
                self.write(f"data: {chunk}\n\n")
                await self.flush()
            
            self.write("data: [DONE]\n\n")
            await self.flush()
        except Exception as e:
            self.write(f"data: error: {str(e)}\n\n")
        finally:
            self.finish()

# 修改 AIChatClearHandler
class AIChatClearHandler(webBase.BaseHandler, ABC):
    def post(self):
        # 直接重置聊天实例
        AIChatHandler._chat_instance = AIChat()
        self.write({"status": "success"})


# 修改 UsageHandler
class UsageHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        self.render("usage.html",
                   stockVersion=version.__version__,
                   leftMenu=webBase.GetLeftMenu(self.request.uri))

# 我的关注处理器
class MyAttentionHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        try:
            sql = """
                SELECT s.code, s.name, s.new_price, s.change_rate, s.ups_downs, s.volume, 
                       s.deal_amount, s.amplitude, s.volume_ratio, s.turnoverrate, s.open_price, 
                       s.high_price, s.low_price, s.pre_close_price, s.dtsyl, s.pe9, s.pe, 
                       s.pbnewmrq, s.basic_eps, s.bvps, s.per_capital_reserve, s.per_unassign_profit, 
                       s.roe_weight, s.sale_gpr, s.debt_asset_ratio, s.total_operate_income, 
                       s.toi_yoy_ratio, s.parent_netprofit, s.netprofit_yoy_ratio, s.total_shares, 
                       s.free_shares, s.total_market_cap, s.free_cap, s.industry
                FROM cn_stock_attention a
                JOIN cn_stock_spot s ON a.code = s.code
                GROUP BY s.code
            """
            stocks = self.db.query(sql)
            if self.get_argument("format", None) == "json":
                self.write({"data": stocks})
            else:
                self.render("my_attention.html",
                        stocks=stocks,
                        leftMenu=webBase.GetLeftMenu(self.request.uri))
        except Exception as e:
            self.write(f"获取关注的股票信息失败：{e}")

def main():
    http_server = tornado.httpserver.HTTPServer(Application())
    port = 9988
    http_server.listen(port)
    
    print(f"服务已启动，web地址 : http://localhost:{port}/")
    
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
