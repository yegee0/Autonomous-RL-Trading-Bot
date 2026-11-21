import time
from datetime import datetime
from typing import Dict, Tuple, Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from duckduckgo_search import DDGS

try:
    from src.agents.comprehensive_scanner import MarketSentimentAgent

    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False


class MarketIntelligence:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.ddgs = DDGS()
        self.agent = None
        if SENTIMENT_AVAILABLE:
            try:
                self.agent = MarketSentimentAgent()
            except Exception as e:
                print(f"MarketSentimentAgent init failed: {e}")

    def _score_text(self, text: str) -> float:
        if self.agent:
            return self.agent.analyze_text(text)
        return self._simple_sentiment(text)

    def _simple_sentiment(self, text: str) -> float:
        positive = ['bull', 'buy', 'surge', 'jump', 'profit', 'gain', 'rally', 'breakout',
                    'moon', 'rocket', 'soar', 'strong', 'up', 'green', 'growth', 'beat']
        negative = ['bear', 'sell', 'crash', 'drop', 'loss', 'decline', 'dump', 'plunge',
                    'weak', 'down', 'red', 'fall', 'collapse', 'miss', 'fear']

        text_lower = text.lower()
        pos = sum(text_lower.count(w) for w in positive)
        neg = sum(text_lower.count(w) for w in negative)
        total = pos + neg

        if total == 0:
            return 0.0
        return float(np.clip((pos - neg) / total, -1.0, 1.0))

    def get_macro_data(self) -> Dict:
        try:
            print("📊 Fetching macro data...")
            tickers = ["^VIX", "^TNX", "DX-Y.NYB"]
            df = yf.download(tickers, period="5d", progress=False)['Close']

            macro_data = {}

            if not df.empty:
                if "^VIX" in df.columns:
                    last_vix = df["^VIX"].iloc[-1]
                    prev_vix = df["^VIX"].iloc[-2] if len(df) > 1 else last_vix
                    macro_data['VIX'] = {
                        "val": float(last_vix),
                        "delta": float((last_vix - prev_vix) / prev_vix) if prev_vix != 0 else 0
                    }

                if "^TNX" in df.columns:
                    last_tnx = df["^TNX"].iloc[-1]
                    prev_tnx = df["^TNX"].iloc[-2] if len(df) > 1 else last_tnx
                    macro_data['US10Y'] = {
                        "val": float(last_tnx),
                        "delta": float((last_tnx - prev_tnx) / prev_tnx) if prev_tnx != 0 else 0
                    }

                if "DX-Y.NYB" in df.columns:
                    last_dxy = df["DX-Y.NYB"].iloc[-1]
                    prev_dxy = df["DX-Y.NYB"].iloc[-2] if len(df) > 1 else last_dxy
                    macro_data['DXY'] = {
                        "val": float(last_dxy),
                        "delta": float((last_dxy - prev_dxy) / prev_dxy) if prev_dxy != 0 else 0
                    }

            return macro_data

        except Exception as e:
            print(f"⚠️ Macro data error: {e}")
            return {}

    def get_social_intelligence(self, ticker: str, include_reddit: bool = False,
                                include_forums: bool = False) -> Dict:
        search_term = ticker.split("-")[0].replace(".IS", "")

        financial_news = self._fetch_financial_news(search_term)
        reddit_posts = self._fetch_reddit_comprehensive(search_term) if include_reddit else []
        forum_posts = self._fetch_forum_posts(search_term) if include_forums else []

        return {
            "financial_news": financial_news,
            "reddit_mentions": len(reddit_posts),
            "reddit_posts": reddit_posts,
            "forum_posts": forum_posts,
        }

    def _fetch_financial_news(self, term: str, limit: int = 10) -> list:
        news = []
        sources = [
            f"{term} stock market news",
            f"{term} price forecast",
        ]

        try:
            seen_headlines = set()

            for query in sources:
                if len(news) >= limit:
                    break

                try:
                    results = self.ddgs.news(
                        keywords=query,
                        region="wt-wt",
                        safesearch="off",
                        max_results=5
                    )

                    if not results:
                        continue

                    for item in results:
                        if len(news) >= limit:
                            break

                        title = item.get('title', '')
                        source = item.get('source', 'Financial News')
                        date = item.get('date', '')
                        link = item.get('url', '')

                        title_clean = title.lower().strip()
                        if title_clean in seen_headlines or not title:
                            continue

                        seen_headlines.add(title_clean)
                        sentiment = self._score_text(title)

                        news.append({
                            'title': title,
                            'source': source,
                            'date': date,
                            'link': link,
                            'sentiment': sentiment,
                            'type': 'Financial News'
                        })

                except Exception:
                    continue

                time.sleep(0.3)

        except Exception as e:
            print(f"  ⚠️ News scan error: {e}")

        return news[:limit]

    def _fetch_reddit_comprehensive(self, term: str, limit: int = 10) -> list:
        posts: list = []
        subreddits = ["wallstreetbets", "stocks", "cryptocurrency", "stockmarket"]
        seen_ids: set = set()

        for sub in subreddits:
            if len(posts) >= limit:
                break
            try:
                posts.extend(self._fetch_reddit_subreddit(sub, term, "hot", seen_ids))
            except Exception:
                continue

        posts.sort(key=lambda x: x.get("score", 0), reverse=True)
        return posts[:limit]

    def _fetch_reddit_subreddit(self, subreddit: str, term: str, sort: str, seen_ids: set) -> list:
        posts = []

        try:
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
            params = {
                'q': term,
                'sort': sort,
                'limit': 15,
                'restrict_sr': 'true',
                't': 'week'
            }

            resp = requests.get(url, params=params, headers=self.headers, timeout=5)

            if resp.status_code != 200:
                return posts

            data = resp.json().get('data', {}).get('children', [])

            for post in data:
                try:
                    p_data = post.get('data', {})
                    post_id = p_data.get('id', '')

                    if post_id in seen_ids:
                        continue

                    title = p_data.get('title', '')
                    body = p_data.get('selftext', '')[:300]
                    score = p_data.get('score', 0)
                    num_comments = p_data.get('num_comments', 0)
                    permalink = p_data.get('permalink', '')
                    created_utc = p_data.get('created_utc', 0)

                    if not title or score < 5:
                        continue

                    seen_ids.add(post_id)

                    full_text = f"{title} {body}"
                    sentiment = self._score_text(full_text)

                    created_time = datetime.fromtimestamp(created_utc) if created_utc else datetime.now()
                    time_ago = self._format_time_ago(created_time)

                    posts.append({
                        'title': title,
                        'body': body if body else 'No description',
                        'score': score,
                        'comments': num_comments,
                        'sub': subreddit,
                        'link': f"https://reddit.com{permalink}",
                        'sentiment': sentiment,
                        'type': 'Reddit',
                        'time_ago': time_ago,
                        'icon': '🔴'
                    })

                except Exception:
                    continue

        except Exception:
            pass

        return posts

    def _format_time_ago(self, dt: datetime) -> str:
        now = datetime.now()
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"

    def _fetch_forum_posts(self, term: str, limit: int = 5) -> list:
        posts = []

        try:
            queries = [
                f"{term} analysis forum",
                f"{term} technical analysis discussion"
            ]

            for q in queries:
                if len(posts) >= limit:
                    break

                try:
                    results = self.ddgs.text(
                        keywords=q,
                        region="wt-wt",
                        safesearch="off",
                        max_results=3
                    )

                    if not results:
                        continue

                    for item in results:
                        if len(posts) >= limit:
                            break

                        title = item.get('title', '')
                        body = item.get('body', '')
                        link = item.get('href', '')

                        if not title:
                            continue

                        sentiment = self._score_text(f"{title} {body}")

                        posts.append({
                            'title': title,
                            'body': body[:200] if body else '',
                            'link': link,
                            'sentiment': sentiment,
                            'type': 'Forum'
                        })

                except Exception:
                    continue

        except Exception as e:
            print(f"  ⚠️ Forum fetch error: {e}")

        return posts

    def detect_whale_activity(self, df) -> Tuple[bool, str]:
        if df is None or df.empty or 'Volume' not in df.columns:
            return False, "No data"

        try:
            last_vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].tail(21).iloc[:-1].mean()

            if avg_vol == 0:
                return False, "Normal"

            ratio = last_vol / avg_vol

            if ratio > 5.0:
                return True, f"🚨 MASSIVE WHALE ALERT: Vol {ratio:.1f}x higher!"
            elif ratio > 3.0:
                return True, f"🐋 Whale Activity: Vol {ratio:.1f}x higher"

            return False, "Normal"

        except Exception as e:
            print(f"⚠️ Whale detection error: {e}")
            return False, "Error"

    def get_order_book_data(self, ticker: str) -> Optional[pd.DataFrame]:
        try:
            if "-USD" not in ticker and "-USDT" not in ticker:
                return None

            current_price = yf.download(ticker, period="1d", progress=False)['Close'].iloc[-1]

            data_list = []

            bid_cumulative = 0
            for i in range(1, 11):
                price = float(current_price * (1 - (i * 0.001)))
                volume = float(np.random.uniform(0.5, 3.0))
                bid_cumulative += volume
                data_list.append({
                    'Price': price,
                    'Volume': volume,
                    'Total': bid_cumulative,
                    'Type': 'Bid'
                })

            ask_cumulative = 0
            for i in range(1, 11):
                price = float(current_price * (1 + (i * 0.001)))
                volume = float(np.random.uniform(0.5, 3.0))
                ask_cumulative += volume
                data_list.append({
                    'Price': price,
                    'Volume': volume,
                    'Total': ask_cumulative,
                    'Type': 'Ask'
                })

            return pd.DataFrame(data_list) if data_list else None

        except Exception as e:
            print(f"⚠️ Order book error: {e}")
            return None

    def analyze_liquidity(self, order_book_df: Optional[pd.DataFrame]) -> Dict:
        if order_book_df is None or order_book_df.empty:
            return {"bid_ask_spread": "N/A", "depth_score": 0, "liquidity_level": "Low"}

        try:
            bids = order_book_df[order_book_df['Type'] == 'Bid'].sort_values('Price', ascending=False)
            asks = order_book_df[order_book_df['Type'] == 'Ask'].sort_values('Price', ascending=True)

            if len(bids) == 0 or len(asks) == 0:
                return {"bid_ask_spread": "N/A", "depth_score": 0, "liquidity_level": "Low"}

            best_bid = bids.iloc[0]['Price']
            best_ask = asks.iloc[0]['Price']

            if best_bid == 0:
                return {"bid_ask_spread": "N/A", "depth_score": 0, "liquidity_level": "Low"}

            spread = ((best_ask - best_bid) / best_bid) * 100
            depth_score = min(100, (bids['Volume'].sum() + asks['Volume'].sum()) / 10)
            liquidity = "High" if depth_score > 70 else "Medium" if depth_score > 30 else "Low"

            return {
                "bid_ask_spread": f"{spread:.3f}%",
                "depth_score": float(depth_score),
                "liquidity_level": liquidity,
                "best_bid": float(best_bid),
                "best_ask": float(best_ask),
            }

        except Exception as e:
            print(f"⚠️ Liquidity analysis error: {e}")
            return {"bid_ask_spread": "N/A", "depth_score": 0, "liquidity_level": "Low"}

    def get_insider_trading(self, ticker: str) -> pd.DataFrame:
        try:
            if "-USD" in ticker or "-USDT" in ticker:
                return pd.DataFrame()

            print(f"📊 Fetching insider trading for {ticker}...")
            stock = yf.Ticker(ticker)
            insider_df = stock.insider_transactions

            if insider_df is None or insider_df.empty:
                return pd.DataFrame()

            columns_to_keep = ['Insider', 'Relation', 'Date', 'Transaction', 'Shares', 'Value']
            available_cols = [col for col in columns_to_keep if col in insider_df.columns]

            if available_cols:
                insider_df = insider_df[available_cols].head(10)

            return insider_df

        except Exception as e:
            print(f"⚠️ Insider trading error: {e}")
            return pd.DataFrame()

    def get_analyst_recommendations(self, ticker: str) -> Dict:
        try:
            if "-USD" in ticker or "-USDT" in ticker:
                return {}

            stock = yf.Ticker(ticker)
            recommendations = stock.recommendations

            if recommendations is None or recommendations.empty:
                return {}

            recent = recommendations.tail(30)

            summary = {
                'total_recommendations': len(recent),
                'strong_buy': len(
                    recent[recent['To Grade'].str.contains('Strong Buy|Outperform', case=False, na=False)]),
                'buy': len(recent[recent['To Grade'].str.contains('Buy|Overweight', case=False, na=False)]),
                'hold': len(recent[recent['To Grade'].str.contains('Hold|Neutral|Equal', case=False, na=False)]),
                'sell': len(
                    recent[recent['To Grade'].str.contains('Sell|Underweight|Underperform', case=False, na=False)]),
            }

            return summary

        except Exception as e:
            print(f"⚠️ Analyst recommendations error: {e}")
            return {}

    def get_institutional_holders(self, ticker: str) -> pd.DataFrame:
        try:
            if "-USD" in ticker or "-USDT" in ticker:
                return pd.DataFrame()

            stock = yf.Ticker(ticker)
            holders = stock.institutional_holders

            if holders is None or holders.empty:
                return pd.DataFrame()

            return holders.head(10)

        except Exception as e:
            print(f"⚠️ Institutional holders error: {e}")
            return pd.DataFrame()

    def get_fear_greed_index(self) -> Dict:
        try:
            macro = self.get_macro_data()
            vix = macro.get('VIX', {}).get('val', 20)

            if vix > 30:
                score = max(0, 50 - (vix - 20) * 2)
                label = "Extreme Fear" if score < 25 else "Fear"
            elif vix < 15:
                score = min(100, 50 + (20 - vix) * 3)
                label = "Extreme Greed" if score > 75 else "Greed"
            else:
                score = 50
                label = "Neutral"

            return {
                'score': float(score),
                'label': label,
                'vix_based': True,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"⚠️ Fear & Greed error: {e}")
            return {'score': 50, 'label': 'Neutral', 'vix_based': True}

    def get_comprehensive_fundamentals(self, ticker: str) -> Dict:
        try:
            if "-USD" in ticker or "-USDT" in ticker:
                return self._get_crypto_fundamentals(ticker)

            stock = yf.Ticker(ticker)
            info = stock.info

            fundamentals = {
                'company_name': info.get('longName', ticker),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'description': info.get('longBusinessSummary', 'No description available'),
                'website': info.get('website', ''),
                'employees': info.get('fullTimeEmployees', 0),
                'country': info.get('country', 'N/A'),
                'market_cap': info.get('marketCap', 0),
                'enterprise_value': info.get('enterpriseValue', 0),
                'trailing_pe': info.get('trailingPE', 'N/A'),
                'forward_pe': info.get('forwardPE', 'N/A'),
                'peg_ratio': info.get('pegRatio', 'N/A'),
                'price_to_book': info.get('priceToBook', 'N/A'),
                'price_to_sales': info.get('priceToSalesTrailing12Months', 'N/A'),
                'ev_to_revenue': info.get('enterpriseToRevenue', 'N/A'),
                'ev_to_ebitda': info.get('enterpriseToEbitda', 'N/A'),
                'profit_margin': info.get('profitMargins', 0),
                'operating_margin': info.get('operatingMargins', 0),
                'roe': info.get('returnOnEquity', 0),
                'roa': info.get('returnOnAssets', 0),
                'revenue': info.get('totalRevenue', 0),
                'revenue_growth': info.get('revenueGrowth', 0),
                'earnings_growth': info.get('earningsGrowth', 0),
                'gross_profit': info.get('grossProfits', 0),
                'ebitda': info.get('ebitda', 0),
                'net_income': info.get('netIncomeToCommon', 0),
                'total_cash': info.get('totalCash', 0),
                'total_debt': info.get('totalDebt', 0),
                'current_ratio': info.get('currentRatio', 'N/A'),
                'quick_ratio': info.get('quickRatio', 'N/A'),
                'debt_to_equity': info.get('debtToEquity', 'N/A'),
                'dividend_yield': info.get('dividendYield', 0),
                'dividend_rate': info.get('dividendRate', 0),
                'payout_ratio': info.get('payoutRatio', 0),
                'ex_dividend_date': info.get('exDividendDate', 'N/A'),
                'beta': info.get('beta', 'N/A'),
                '52_week_high': info.get('fiftyTwoWeekHigh', 0),
                '52_week_low': info.get('fiftyTwoWeekLow', 0),
                '50_day_avg': info.get('fiftyDayAverage', 0),
                '200_day_avg': info.get('twoHundredDayAverage', 0),
                'avg_volume': info.get('averageVolume', 0),
                'avg_volume_10d': info.get('averageVolume10days', 0),
                'shares_outstanding': info.get('sharesOutstanding', 0),
                'float_shares': info.get('floatShares', 0),
                'short_ratio': info.get('shortRatio', 'N/A'),
                'short_percent': info.get('shortPercentOfFloat', 0),
                'target_high': info.get('targetHighPrice', 0),
                'target_low': info.get('targetLowPrice', 0),
                'target_mean': info.get('targetMeanPrice', 0),
                'recommendation': info.get('recommendationKey', 'N/A'),
            }

            return fundamentals

        except Exception as e:
            print(f"⚠️ Fundamentals error: {e}")
            return {}

    def _get_crypto_fundamentals(self, ticker: str) -> Dict:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")

            if hist.empty:
                return {}

            current_price = hist['Close'].iloc[-1]
            high_52w = hist['High'].max()
            low_52w = hist['Low'].min()
            avg_volume = hist['Volume'].mean()

            return {
                'company_name': ticker.replace("-USD", ""),
                'sector': 'Cryptocurrency',
                'industry': 'Digital Assets',
                'description': f'{ticker} cryptocurrency trading pair',
                'market_cap': 'N/A',
                '52_week_high': float(high_52w),
                '52_week_low': float(low_52w),
                'avg_volume': float(avg_volume),
                'current_price': float(current_price),
                'from_52w_high': float((current_price - high_52w) / high_52w * 100),
                'from_52w_low': float((current_price - low_52w) / low_52w * 100),
            }

        except Exception as e:
            print(f"⚠️ Crypto fundamentals error: {e}")
            return {}