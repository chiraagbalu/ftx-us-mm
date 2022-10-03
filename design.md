# Design Doc

## Initializing
Import libraries
Import API libraries
Import keys

Connect to Rest Client - static call/response
Connect to Websocket Client - connect to stream

Set up atexit - cancel all orders on exit

Open Settings file - get markets to trade

Get current inventory - initial USD, initial value in each coin
Define how much money is being allocated to each market (usd_per)

For each coin, buy or sell such that our initial inventory is roughly 50% asset, 50% USD (to enable quoting a 2 sided market)

USD_PER = total/(2*markets)

total = 3000
markets = 3
3000/6 -> 500
rebalance to 500 long of {asset}
if already 400 long asset, purchase 500-400 = 100 of asset
if already 600 long asset, sell 600-500 = 100 of asset

Place Initial Orders far away from current market - to adjust during quoting

## Trading loop
### Per Loop
Load settings file to get most up-to-date settings
Call API to get current open orders

## Per Market
Get time to check time taken

Get parameters from settings file

Calculate realized vol - to adjust size of spread

Rvol = stdv of close data

Close = 1300
STDV = 1
RVOL = 1

Get our current quote info
If we have excess buy/sell quotes, delete the wider ones (more likely stale)
^TODO: change above to sort by createdAt

Get our current bid/ask quote price as well as ID, for adjustment later

Get current inventory - to calculate delta (are we net long/short)

Delta: (current USD value long - initial USD value long)/initial USD value long
example:
init: 500$
current: 600$
(600-500)/500 -> 20% (positive = long)

init: 500$
current: 1000$
total per market: init
1000-500/500 -> 100% long

Get orderbook data (best bid/ask) to calculate mid

Adjust fair using our current inventory (fair starts as mid, adjusted up/down to get more fills long/short to balance inventory towards 0)

Fair = Mid * (1+(-Fade*Delta))
Delta = 0.2 (600 current, 500 init)
Fade = 0.001 (arbitrary)
Mid = 35

Fair = 35 * (1+(-0.001*0.2))
Fair = 35 * (1+(-0.0002))
Fair = 35 * (0.9998)

Fair gets lower when we are net long, to get more fills short
Fair get higher when we are net short, to get more fills long

Calculate desired quote based on realized vol and our fair value

Bid = Fair - rVol * sigma 
Ask = Fair + rVol * sigma

Fair = 1300, rVol = 1, sigma = 2 (quote 2 stdv)

Bid = 1298
Ask = 1302

If the quote is too tight, adjust the quote to be the min tick size of the market

If we have no bid/ask (filled/canceled) then replace the bid/ask

If we have a bid/ask then modify the bid/ask if it is different from our current bid/ask 

Print out market data for monitoring delta, fair value, our quotes, pnl


