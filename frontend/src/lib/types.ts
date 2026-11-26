export type AssetClass = "crypto" | "stock" | "bist";

export type ActionLabel =
  | "HOLD"
  | "BUY_25"
  | "BUY_50"
  | "BUY_100"
  | "SELL_25"
  | "SELL_50"
  | "SELL_100";

export type Direction = "long" | "short" | "flat";

export interface TickerMeta {
  symbol: string;
  name: string;
  asset_class: AssetClass;
  model_available: boolean;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Indicators {
  rsi?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  atr?: number | null;
  sma20?: number | null;
  sma50?: number | null;
  bb_upper?: number | null;
  bb_lower?: number | null;
  stoch_k?: number | null;
  stoch_d?: number | null;
  volume_ratio?: number | null;
}

export interface SignalResponse {
  ticker: string;
  action: number;
  action_label: ActionLabel;
  confidence: number;
  direction: Direction;
  source: "ppo" | "fallback" | "ensemble";
  sentiment: number;
  price: number;
  regime?: "trend" | "range" | "crisis" | null;
  expert?: string | null;
}

export interface RiskMetrics {
  volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown: number;
  var_95: number;
}

export interface PositionSizing {
  position_size_usd: number;
  position_size_pct: number;
  stop_loss: number;
  take_profit: number;
  kelly_fraction: number;
}

export interface NewsItem {
  title: string;
  source: string;
  link: string;
  sentiment: number;
  time_ago?: string | null;
}

export interface RedditPost {
  title: string;
  body?: string;
  score: number;
  comments: number;
  sub: string;
  link: string;
  sentiment: number;
  time_ago?: string | null;
}

export interface NewsFeed {
  news: NewsItem[];
  reddit: RedditPost[];
  avg_sentiment: number;
}

export interface MacroMetric {
  value: number;
  delta: number;
}

export interface MacroSnapshot {
  vix?: MacroMetric | null;
  us10y?: MacroMetric | null;
  dxy?: MacroMetric | null;
  fear_greed?: number | null;
  fear_greed_label?: string | null;
}

export interface Fundamentals {
  company_name?: string | null;
  sector?: string | null;
  industry?: string | null;
  description?: string | null;
  website?: string | null;
  country?: string | null;
  market_cap?: number | null;
  trailing_pe?: number | null;
  forward_pe?: number | null;
  price_to_book?: number | null;
  profit_margin?: number | null;
  roe?: number | null;
  revenue?: number | null;
  revenue_growth?: number | null;
  earnings_growth?: number | null;
  dividend_yield?: number | null;
  beta?: number | null;
  fifty_two_week_high?: number | null;
  fifty_two_week_low?: number | null;
  target_mean?: number | null;
  recommendation?: string | null;
  is_crypto: boolean;
}

export interface AnalyzeResponse {
  ticker: string;
  price: number;
  candles: Candle[];
  indicators: Indicators;
  signal: SignalResponse;
  risk: RiskMetrics;
  sizing: PositionSizing;
  news: NewsItem[];
  sentiment_score: number;
}

export interface LiveKline {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: boolean;
}

export interface BacktestMarker {
  time: number;
  kind: "buy" | "sell";
  price: number;
}

export interface BacktestReport {
  ticker: string;
  source: "ppo" | "fallback";
  initial_balance: number;
  final_equity: number;
  total_return: number;
  buy_hold_return: number;
  outperformance: number;
  sharpe: number;
  volatility: number;
  max_drawdown: number;
  total_trades: number;
  equity_curve: number[];
  markers: BacktestMarker[];
  bars: number;
}

export interface PaperPosition {
  ticker: string;
  qty: number;
  avg_cost: number;
  market_value?: number | null;
  unrealized_pnl?: number | null;
}

export interface PaperTrade {
  id: number;
  ts: number;
  ticker: string;
  side: "buy" | "sell";
  qty: number;
  price: number;
  fee: number;
}

export interface PaperPortfolio {
  cash: number;
  positions: PaperPosition[];
  total_market_value: number;
  total_equity: number;
}

export interface GuardrailSnapshot {
  kill_switch_active: boolean;
  kill_switch_file: string;
  kill_switch_file_exists: boolean;
  daily_loss_tripped: boolean;
  day_start_equity: number;
  day_key: string | null;
  rate_hits_in_window: number;
  rate_limit_max: number;
  rate_limit_window_s: number;
  limits: {
    max_position_pct: number;
    max_order_pct: number;
    max_daily_loss_pct: number;
    rsi_buy_block: number;
    rsi_sell_block: number;
  };
}

export interface OnChain {
  symbol: string;
  funding_rate: number | null;
  funding_annualized: number | null;
  next_funding_time: number | null;
  mark_price: number | null;
  open_interest: number | null;
  open_interest_usd: number | null;
  oi_change_24h: number | null;
  crowded_side: "long" | "short" | "neutral" | null;
}

export interface CalendarEvent {
  ts: number;
  name: string;
  impact: "high" | "medium" | "low" | string;
  affects: string;
  source: "macro" | "earnings" | string;
}

export interface CalendarResponse {
  events: CalendarEvent[];
  event_window_active: boolean;
  active_event: CalendarEvent | null;
}

export interface OptionRow {
  strike: number;
  last: number;
  bid: number;
  ask: number;
  volume: number;
  open_interest: number;
  implied_vol: number;
}

export interface OptionChainResponse {
  ticker: string;
  expiry: string;
  spot: number;
  calls: OptionRow[];
  puts: OptionRow[];
  atm_iv: number | null;
  skew_25d: number | null;
  put_call_oi: number | null;
  expiries: string[];
}

export interface PortfolioRiskReport {
  equity: number;
  cash: number;
  market_value: number;
  gross_exposure_pct: number;
  net_exposure_pct: number;
  concentration_pct: number;
  var_95_parametric: number;
  var_95_historical: number;
  portfolio_vol_annualized: number;
  correlations: Record<string, Record<string, number>>;
  tickers: string[];
  warnings: string[];
}

export interface DriftReport {
  ok: boolean;
  reason?: string;
  ticker?: string;
  bars?: number;
  drift_score?: number;
  level?: "ok" | "watch" | "retrain";
  return_drift?: number;
  policy_drift?: number;
  pnl_drift?: number;
  baseline?: {
    mean: number;
    std: number;
    skew: number;
    buy_pct: number;
    sell_pct: number;
    total_return: number;
  };
  recent?: {
    mean: number;
    std: number;
    skew: number;
    buy_pct: number;
    sell_pct: number;
    total_return: number;
  };
}
