import axios from "axios";
import type {
  AnalyzeResponse,
  BacktestMarker,
  BacktestReport,
  CalendarResponse,
  Candle,
  DriftReport,
  Fundamentals,
  GuardrailSnapshot,
  MacroSnapshot,
  NewsFeed,
  OnChain,
  OptionChainResponse,
  PaperPortfolio,
  PaperTrade,
  PortfolioRiskReport,
  SignalResponse,
  TickerMeta,
} from "./types";

export const http = axios.create({
  baseURL: "/api",
  timeout: 60000,
});

export const api = {
  async tickers(): Promise<TickerMeta[]> {
    const { data } = await http.get<TickerMeta[]>("/tickers");
    return data;
  },

  async analyze(
    ticker: string,
    period = "3mo",
    interval = "1d",
    sentiment = 0
  ): Promise<AnalyzeResponse> {
    const { data } = await http.post<AnalyzeResponse>("/analyze", {
      ticker,
      period,
      interval,
      sentiment,
    });
    return data;
  },

  async signal(ticker: string, period = "1mo", interval = "1d"): Promise<SignalResponse> {
    const { data } = await http.get<SignalResponse>(`/signal/${ticker}`, {
      params: { period, interval },
    });
    return data;
  },

  async price(ticker: string, period = "3mo", interval = "1d", limit = 400): Promise<Candle[]> {
    const { data } = await http.get<Candle[]>(`/price/${ticker}`, {
      params: { period, interval, limit },
    });
    return data;
  },

  async news(ticker: string, limit = 8, reddit = true): Promise<NewsFeed> {
    const { data } = await http.get<NewsFeed>(`/news/${ticker}`, {
      params: { limit, reddit },
    });
    return data;
  },

  async overview(ticker: string): Promise<Fundamentals> {
    const { data } = await http.get<Fundamentals>(`/overview/${ticker}`);
    return data;
  },

  async macro(): Promise<MacroSnapshot> {
    const { data } = await http.get<MacroSnapshot>(`/macro`);
    return data;
  },

  async signalHistory(ticker: string, period = "3mo", interval = "1d", maxBars = 200): Promise<BacktestMarker[]> {
    const { data } = await http.get<BacktestMarker[]>(`/signals/${ticker}/history`, {
      params: { period, interval, max_bars: maxBars },
    });
    return data;
  },

  async backtest(ticker: string, period = "6mo", interval = "1d", maxBars = 400): Promise<BacktestReport> {
    const { data } = await http.get<BacktestReport>(`/backtest/${ticker}`, {
      params: { period, interval, max_bars: maxBars },
      timeout: 120_000,
    });
    return data;
  },

  async paperPortfolio(): Promise<PaperPortfolio> {
    const { data } = await http.get<PaperPortfolio>("/paper/portfolio");
    return data;
  },

  async paperTrades(limit = 50, ticker?: string): Promise<PaperTrade[]> {
    const { data } = await http.get<PaperTrade[]>("/paper/trades", {
      params: { limit, ticker },
    });
    return data;
  },

  async paperTrade(body: { ticker: string; side: "buy" | "sell"; qty: number; price: number }): Promise<PaperTrade> {
    const { data } = await http.post<PaperTrade>("/paper/trade", body);
    return data;
  },

  async paperReset(): Promise<{ status: string; cash: number }> {
    const { data } = await http.post<{ status: string; cash: number }>("/paper/reset");
    return data;
  },

  async guardrails(): Promise<GuardrailSnapshot> {
    const { data } = await http.get<GuardrailSnapshot>("/paper/guardrails");
    return data;
  },

  async guardrailsReset(): Promise<GuardrailSnapshot> {
    const { data } = await http.post<GuardrailSnapshot>("/paper/guardrails/reset");
    return data;
  },

  async drift(ticker: string, period = "1y", interval = "1d"): Promise<DriftReport> {
    const { data } = await http.get<DriftReport>(`/drift/${ticker}`, {
      params: { period, interval },
      timeout: 120_000,
    });
    return data;
  },

  async onchain(ticker: string): Promise<OnChain> {
    const { data } = await http.get<OnChain>(`/onchain/${ticker}`);
    return data;
  },

  async calendar(ticker?: string, hoursAhead = 168): Promise<CalendarResponse> {
    const { data } = await http.get<CalendarResponse>(`/calendar`, {
      params: { ticker, hours_ahead: hoursAhead },
    });
    return data;
  },

  async portfolioRisk(): Promise<PortfolioRiskReport> {
    const { data } = await http.get<PortfolioRiskReport>(`/paper/risk`);
    return data;
  },

  async options(ticker: string, expiry?: string): Promise<OptionChainResponse> {
    const { data } = await http.get<OptionChainResponse>(`/options/${ticker}`, {
      params: expiry ? { expiry } : {},
    });
    return data;
  },
};

export function liveWsUrl(ticker: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/live/${ticker}`;
}
