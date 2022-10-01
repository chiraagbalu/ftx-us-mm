import pandas as pd
import numpy as np
import traceback
import yaml
from datetime import datetime
import time
import atexit

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

atexit.register(rest.cancel_orders)

# setup
with open("settings.yaml", "r") as f:
    settings = yaml.safe_load(f)

markets = settings.keys()

# get current inventory
bals = pd.DataFrame(rest.get_balances())
init_inventory = bals[['coin', 'usdValue']].set_index('coin').to_dict()[
    'usdValue']
inventory = init_inventory
# calculate total value of account, and amount of money per market
usd_total = rest.get_total_usd_balance()
usd_per = usd_total/(2*len(markets)) * (1-0.0002)
coins = [market[:-4] for market in markets]

# for each coin we are trading:
for coin in coins:
    coin_usdval = inventory[coin]
    delta = coin_usdval-usd_per
    sellp = 0
    buyp = 0
    # marekt in to adjust initial inventory as needed
    if delta > 0:
        sellp = sock.get_orderbook(f'{coin}/USD')['bids'][0][0]
        try:
            rest.place_order(market=f'{coin}/USD', side='sell',
                             size=delta/sellp*1.0001, price=sellp)
        except Exception as error:
            print(f'{error}')
    elif delta < 0:
        buyp = sock.get_orderbook(f'{coin}/USD')['asks'][0][0]
        try:
            rest.place_order(market=f'{coin}/USD', side='buy',
                             size=-delta/buyp*1.0001, price=buyp)
        except Exception as error:
            print(f'{error}')
    marketp = max(sellp, buyp)
    # initial quote
    rest.place_order(f'{coin}/USD', side='sell', price=marketp*1.19,
                     size=settings[f'{coin}/USD']['minsize'], post_only=True)
    rest.place_order(f'{coin}/USD', side='buy', price=marketp*0.81,
                     size=settings[f'{coin}/USD']['minsize'], post_only=True)


while True:
    # update settings
    with open("settings.yaml", "r") as f:
        settings = yaml.safe_load(f)
    # get orders
    orders = pd.DataFrame(rest.get_open_orders())
    # for each market
    for market in markets:
        start = time.time()
        # get params
        size = settings[market]['size']
        sigma = settings[market]['sigma']
        fade = settings[market]['fade']
        maxquotes = 1

        # calculate realized vol
        lookback = 4
        seconds = 15
        r_vol = pd.DataFrame(rest.get_historical_prices(
            market, resolution=seconds, start_time=time.time()-seconds*lookback))['close'].std()

        # get current order prices
        cur_quote = orders[orders['market'] == market]
        cur_bid = 0
        cur_ask = 0
        nobid = True
        noask = True
        buy_quote = cur_quote[cur_quote['side'] == 'buy']
        sell_quote = cur_quote[cur_quote['side'] == 'sell']
        if not buy_quote.empty:
            print(f'{market} bids: {len(buy_quote)}')

            if len(buy_quote) > maxquotes:
                print(f'canceling: {len(buy_quote) - maxquotes}')
                cancel_buys = buy_quote.sort_values(by='price')[:-maxquotes]
                cancel_ids = list(cancel_buys['id'])
                for id in cancel_ids:
                    try:
                        rest.cancel_order(id)
                    except Exception as error:
                        print(error)

            print(f'{market} bids: {len(buy_quote)}')
            cur_bid_id = buy_quote['id'].item()
            cur_bid = buy_quote['price'].item()
            nobid = False
        if not sell_quote.empty:
            print(f'{market} asks: {len(sell_quote)}')

            if len(sell_quote) > maxquotes:
                print(f'canceling: {len(sell_quote) - maxquotes}')
                cancel_sells = sell_quote.sort_values(by='price')[:-maxquotes]
                cancel_ids = list(cancel_sells['id'])
                for id in cancel_ids:
                    try:
                        rest.cancel_order(id)
                    except Exception as error:
                        print(error)

            print(f'{market} asks: {len(sell_quote)}')
            cur_ask_id = sell_quote['id'].item()
            cur_ask = sell_quote['price'].item()
            nobid = False

        # get current inventory
        inventory = pd.DataFrame(rest.get_balances())[
            ['coin', 'usdValue']].set_index('coin').to_dict()['usdValue']
        delta = inventory[market[:-4]]-init_inventory[market[:-4]]

        # get orderbook data and send to market
        bestask = sock.get_orderbook(market)['asks'][0][0]
        bestbid = sock.get_orderbook(market)['bids'][0][0]

        # prepare for quote data
        mid = (bestask+bestbid)/2
        fair = mid + -fade*delta

        # calculate our quote
        our_bid = mid-(sigma*r_vol)
        our_ask = mid+(sigma*r_vol)

        # decide to add/cancel/mod

        # check if bid, otherwise modify
        if nobid:
            try:
                rest.place_order(market, side='buy', price=our_bid,
                                 size=size, post_only=True)
            except Exception as error:
                print(error)
        else:
            try:
                if not cur_bid == our_bid:
                    rest.modify_order(cur_bid_id, price=our_bid)
            except Exception as error:
                print(error)

        # check if ask, otherwise modify
        if noask:
            try:
                rest.place_order(market, side='sell', price=our_ask,
                                 size=size, post_only=True)
            except Exception as error:
                print(error)
        else:
            try:
                if not cur_ask == our_ask:
                    rest.modify_order(cur_ask_id, price=our_ask)
            except Exception as error:
                print(error)
        print(f'time elapsed: {time.time()-start}')
        print(f'{market} | {our_bid} | {mid} | {our_ask} | {np.round(delta, 3)}')
