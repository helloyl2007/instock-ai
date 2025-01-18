#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

from abc import ABC
from tornado import gen
import tornado.escape
import logging
import instock.core.stockfetch as stf
import instock.core.kline.visualization as vis
import instock.web.base as webBase

__author__ = 'myh '
__date__ = '2023/3/10 '


# 获得页面数据。
class GetDataIndicatorsHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        code = self.get_argument("code", default=None, strip=False)
        date = self.get_argument("date", default=None, strip=False)
        name = self.get_argument("name", default=None, strip=False)
        comp_list = []
        isAttention = False
        try:
            if code.startswith(('1', '5')):
                stock = stf.fetch_etf_hist((date, code))
            else:
                stock = stf.fetch_stock_hist((date, code))
            if stock is None:
                return

            pk = vis.get_plot_kline(code, stock, date, name)
            if pk is None:
                return

            comp_list.append(pk)

            if self.get_secure_cookie("user"):
                user = tornado.escape.xhtml_escape(self.get_secure_cookie("user").decode())
                sql = "SELECT COUNT(*) as count FROM cn_stock_attention WHERE code = %s AND user_id = (SELECT id FROM users WHERE username = %s)"
                result = self.db.get(sql, code, user)
                isAttention = result['count'] > 0

        except Exception as e:
            logging.error(f"dataIndicatorsHandler.GetDataIndicatorsHandler处理异常：{e}")

        self.render("stock_indicators.html", comp_list=comp_list,
                    leftMenu=webBase.GetLeftMenu(self.request.uri),
                    code=code,
                    isAttention=isAttention)


# 关注股票和检查关注状态。
class AttentionHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        import datetime
        import instock.core.tablestructure as tbs
        code = self.get_argument("code", default=None, strip=False)
        action = self.get_argument("action", default=None, strip=False)
        
        try:
            table_name = tbs.TABLE_CN_STOCK_ATTENTION['name']
            if action == "check":
                sql = f"SELECT COUNT(*) as count FROM {table_name} WHERE code = %s"
                result = self.db.get(sql, code)
                isAttention = result['count'] > 0
                self.write({"isAttention": isAttention})
            elif action == "toggle":
                sql_check = f"SELECT COUNT(*) as count FROM `{table_name}` WHERE `code` = %s"
                result = self.db.get(sql_check, code)
                otype = '1' if result['count'] > 0 else '0'
                if otype == '1':
                    sql = f"DELETE FROM `{table_name}` WHERE `code` = %s"
                    self.db.execute(sql, code)
                else:
                    sql = f"INSERT INTO `{table_name}`(`datetime`, `code`) VALUES (%s, %s)"
                    self.db.execute(sql, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), code)
                self.write({"success": True})
        except Exception as e:
            err = {"error": str(e)}
            self.write(err)

    @gen.coroutine
    def get_my_attention(self):
        try:
            sql = """
                SELECT s.* FROM cn_stock_attention a
                JOIN cn_stock_spot s ON a.code = s.code
                GROUP BY s.code
            """
            stocks = self.db.query(sql)
            self.write({"stocks": stocks})
        except Exception as e:
            self.write({"error": str(e)})