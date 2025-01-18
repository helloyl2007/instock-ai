#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import json
from abc import ABC
from tornado import gen
# import logging
import datetime
import instock.lib.trade_time as trd
import instock.core.singleton_stock_web_module_data as sswmd
import instock.web.base as webBase

__author__ = 'myh '
__date__ = '2023/3/10 '


class MyEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, bytes):
            return "是" if ord(obj) == 1 else "否"
        elif isinstance(obj, datetime.date):
            # 直接返回日期字符串，不使用OADate格式
            return obj.strftime('%Y-%m-%d')
        else:
            return json.JSONEncoder.default(self, obj)


# 获得页面数据。
class GetStockHtmlHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        name = self.get_argument("table_name", default=None, strip=False)
        web_module_data = sswmd.stock_web_module_data().get_data(name)
        run_date, run_date_nph = trd.get_trade_date_last()
        if web_module_data.is_realtime:
            date_now_str = run_date_nph.strftime("%Y-%m-%d")
        else:
            date_now_str = run_date.strftime("%Y-%m-%d")
        self.render("stock_web.html", web_module_data=web_module_data, date_now=date_now_str,
                    leftMenu=webBase.GetLeftMenu(self.request.uri))


# 获得股票数据内容。
class GetStockDataHandler(webBase.BaseHandler, ABC):
    def get(self):
        name = self.get_argument("name", default=None, strip=False)
        date = self.get_argument("date", default=None, strip=False)
        code = self.get_argument("code", default=None, strip=False)
        stock_name = self.get_argument("stock_name", default=None, strip=False)
        get_last_date = self.get_argument("get_last_date", default=None, strip=False)
        
        web_module_data = sswmd.stock_web_module_data().get_data(name)
        self.set_header('Content-Type', 'application/json;charset=UTF-8')

        if get_last_date:
            # 获取最新的交易日期
            sql = f"""
                SELECT `date` 
                FROM `{web_module_data.table_name}` 
                ORDER BY `date` DESC 
                LIMIT 1
            """
            data = self.db.query(sql)
            self.write(json.dumps(data, cls=MyEncoder))
            return

        where_conditions = []
        where_params = []
        
        if date is not None:
            where_conditions.append("`date` = %s")
            where_params.append(date)
            
        if code is not None:
            where_conditions.append("`code` = %s")
            where_params.append(code)
            
        if stock_name is not None:
            where_conditions.append("`name` = %s")
            where_params.append(stock_name)

        where = ""
        if where_conditions:
            where = " WHERE " + " AND ".join(where_conditions)

        order_by = ""
        if web_module_data.order_by is not None:
            order_by = f" ORDER BY {web_module_data.order_by}"

        sql = f"SELECT * FROM `{web_module_data.table_name}`{where}{order_by}"
        data = self.db.query(sql, *where_params)

        self.write(json.dumps(data, cls=MyEncoder))
