import pandas as pd
import numpy as np
import traceback
import yaml
from datetime import datetime
import time

from websock.client import FtxWebsocketClient
# from websock.websocket_manager import WebsocketManager
from rest import client_us as restclient

import os
from dotenv import load_dotenv

import logging
# logging.basicConfig(level=logging.DEBUG)
#logger = logging.getLogger(__name__)

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

# setup
with open("settings.yaml", "r") as f:
    settings = yaml.safe_load(f)

markets = settings.keys()

bals = pd.DataFrame(rest.get_balances()).set_index('coin')
usd_total = rest.get_total_usd_balance()
num_markets = len(markets)
usd_pos = usd_total/(2*num_markets) * (1-0.0002)
coins = [market[:-4] for market in markets]

inventory = {}
# go 50/50 usd, instrument (per market)
for coin in coins:
    # print(f'rebalancing coin: {coin}')
    coin_usdval = bals.loc[coin, :]['usdValue']
    # print(f'coin val: {coin_usdval}')
    delta = coin_usdval-usd_pos
    # print(f'intended pos: {usd_pos}')
    # print(f'delta: {delta}')
    if delta > 0:
        # sell some coin
        sellp = sock.get_orderbook(f'{coin}/USD')['bids'][0][0]
        # print(f'selling {delta/sellp} at {sellp}')
        try:
            rest.place_order(market=f'{coin}/USD', side='sell',
                             size=delta/sellp*1.0001, price=sellp)
        except Exception as error:
            print()
            # print(f'ERROR: {error}')
    elif delta < 0:
        # buy some coin
        buyp = sock.get_orderbook(f'{coin}/USD')['asks'][0][0]
        # print(
        #    f'buying {-delta/buyp} at {buyp} for total: {-delta/buyp * buyp}')
        try:
            rest.place_order(market=f'{coin}/USD', side='buy',
                             size=-delta/buyp*1.0001, price=buyp)
        except Exception as error:
            print()
        #    print(f'ERROR: {error}')
    else:
        print()
        # print('no need to adjust')
    # store initial inventory as bench mark for delta neutral (roughly)
    bals = pd.DataFrame(rest.get_balances()).set_index('coin')
    inventory[f'{coin}/USD'] = bals.loc[coin, :]['usdValue']
    # print(f'initial inventory {coin}/USD = {inventory[f"{coin}/USD"]}')


while True:

    if i % 1000000 == 0:
        with open("settings.yaml", "r") as f:
            settings = yaml.safe_load(f)

    # get our open orders
    orderdf = pd.DataFrame(rest.get_open_orders())
    # per market
    markets = settings.keys()

    # for each market
    # figure out current market info (nbbo)
    # figure out how wide to quote (vol)
    # figure out how to adjust mid (fade/delta)
    # see if that lines up with the orders we currently have
    # cancel or keep orders
    # spit out what we are currently doing
    # info needed
    # call orderbook data as late as possible - right before execution
    # can we have

    for market in markets:
        # print('-'*70)
        # print(f'{market} settings: {settings[market]}')
        # print(f'{market}')

        delta = pd.DataFrame(rest.get_balances()).set_index(
            'coin').loc[market[:-4], :]['usdValue'] - inventory[market]
        # print(
        #    f'{market} current: {pd.DataFrame(rest.get_balances()).set_index("coin").loc[market[:-4], :]["usdValue"]}')
        # print(f'{market} initial inventory: {inventory[market]}')
        # print(f'{market} delta: {delta}')

        lookback = 4
        seconds = 15
        ohlc_s = pd.DataFrame(rest.get_historical_prices(
            market, resolution=seconds, start_time=time.time()-seconds*lookback))
        stdv = ohlc_s['close'].std()

        # get params
        size = settings[market]['size']
        spread_sigma = settings[market]['spread_sigma']
        fade = settings[market]['fade']

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
        #mid += fade*(delta/usd_pos)

        # set bid and ask
        bid_price = mid-(spread_sigma*stdv)
        ask_price = mid+(spread_sigma*stdv)

        # print(f'{market} mid: {mid}')
        # print(f'{market}: stdv: {stdv}')
        # print(f'{market}: nbbo: {bestbid_price} @ {bestask_price}')
        # print(f'{market}: stdv sigma: {stdv*spread_sigma}')
        # print(f'{market}: intended quote: {bid_price} @ {ask_price}')

        # if we don't have anything in the order df, then place order initially
        if len(orderdf) == 0:
            try:
                rest.place_order(market=market, side='buy',
                                 price=bid_price, size=size, post_only=True)
            except Exception as error:
                print()
            #    print(f'ERROR: {error}')
            try:
                rest.place_order(market=market, side='sell',
                                 price=ask_price, size=size, post_only=True)
            except Exception as error:
                print()
            #    print(f'ERROR: {error}')
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

        # print(f'{market} current quote: {curbid} @ {curask}')
        # print(f'{market} intended quote: {bid_price} @ {ask_price}')
        # print(f'{market} size: {bid_price*size} @ {ask_price*size}')

        totalorders = numasks + numbids
        # if no orders in market
        if totalorders == 0:
            try:
                rest.place_order(market=market, side='buy',
                                 price=bid_price, size=1, post_only=True)
            except Exception as error:
                print()
                # print(f'ERROR: {error}')
            try:
                rest.place_order(market=market, side='sell',
                                 price=ask_price, size=1, post_only=True)
            except Exception as error:
                print()
                # print(f'ERROR: {error}')
        else:
            if not curbid == bid_price:
                # print(f'{market} {curbid} not {bid_price}')
                if not numbids == 0:
                    bid_id = thismarket[thismarket['side']
                                        == 'buy']['id'].item()
                    rest.cancel_order(bid_id)
                try:
                    rest.place_order(
                        market=market, side='buy', price=bid_price, size=1, post_only=True)
                except Exception as error:
                    print()
                    # print(f'ERROR: {error}')
            if not curask == ask_price:
                # print(f'{market} {curask} not {ask_price}')
                if not numasks == 0:
                    ask_id = thismarket[thismarket['side']
                                        == 'sell']['id'].item()
                    rest.cancel_order(ask_id)
                try:
                    rest.place_order(
                        market=market, side='sell', price=ask_price, size=1, post_only=True)
                except Exception as error:
                    print()
                    # print(f'ERROR: {error}')

        print(f'{market} | {bid_price} | {mid} | {ask_price} | {np.round(delta, 3)}')
