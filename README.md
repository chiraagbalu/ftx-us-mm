# ftx-us-mm
the rest folder establishes the necessary commands for interacting with FTX's REST-API

the websock folder does the same for interacting with the websocket

this market maker is very barebones at the moment, and will probably not make money (or fill trades) in its current state

more importantly, you will need to create a .env file to run anything or send orders

create a file called .env with the variables

API_KEY = <your api key here>

SECRET_KEY = <your secret key here>

in the settings file, fade should be a positive number, 0 at minimum (1 is default)

sigma represents the standard deviations you quote at (if sigma = 1, quote at 1 standard deviation +- the current mid price, not taking inventory into account)