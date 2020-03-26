# coding: utf-8
import json
import os
import pandas as pd
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.options import define, options, parse_command_line
from tornado.web import RequestHandler, Application
from tornado.web import StaticFileHandler
from datetime import datetime
from chan import KlineAnalyze
import requests


url = "https://dataapi.joinquant.com/apis"
# 获取调用凭证
body = {
    "method": "get_token",
    "mob": "***",  # mob是申请JQData时所填写的手机号
    "pwd": "***",  # Password为聚宽官网登录密码，新申请用户默认为手机号后6位
}
response = requests.post(url, data=json.dumps(body))
token = response.text


def __ts2jq(ts_code):
    if ts_code.endswith("SH") or ts_code.endswith("XSHG"):
        return ts_code[:6] + ".XSHG"
    elif ts_code.endswith("SZ") or ts_code.endswith("XSHE"):
        return ts_code[:6] + ".XSHE"
    else:
        raise ValueError('当前仅支持股票和指数')


def text2df(text):
    rows = [x.split(",") for x in text.strip().split('\n')]
    df = pd.DataFrame(rows[1:], columns=rows[0])
    return df


def get_kline(ts_code, end_date, freq):
    # 1m, 5m, 15m, 30m, 60m, 120m, 1d, 1w, 1M
    freq_convert = {"1min": "1m", "5min": '5m', '15min': '15m',
                    "30min": "30m", "60min": '60m', "D": "1d", "W": '1w'}
    if "-" not in end_date:
        end_date = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")

    data = {
        "method": "get_price",
        "token": token,
        "code": __ts2jq(ts_code),
        "count": 2000,
        "unit": freq_convert[freq],
        "end_date": end_date,
        "fq_ref_date": "2010-01-01"
    }
    r = requests.post(url, data=json.dumps(data))
    df = text2df(r.text)
    df['symbol'] = ts_code
    df.rename({'date': 'dt', 'volume': 'vol'}, axis=1, inplace=True)
    df = df[['symbol', 'dt', 'open', 'close', 'high', 'low', 'vol']]
    for col in ['open', 'close', 'high', 'low']:
        df.loc[:, col] = df[col].apply(lambda x: round(float(x), 2))
    return df


# 端口固定为 8005，不可以调整
define('port', type=int, default=8005, help='服务器端口')
current_path = os.path.dirname(__file__)


class BaseHandler(RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")  # 这个地方可以写域名
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def post(self):
        self.write('some post')

    def get(self):
        self.write('some get')

    def options(self):
        self.set_status(204)
        self.finish()


class BasicHandler(BaseHandler):
    """股票基本信息"""
    def get(self):
        ts_code = self.get_argument('ts_code')
        results = {"msg": "success", "basic": None}
        self.write(json.dumps(results, ensure_ascii=False))


class KlineHandler(BaseHandler):
    """K 线"""
    def get(self):
        ts_code = self.get_argument('ts_code')
        freq = self.get_argument('freq')
        trade_date = self.get_argument('trade_date')
        if trade_date == 'null':
            trade_date = datetime.now().date().__str__().replace("-", "")
        kline = get_kline(ts_code=ts_code, end_date=trade_date, freq=freq)
        ka = KlineAnalyze(kline)
        kline = pd.DataFrame(ka.kline)
        kline = kline.fillna("")
        columns = ["dt", "open", "close", "low", "high", "vol", 'fx_mark', 'fx', 'bi', 'xd']

        self.finish({'kdata': kline[columns].values.tolist()})


if __name__ == '__main__':
    parse_command_line()
    app = Application([
            ('/kline', KlineHandler),
            ('/basic', BasicHandler),
            (r'^/(.*?)$', StaticFileHandler, {"path": os.path.join(current_path, "web"),
                                              "default_filename": "index.html"}),
        ],
        static_path=os.path.join(current_path, "web"),
        dubug=True
    )
    http_server = HTTPServer(app)
    http_server.listen(options.port)
    IOLoop.current().start()



