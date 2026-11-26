from duckduckgo_search import DDGS
from transformers import BertTokenizer, BertForSequenceClassification, pipeline
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple


class MarketSentimentAgent:
    def __init__(self):
        self.nlp = None
        self.tokenizer = None
        self.model = None
        self.cache = {}
        self.cache_timestamp = {}
        self.cache_ttl = 3600  # 1 saat
        self.ddgs = DDGS()

        self._init_models()

    def _init_models(self):
        try:
            self.tokenizer = BertTokenizer.from_pretrained('ProsusAI/finbert')
            self.model = BertForSequenceClassification.from_pretrained('ProsusAI/finbert')
            # Force CPU — some environments have mismatched CUDA (e.g. an older
            # GPU where PyTorch's kernels aren't built), which would otherwise
            # error on every inference call.
            self.nlp = pipeline(
                "sentiment-analysis", model=self.model, tokenizer=self.tokenizer, device=-1
            )
            # Smoke-test once so a broken pipeline falls back now, not later.
            self.nlp("ok")
        except Exception as e:
            print(f"FinBERT init failed, falling back to keyword scorer: {e}")
            self.nlp = None

    def _analyze_with_fallback(self, text: str) -> float:
        positive_words = [
            'bull', 'buy', 'surge', 'jump', 'profit', 'gain', 'outperform',
            'bullish', 'strong', 'up', 'rally', 'breakout', 'momentum',
            'green', 'upside', 'rise', 'recovery', 'beat', 'upgrade',
            'positive', 'excellent', 'strong', 'amazing', 'great'
        ]

        negative_words = [
            'bear', 'sell', 'crash', 'drop', 'loss', 'decline', 'underperform',
            'bearish', 'weak', 'down', 'correction', 'downside', 'bearish',
            'red', 'downside', 'fall', 'collapse', 'miss', 'downgrade',
            'negative', 'poor', 'weak', 'terrible', 'bad'
        ]

        text_lower = text.lower()

        pos_count = sum(text_lower.count(word) for word in positive_words)
        neg_count = sum(text_lower.count(word) for word in negative_words)

        total = pos_count + neg_count
        if total == 0:
            return 0.0

        score = (pos_count - neg_count) / total
        return float(np.clip(score, -1.0, 1.0))

    def analyze_text(self, text: str, use_cache: bool = True) -> float:
        if not text or len(text) == 0:
            return 0.0

        # Cache check
        text_hash = hash(text)
        if use_cache and text_hash in self.cache:
            # Cache TTL kontrol
            if datetime.now().timestamp() - self.cache_timestamp[text_hash] < self.cache_ttl:
                return self.cache[text_hash]

        try:
            # FinBERT kullan
            if self.nlp is not None:
                result = self.nlp(text[:512])[0]
                score = float(result['score'])
                label = result['label']

                if label == 'negative':
                    final_score = -score
                elif label == 'neutral':
                    final_score = 0.0
                else:  # positive
                    final_score = score
            else:
                # Fallback yöntemi
                final_score = self._analyze_with_fallback(text)

            # Cache'e kaydet
            self.cache[text_hash] = final_score
            self.cache_timestamp[text_hash] = datetime.now().timestamp()

            return final_score

        except Exception as e:
            print(f"⚠️ Sentiment analiz hatası (fallback'e geçiyor): {e}")
            try:
                return self._analyze_with_fallback(text)
            except Exception:
                return 0.0

    def batch_analyze(self, texts: List[str]) -> List[float]:
        return [self.analyze_text(text) for text in texts]

    def scan_internet(self, keyword: str, limit: int = 5) -> List[Dict]:
        processed_data = []

        try:
            results = self.ddgs.news(
                keywords=keyword,
                region="wt-wt",
                safesearch="off",
                max_results=limit
            )

            if not results:
                return processed_data

            seen_urls = set()

            for item in results:
                try:
                    title = item.get('title', '')
                    source = item.get('source', 'Web News')
                    date = item.get('date', '')
                    link = item.get('url', item.get('href', '#'))

                    # Duplicate kontrol
                    if link in seen_urls or not title:
                        continue

                    seen_urls.add(link)

                    # Sentiment analiz
                    score = self.analyze_text(title)

                    processed_data.append({
                        'source': source,
                        'title': title,
                        'date': date,
                        'sentiment': score,
                        'link': link,
                        'type': 'News'
                    })

                except Exception as e:
                    print(f"⚠️ Haber işleme hatası: {e}")
                    continue

        except Exception as e:
            print(f"⚠️ İnternet tarama hatası: {e}")

        return processed_data

    def scan_social_media(self, keyword: str, limit: int = 5) -> List[Dict]:
        processed_data = []

        # Twitter ve Reddit'te ara
        social_query = f"{keyword} site:twitter.com OR site:reddit.com"

        try:
            results = self.ddgs.text(
                keywords=social_query,
                region="wt-wt",
                safesearch="off",
                max_results=limit
            )

            if not results:
                return processed_data

            seen_urls = set()

            for item in results:
                try:
                    title = item.get('title', '')
                    body = item.get('body', '')
                    link = item.get('href', '#')

                    # Duplicate kontrol
                    if link in seen_urls or not title:
                        continue

                    seen_urls.add(link)

                    # Platform belirle
                    platform = "Twitter/X" if "twitter.com" in link else "Reddit"

                    # Sentiment
                    full_text = f"{title}. {body}"
                    score = self.analyze_text(full_text)

                    processed_data.append({
                        'source': platform,
                        'title': body[:100] + "..." if body else title,
                        'date': 'Now',
                        'sentiment': score,
                        'link': link,
                        'type': 'Social'
                    })

                except Exception as e:
                    print(f"⚠️ Sosyal medya işleme hatası: {e}")
                    continue

        except Exception as e:
            print(f"⚠️ Sosyal medya tarama hatası: {e}")

        return processed_data

    def get_market_mood(self, ticker: str) -> Tuple[float, pd.DataFrame]:
        print(f"📊 {ticker} için piyasa duygusu analiz ediliyor...")
        # Haber tarama
        news_data = self.scan_internet(f"{ticker} finance news", limit=8)

        # Sosyal medya tarama
        social_data = self.scan_social_media(f"${ticker} trading", limit=5)

        # Birleştir
        all_data = news_data + social_data

        if not all_data:
            return 0.0, pd.DataFrame()

        df = pd.DataFrame(all_data)

        # Ortalama sentiment
        avg_score = df['sentiment'].mean()

        print(f"✅ Analiz tamamlandı: {len(all_data)} kaynak, Sentiment: {avg_score:.2f}")

        return float(avg_score), df

    def clear_cache(self):
        self.cache = {}
        self.cache_timestamp = {}
        print("✅ Cache temizlendi")
