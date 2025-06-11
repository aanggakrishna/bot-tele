from datetime import datetime, timedelta

class TradeState:
    def __init__(self, max_open_positions=2):
        self.max_open_positions = max_open_positions
        self.positions = []  # list of dict: ca, buy_price, buy_time

    def can_buy(self):
        return len(self.positions) < self.max_open_positions

    def bought(self, ca, buy_price):
        self.positions.append({
            "ca": ca,
            "buy_price": buy_price,
            "buy_time": datetime.utcnow()
        })

    def sold(self, ca):
        self.positions = [pos for pos in self.positions if pos["ca"] != ca]

    async def check_positions(self, get_price_func, sell_func, dm_func):
        now = datetime.utcnow()
        for pos in self.positions[:]:
            ca = pos["ca"]
            buy_price = pos["buy_price"]
            buy_time = pos["buy_time"]
            current_price = await get_price_func(ca)

            if not current_price:
                continue

            change_pct = (current_price - buy_price) / buy_price * 100

            if change_pct >= 100:
                sell_func(ca)
                self.sold(ca)
                await dm_func(f"🎯 SELL TP {ca} profit {change_pct:.2f}%")

            elif change_pct <= -52:
                sell_func(ca)
                self.sold(ca)
                await dm_func(f"🔻 SELL SL {ca} loss {change_pct:.2f}%")

            elif now - buy_time > timedelta(days=1):
                sell_func(ca)
                self.sold(ca)
                await dm_func(f"🕰 SELL timeout {ca} >1 hari")
