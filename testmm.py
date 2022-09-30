import pandas as pd
import traceback
import yaml
from datetime import datetime

from websock.client import FtxWebsocketClient
# from websock.websocket_manager import WebsocketManager
from rest import client_us as restclient

import os
from dotenv import load_dotenv

load_dotenv()

# load in api keys
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

# connect to rest client
rest = restclient.FtxClient(api_key=API_KEY, api_secret=SECRET_KEY)

# connect to websocket
sock = FtxWebsocketClient()
sock.connect()

i = 0

while True:

    if i % 1000000 == 0:
        with open("settings.yaml", "r") as f:
            settings = yaml.load(f)

        size = settings['size']
        edge = settings['edge']
        markets = settings['markets']

    # get our open orders
    # orderdf = pd.DataFrame(rest.get_open_orders())
    # per market

    for market in markets:
        continue
        print('-'*35)ç
        print(f'{market}')

        # get orderbook data, top 10 bids and asks
        asks = pd.DataFrame(sock.get_orderbook(market)['asks'][0:11]).rename(
            columns={0: 'price', 1: 'size'})
        bids = pd.DataFrame(sock.get_orderbook(market)['bids'][0:11]).rename(
            columns={0: 'price', 1: 'size'})

        bestask_price = asks.iloc[0]['price']
        bestbid_price = bids.iloc[0]['price']
        bestask_size = asks.iloc[0]['size']
        bestbid_size = bids.iloc[0]['size']

        mid = (bestbid_price+bestask_price)/2

        # set bid and ask
        bid_price = mid*(1-edge)
        ask_price = mid*(1+edge)

        # if we don't have anything in the order df, then place order initially
        if len(orderdf) == 0:
            try:
                rest.place_order(market=market, side='buy',
                                 price=bid_price, size=size)
            except:
                print(traceback.format_exc())
                print(f'{market} initial bid failed')
            try:
                rest.place_order(market=market, side='sell',
                                 price=ask_price, size=size)
            except:
                print(traceback.format_exc())
                print(f'{market} initial offer failed')
            continue
        # otherwise, set the orderdf of this market
        else:
            thismarket = orderdf[orderdf['market'] == market]

        # get number of asks/bids (should be one for now, eventually add scales)
        numasks = len(thismarket[thismarket['side'] == 'sell']['price'])
        numbids = len(thismarket[thismarket['side'] == 'buy']['price'])

        # find our current bid and ask
        if numbids > 0:
            curbid = thismarket[thismarket['side'] == 'buy']['price'].item()
        else:
            curbid = 0
        if numasks > 0:
            curask = thismarket[thismarket['side'] == 'sell']['price'].item()
        else:
            curask = 0

        # print what we're doing

        print(f'{market} current quote: {curbid} @ {curask}')
        print(f'{market} intended quote: {bid_price} @ {ask_price}')
        print(f'{market} size: {bid_price*size} @ {ask_price*size}')

        totalorders = numasks + numbids
        # if no orders in market
        if totalorders == 0:
            try:
                rest.place_order(market=market, side='buy',
                                 price=bid_price, size=1)
            except:
                print(traceback.format_exc())
                print(f'{market} initial bid failed')
            try:
                rest.place_order(market=market, side='sell',
                                 price=ask_price, size=1)
            except:
                print(traceback.format_exc())
                print(f'{market} initial offer failed')
        else:
            if not curbid == bid_price:
                print(f'{market} {curbid} not {bid_price}')
                if not numbids == 0:
                    bid_id = thismarket[thismarket['side']
                                        == 'buy']['id'].item()
                    rest.cancel_order(bid_id)
                try:
                    rest.place_order(
                        market=market, side='buy', price=bid_price, size=1)
                except:
                    print(traceback.format_exc())
                    print(f'{market} failed to replace bid')
            if not curask == ask_price:
                print(f'{market} {curask} not {ask_price}')
                if not numasks == 0:
                    ask_id = thismarket[thismarket['side']
                                        == 'sell']['id'].item()
                    rest.cancel_order(ask_id)
                try:
                    rest.place_order(
                        market=market, side='sell', price=ask_price, size=1)
                except:
                    print(traceback.format_exc())
                    print(f'{market} failed to replace offer')
