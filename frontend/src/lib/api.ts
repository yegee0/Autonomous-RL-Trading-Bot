import axios from "axios";
import type {
  AnalyzeResponse,
  BacktestMarker,
  BacktestReport,
  Candle,
  NewsItem,
  PaperPortfolio,
  PaperTrade,
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

  async analyze(ticker: string, period = "3mo", interval = "1d"): Promise<AnalyzeResponse> {
    const { data } = await http.post<AnalyzeResponse>("/analyze", {
      ticker,
      period,
      interval,
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

  async news(ticker: string, limit = 8): Promise<NewsItem[]> {
    const { data } = await http.get<NewsItem[]>(`/news/${ticker}`, { params: { limit } });
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
};

export function liveWsUrl(ticker: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/live/${ticker}`;
}
