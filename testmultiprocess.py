# libraries we need
import pandas as pd
import numpy as np
import time
import multiprocessing

# FTXUS API stuff
from websock.client import FtxWebsocketClient
from rest import client_us as restclient

# reading from other files
import os
from dotenv import load_dotenv
import yaml


def midwatch(markets, sock):
    while True:
        mid_dict = {}
        for market in markets:
            book = sock.get_orderbook(market)
            topask = book['asks'][0][0]
            topbid = book['bids'][0][0]
            mid = (topask+topbid)/2
            mid_dict[market] = mid
        with open("marketdata.yaml", "w") as f:
            yaml.dump(mid_dict, f)


def trader(markets, rest):
    flag = False
    while True:
        with open("marketdata.yaml", "r") as f:
            marketdata = yaml.safe_load(f)
        with open("settings.yaml", "r") as f:
            settings = yaml.safe_load(f)
        for market in markets:
            mid = marketdata[market]
            bid = 0.9*mid
            ask = 1.1*mid
            if not flag:
                rest.place_order(market=market, price=bid, side='buy',
                                 size=settings[market]['size'], post_only=True)
                rest.place_order(market=market, price=ask, side='sell',
                                 size=settings[market]['size'], post_only=True)
                flag = True


if __name__ == '__main__':
    # initialize everything

    # load in api keys
    API_KEY = os.getenv('API_KEY')
    SECRET_KEY = os.getenv('SECRET_KEY')

    # connect to rest client
    rest = restclient.FtxClient(api_key=API_KEY, api_secret=SECRET_KEY)

    # connect to websocket
    sock = FtxWebsocketClient()
    sock.connect()

    # read settings file
    with open("settings.yaml", "r") as f:
        settings = yaml.safe_load(f)
    pairs = list(settings.keys())

    # initialize market data file
    with open("marketdata.yaml", "w") as f:
        initdata = yaml.dump({
            'SOL/USD': 0,
            'BTC/USD': 0,
            'ETH/USD': 0,
        }, f)
    with open("marketdata.yaml", "r") as f:
        initdata = yaml.safe_load(f)
    print(f'init: {initdata}')

    p1 = multiprocessing.Process(
        name='p1', target=midwatch, kwargs={"markets": pairs, "sock": sock})
    p = multiprocessing.Process(
        name='p', target=trader, kwargs={"markets": pairs, "rest": rest})

    p1.start()
    p.start()
