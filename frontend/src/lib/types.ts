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
}

export interface SignalResponse {
  ticker: string;
  action: number;
  action_label: ActionLabel;
  confidence: number;
  direction: Direction;
  source: "ppo" | "fallback";
  sentiment: number;
  price: number;
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
