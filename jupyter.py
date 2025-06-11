import requests

JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"

def get_quote(input_mint, output_mint, amount):
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": amount,
        "slippageBps": 50,  # 0.5% slippage
    }
    response = requests.get(JUPITER_QUOTE_URL, params=params)
    response.raise_for_status()
    return response.json()

def get_swap(swap_params):
    response = requests.post(JUPITER_SWAP_URL, json=swap_params)
    response.raise_for_status()
    return response.json()
