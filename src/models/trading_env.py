import gymnasium as gym
import numpy as np
from gymnasium import spaces


class StockTradingEnv(gym.Env):
    def __init__(self, df):
        super().__init__()
        self.balance = None
        self.current_step = None
        self.net_worth = None
        self.shares_held = None
        self.df = df.reset_index(drop=True)
        self.initial_balance = 10000.0

        # 0: Hold
        # 1: Buy %25, 2: Buy %50, 3: Buy %100
        # 4: Sell %25, 5: Sell %50, 6: Sell %100
        self.action_space = spaces.Discrete(7)

        # [Balance, Shares, Price, Sentiment, RSI, MACD, ATR]
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(7,), dtype=np.float32)

        self.max_steps = len(self.df) - 1
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.balance = float(self.initial_balance)
        self.shares_held = 0.0
        self.current_step = 0
        self.net_worth = float(self.initial_balance)
        return self._next_observation(), {}

    def _next_observation(self):
        idx = min(self.current_step, self.max_steps)

        current_price = float(self.df.loc[idx, "Close"])
        sentiment = float(self.df.loc[idx, "sentiment"]) if "sentiment" in self.df.columns else 0.0
        rsi = float(self.df.loc[idx, "RSI"])
        macd = float(self.df.loc[idx, "MACD"])
        atr = float(self.df.loc[idx, "ATR"])

        return np.array(
            [self.balance, self.shares_held, current_price, sentiment, rsi, macd, atr],
            dtype=np.float32
        )

    def step(self, action):
        commission_rate = 0.001

        idx = min(self.current_step, self.max_steps)
        current_price = float(self.df.loc[idx, "Close"])
        atr = float(self.df.loc[idx, "ATR"])

        # ---- Execute trade (commission ONLY once, via cash) ----
        if action in (1, 2, 3):  # BUY
            frac = {1: 0.25, 2: 0.50, 3: 1.0}[action]
            cost = self.balance * frac
            if cost > 10:  # min trade
                total_cost = cost * (1.0 + commission_rate)
                if self.balance >= total_cost:
                    self.balance -= total_cost
                    self.shares_held += cost / current_price

        elif action in (4, 5, 6):  # SELL
            if self.shares_held > 0:
                frac = {4: 0.25, 5: 0.50, 6: 1.0}[action]
                shares_to_sell = self.shares_held * frac
                proceeds = shares_to_sell * current_price * (1.0 - commission_rate)
                self.shares_held -= shares_to_sell
                self.balance += proceeds

        # ---- advance time ----
        self.current_step += 1
        terminated = self.current_step >= self.max_steps

        # ---- mark-to-market with NEXT price ----
        next_idx = min(self.current_step, self.max_steps)
        next_price = float(self.df.loc[next_idx, "Close"])

        new_net_worth = self.balance + self.shares_held * next_price
        profit = new_net_worth - self.net_worth

        # risk penalty (optional)
        risk_penalty = (atr * 0.1) if self.shares_held > 0 else 0.0

        reward = profit - risk_penalty
        self.net_worth = new_net_worth

        obs = self._next_observation()
        info = {"net_worth": float(self.net_worth)}
        return obs, float(reward), terminated, False, info
