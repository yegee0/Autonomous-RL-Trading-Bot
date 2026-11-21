import time
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.comprehensive_scanner import MarketSentimentAgent
from src.utils.data_loader import fetch_data
from src.utils.technical_indicators import add_advanced_indicators
from src.utils.visualization import plot_advanced_chart, render_ai_decision_card, plot_depth_chart
from src.utils.risk_manager import calculate_risk_metrics, calculate_position_sizing, get_advanced_signals
from src.agents.market_intelligence import MarketIntelligence
from src.agents.rl_agent import load_agent, train_agent, get_ai_action, calculate_fallback_signal
from src.config import apply_styles, init_session_state
from src.utils.alerts_manager import AlertsManager, SignalBroadcaster, TradingSignal, SignalType

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


@st.cache_data(ttl=300)
def get_cached_news(ticker):
    """Cache news for 5 minutes"""
    intel = MarketIntelligence()
    return intel.get_social_intelligence(ticker)


@st.cache_data(ttl=300)
def get_cached_sentiment(ticker):
    """Cache sentiment for 5 minutes"""
    try:
        agent = MarketSentimentAgent()
        clean_term = ticker.split("-")[0].replace(".IS", "")
        score, df = agent.get_market_mood(clean_term)
        return score
    except Exception as e:
        print(f"Sentiment fetch error: {e}")
        return 0.0


@st.cache_data(ttl=600)
def get_cached_fundamentals(ticker):
    """Cache fundamentals for 10 minutes"""
    intel = MarketIntelligence()
    return intel.get_comprehensive_fundamentals(ticker)


@st.cache_data(ttl=300)
def get_cached_macro():
    """Cache macro data for 5 minutes"""
    intel = MarketIntelligence()
    return intel.get_macro_data()


def get_fresh_price_data(ticker, period, interval):
    """Always fetch fresh price data - no cache"""
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data is None or data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        data.reset_index(inplace=True)
        if 'Datetime' in data.columns:
            data.rename(columns={'Datetime': 'Date'}, inplace=True)
        return data
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None


def train_one_ticker_in_app(ticker, total_timesteps):
    model_path = train_agent(ticker, total_timesteps=total_timesteps, use_streamlit=True)
    return model_path


def send_telegram_signal(ticker, action, confidence, sentiment, price, rsi=50, macd=0, chat_id=None):
    """Send trading signal to Telegram"""
    if not chat_id:
        chat_id = st.session_state.get('telegram_chat_id', '')

    if not chat_id or not TELEGRAM_TOKEN:
        return False

    try:
        broadcaster = SignalBroadcaster(TELEGRAM_TOKEN, chat_id)
        return broadcaster.broadcast_from_action(
            ticker=ticker,
            action=action,
            confidence=confidence,
            sentiment=sentiment,
            price=price,
            rsi=rsi,
            macd=macd,
            force=False
        )
    except Exception as e:
        print(f"Telegram send error: {e}")
        return False


def live_step_logic(ticker, sentiment_score):
    """Live simulation (Paper Trading) step logic"""
    try:
        live_data = yf.download(ticker, period="1d", interval="1m", progress=False)
        if live_data.empty:
            st.error("Live data fetch failed.")
            return

        current_price = float(live_data['Close'].iloc[-1])
        current_time = datetime.now().strftime("%H:%M:%S")

        action, confidence = get_ai_action(ticker, current_price, sentiment_score)

        cash = st.session_state.live_cash
        shares = st.session_state.live_shares

        trade_log = ""

        if action in [1, 2, 3]:
            buy_pct = {1: 0.25, 2: 0.50, 3: 1.0}[action]
            usd_amount = cash * buy_pct
            if usd_amount > 10:
                shares_bought = usd_amount / current_price
                st.session_state.live_cash -= usd_amount
                st.session_state.live_shares += shares_bought
                trade_log = f"BUY {buy_pct * 100}%"

        elif action in [4, 5, 6]:
            sell_pct = {4: 0.25, 5: 0.50, 6: 1.0}[action]
            if shares > 0:
                shares_sold = shares * sell_pct
                usd_amount = shares_sold * current_price
                st.session_state.live_cash += usd_amount
                st.session_state.live_shares -= shares_sold
                trade_log = f"SELL {sell_pct * 100}%"
        else:
            trade_log = "HOLD"

        net_worth = st.session_state.live_cash + (st.session_state.live_shares * current_price)

        st.session_state.live_history.append({
            "time": current_time,
            "price": current_price,
            "action": trade_log,
            "net_worth": net_worth
        })
        st.session_state.live_history = st.session_state.live_history[-500:]

        if st.session_state.get('auto_telegram', False) and action != st.session_state.get('last_action'):
            send_telegram_signal(ticker, action, confidence, sentiment_score, current_price)
            st.session_state['last_action'] = action

    except Exception as e:
        st.error(f"Live Loop Error: {e}")


st.set_page_config(
    page_title="TradeMaster",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="expanded"
)

apply_styles()
init_session_state()

with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 20px 0;'>
            <h1 style='color: #FCD535; margin: 0;'>📊 TradeMaster</h1>
            <p style='color: #848E9C; font-size: 12px; margin-top: 5px;'>AI-Powered Trading Intelligence</p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("### 🎯 Asset Selection")
    ticker_input = st.text_input("Enter Ticker Symbol", value="BTC-USD",
                                 help="Examples: BTC-USD, AAPL, TSLA, THYAO.IS").upper()

    col1, col2 = st.columns(2)
    with col1:
        timeframe = st.selectbox("Timeframe", ["1d", "1wk", "1mo"], index=0)
    with col2:
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=3)

    col_btn, col_auto = st.columns([1, 1])
    with col_btn:
        run_btn = st.button("RUN ONCE", type="primary", use_container_width=True)
    with col_auto:
        auto_mode = st.toggle("AUTO-PILOT", value=False, help="Refreshes every 60s")

    if auto_mode:
        st.info(f"Auto-Pilot Active: Scanning {ticker_input}...")
        st.session_state['auto_mode'] = True
    else:
        st.session_state['auto_mode'] = False

    st.markdown("---")

    st.markdown("### 🧪 AI Training")
    train_ticker = st.selectbox("Select ticker to train",
                                ["BTC-USD", "AAPL", "TSLA", "THYAO.IS"], index=0)
    timesteps = st.number_input("Total timesteps", min_value=10_000, value=100_000, step=10_000)

    safe_ticker = train_ticker.replace(".", "_").replace("-", "_")
    model_path_check = os.path.join("models", "trained", f"model_{safe_ticker}.zip")
    model_exists = os.path.exists(model_path_check)

    if model_exists:
        st.warning(f"⚠️ Model for {train_ticker} exists!")
        if st.button("♻️ Retrain Model", use_container_width=True):
            with st.status("🧠 Training started...", expanded=True) as status:
                res = train_one_ticker_in_app(train_ticker, int(timesteps))
                if res:
                    status.update(label="✅ Training Complete!", state="complete")
    else:
        if st.button("🚀 Train New Model", use_container_width=True):
            with st.status("🧠 Training started...", expanded=True) as status:
                res = train_one_ticker_in_app(train_ticker, int(timesteps))
                if res:
                    status.update(label="✅ Training Complete!", state="complete")

    st.markdown("---")

    st.markdown("### 🔔 Telegram Settings")
    telegram_chat = st.text_input("Chat ID", key="tg_chat",
                                  help="Get from @userinfobot on Telegram")
    auto_telegram = st.toggle("Auto-send (≥70%)", value=False)

    if telegram_chat:
        st.session_state['telegram_chat_id'] = telegram_chat
        st.session_state['auto_telegram'] = auto_telegram

should_run = run_btn or st.session_state.get('auto_mode', False)

show_tech = True
show_volume = True

if should_run:
    st.session_state.analyzed = True
    st.session_state['ticker_input'] = ticker_input

    with st.status(f"🔄 AI Agent Scanning: {ticker_input}...", expanded=True) as status:

        st.write("🔍 Fetching real-time market data...")
        df_new = get_fresh_price_data(ticker_input, period=period, interval=timeframe)

        if df_new is None:
            status.update(label="❌ Error: Data Unavailable", state="error")
            st.error("❌ Ticker not found or data unavailable.")
            st.stop()
        else:
            st.write("🌍 Loading cached intelligence data...")
            try:
                macro_data = get_cached_macro()
                social_data = get_cached_news(ticker_input)
                fund_info = get_cached_fundamentals(ticker_input)

                intel = MarketIntelligence()
                order_book_df = intel.get_order_book_data(ticker_input)
                liquidity_data = intel.analyze_liquidity(order_book_df)
                is_whale, whale_msg = intel.detect_whale_activity(df_new)

            except Exception as e:
                print(f"Intel Error: {e}")
                macro_data, social_data, liquidity_data = {}, {}, {}
                order_book_df = None
                fund_info = {}
                is_whale, whale_msg = False, ""

            st.write("📐 Calculating technical indicators...")
            df_new = add_advanced_indicators(df_new)

            st.write("⚖️ Performing risk analysis...")
            risk_metrics = calculate_risk_metrics(df_new)

            st.write("📰 Loading cached sentiment...")
            sentiment_score = get_cached_sentiment(ticker_input)

            st.write("🤖 Generating AI signal...")
            signals, signal_score, avg_conf, conf_scores = get_advanced_signals(df_new)

            current_price = float(df_new.iloc[-1]['Close'])
            current_rsi = float(df_new.iloc[-1].get('RSI', 50))
            current_macd = float(df_new.iloc[-1].get('MACD', 0))

            model, vecnorm_env = load_agent(ticker_input)

            if model and not df_new.empty:
                try:
                    action_pred, conf_pred = get_ai_action(ticker_input, current_price, sentiment_score)
                    ai_action = action_pred
                    ai_confidence = conf_pred
                except Exception as e:
                    print(f"Model Prediction Error: {e}")
                    ai_action, ai_confidence = calculate_fallback_signal(df_new, sentiment_score)
            else:
                ai_action, ai_confidence = calculate_fallback_signal(df_new, sentiment_score)

            if st.session_state.get('auto_telegram', False) and ai_confidence >= 0.70:
                chat_id = st.session_state.get('telegram_chat_id', '')
                if chat_id:
                    send_telegram_signal(
                        ticker_input, ai_action, ai_confidence, sentiment_score,
                        current_price, current_rsi, current_macd, chat_id
                    )

            status.update(label="✅ Analysis Complete", state="complete", expanded=False)

    st.session_state.update({
        'current_ticker': ticker_input,
        'macro_data': macro_data,
        'social_data': social_data,
        'order_book_df': order_book_df,
        'liquidity_data': liquidity_data,
        'fund_info': fund_info,
        'df': df_new,
        'sentiment_score': sentiment_score,
        'signal_score': signal_score,
        'signals': signals,
        'avg_conf': avg_conf,
        'ai_action': ai_action,
        'ai_confidence': ai_confidence,
        'risk_metrics': risk_metrics,
        'is_whale': is_whale,
        'whale_msg': whale_msg
    })

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🎯 MAIN SIGNAL", "📊 TECHNICAL", "📰 INTELLIGENCE", "📈 RISK",
        "💰 FUNDAMENTALS", "🔗 CORRELATIONS", "📉 LIVE TRADING", "🔔 ALERTS"
    ])

    with tab1:
        st.markdown("<h2 style='text-align: center;'>AI Trading Signal</h2>", unsafe_allow_html=True)

        if ai_action is not None:
            render_ai_decision_card(ai_action, ai_confidence, sentiment_score, ticker_input)
        else:
            st.warning("⚠️ No AI Model found for this asset. Please train a model in the sidebar first.")

        st.markdown("---")

        current_balance = st.session_state.get('balance', 10000.0)
        eff_conf = ai_confidence if ai_confidence > 0 else 0.5
        risk_data = calculate_position_sizing(df_new, current_balance, confidence=eff_conf)

        if risk_data:
            st.subheader("🛡️ Trade Setup (Risk Management)")
            r1, r2, r3 = st.columns(3)
            with r1:
                st.info(f"💰 **Size:** ${risk_data.get('position_size_usd', 0):,.2f}")
            with r2:
                st.error(f"🛑 **Stop:** ${risk_data.get('stop_loss', 0):.2f}")
            with r3:
                st.success(f"🎯 **Target:** ${risk_data.get('take_profit', 0):.2f}")

        if macro_data:
            st.markdown("### 🌍 Macro Context")
            m1, m2, m3 = st.columns(3)
            m1.metric("VIX", f"{macro_data.get('VIX', {}).get('val', 0):.2f}")
            m2.metric("US10Y", f"{macro_data.get('US10Y', {}).get('val', 0):.2f}%")
            m3.metric("DXY", f"{macro_data.get('DXY', {}).get('val', 0):.2f}")

        if is_whale:
            st.warning(f"🐋 WHALE ALERT: {whale_msg}")

    with tab2:
        plot_advanced_chart(df_new, show_tech=show_tech, show_volume=show_volume)

        c1, c2, c3 = st.columns(3)
        c1.metric("RSI (14)", f"{df_new.iloc[-1]['RSI']:.2f}")
        c2.metric("MACD", f"{df_new.iloc[-1]['MACD']:.4f}")
        c3.metric("ATR", f"{df_new.iloc[-1]['ATR']:.4f}")

    with tab3:
        st.markdown("""
            <div class="news-section">
                <div class="news-header">📰 Financial News</div>
            </div>
        """, unsafe_allow_html=True)

        news_items = social_data.get('financial_news', [])
        if news_items:
            for n in news_items[:8]:
                sent_class = "positive" if n['sentiment'] > 0.1 else "negative" if n['sentiment'] < -0.1 else "neutral"
                sent_emoji = "🟢" if n['sentiment'] > 0.1 else "🔴" if n['sentiment'] < -0.1 else "⚪"
                st.markdown(f"""
                    <div class="news-card {sent_class}">
                        <span class="news-source-badge">{n['source']}</span>
                        <h4>{sent_emoji} <a href="{n['link']}" target="_blank" style="color: #EAECEF; text-decoration: none;">{n['title']}</a></h4>
                        <span>Sentiment: {n['sentiment']:.2f}</span>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No recent news found.")

        st.markdown("---")

        st.markdown("""
            <div class="reddit-section">
                <div class="reddit-header">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="#FF4500" style="vertical-align: middle; margin-right: 8px;">
                        <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
                    </svg>
                    Reddit Discussions
                </div>
            </div>
        """, unsafe_allow_html=True)

        reddit_items = social_data.get('reddit_posts', [])
        if reddit_items:
            for r in reddit_items[:5]:
                sent_emoji = "🟢" if r.get('sentiment', 0) > 0.1 else "🔴" if r.get('sentiment', 0) < -0.1 else "⚪"
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, rgba(255, 69, 0, 0.08) 0%, rgba(255, 90, 10, 0.03) 100%); 
                                border-left: 3px solid #FF4500; padding: 12px; border-radius: 6px; margin: 8px 0;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                            <span style="background: #FF4500; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">
                                r/{r.get('sub', 'unknown')}
                            </span>
                            <span style="color: #848E9C; font-size: 11px;">⬆️ {r.get('score', 0)} • 💬 {r.get('comments', 0)} • {r.get('time_ago', '')}</span>
                        </div>
                        <a href="{r.get('link', '#')}" target="_blank" style="color: #EAECEF; text-decoration: none; font-weight: 500;">
                            {sent_emoji} {r.get('title', 'No title')}
                        </a>
                        <p style="color: #848E9C; font-size: 12px; margin-top: 6px;">{r.get('body', '')[:150]}...</p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No Reddit discussions found.")

        if order_book_df is not None:
            st.markdown("---")
            st.subheader("📊 Market Depth")
            plot_depth_chart(order_book_df)

    with tab4:
        st.subheader("📈 Risk Metrics")
        rm1, rm2, rm3, rm4 = st.columns(4)
        rm1.metric("Sharpe Ratio", f"{risk_metrics.get('sharpe_ratio', 0):.2f}")
        rm2.metric("Sortino Ratio", f"{risk_metrics.get('sortino_ratio', 0):.2f}")
        rm3.metric("Max Drawdown", f"{risk_metrics.get('max_drawdown', 0) * 100:.2f}%")
        rm4.metric("Volatility", f"{risk_metrics.get('volatility', 0) * 100:.2f}%")

        st.markdown("### 📊 Daily Returns (Last 50 Days)")
        returns = df_new['Close'].pct_change().tail(50)
        fig_returns = go.Figure()
        colors = ['#0ECB81' if r >= 0 else '#F6465D' for r in returns]
        fig_returns.add_trace(go.Bar(y=returns, marker_color=colors, name='Returns'))
        fig_returns.update_layout(
            template="plotly_dark",
            height=300,
            paper_bgcolor='rgba(30,35,41,1)',
            plot_bgcolor='rgba(30,35,41,0.5)'
        )
        st.plotly_chart(fig_returns, use_container_width=True)

    with tab5:
        st.subheader(f"🏢 {fund_info.get('company_name', ticker_input)}")

        if fund_info:
            col_info1, col_info2 = st.columns(2)

            with col_info1:
                st.markdown("### 📋 Company Overview")
                st.write(fund_info.get('description', 'No description available.')[:500] + "...")

                info_data = {
                    "Sector": fund_info.get('sector', 'N/A'),
                    "Industry": fund_info.get('industry', 'N/A'),
                    "Country": fund_info.get('country', 'N/A'),
                    "Employees": f"{fund_info.get('employees', 0):,}" if fund_info.get('employees') else 'N/A',
                    "Website": fund_info.get('website', 'N/A'),
                }
                for k, v in info_data.items():
                    st.markdown(f"**{k}:** {v}")

            with col_info2:
                st.markdown("### 💵 Market Data")
                market_cap = fund_info.get('market_cap', 0)
                if isinstance(market_cap, (int, float)) and market_cap > 0:
                    if market_cap >= 1e12:
                        mc_str = f"${market_cap / 1e12:.2f}T"
                    elif market_cap >= 1e9:
                        mc_str = f"${market_cap / 1e9:.2f}B"
                    elif market_cap >= 1e6:
                        mc_str = f"${market_cap / 1e6:.2f}M"
                    else:
                        mc_str = f"${market_cap:,.0f}"
                else:
                    mc_str = "N/A"

                st.metric("Market Cap", mc_str)

                mc1, mc2 = st.columns(2)
                mc1.metric("52W High", f"${fund_info.get('52_week_high', 0):,.2f}")
                mc2.metric("52W Low", f"${fund_info.get('52_week_low', 0):,.2f}")

            st.markdown("---")
            st.markdown("### 📊 Valuation Metrics")

            val1, val2, val3, val4 = st.columns(4)
            val1.metric("P/E (TTM)", f"{fund_info.get('trailing_pe', 'N/A')}")
            val2.metric("P/E (FWD)", f"{fund_info.get('forward_pe', 'N/A')}")
            val3.metric("PEG Ratio", f"{fund_info.get('peg_ratio', 'N/A')}")
            val4.metric("P/B Ratio", f"{fund_info.get('price_to_book', 'N/A')}")

            val5, val6, val7, val8 = st.columns(4)
            val5.metric("P/S Ratio", f"{fund_info.get('price_to_sales', 'N/A')}")
            val6.metric("EV/Revenue", f"{fund_info.get('ev_to_revenue', 'N/A')}")
            val7.metric("EV/EBITDA", f"{fund_info.get('ev_to_ebitda', 'N/A')}")
            val8.metric("Beta", f"{fund_info.get('beta', 'N/A')}")

            st.markdown("---")
            st.markdown("### 💰 Financial Performance")

            fin1, fin2, fin3, fin4 = st.columns(4)

            profit_margin = fund_info.get('profit_margin', 0)
            pm_str = f"{profit_margin * 100:.1f}%" if isinstance(profit_margin, (int, float)) else 'N/A'
            fin1.metric("Profit Margin", pm_str)

            op_margin = fund_info.get('operating_margin', 0)
            om_str = f"{op_margin * 100:.1f}%" if isinstance(op_margin, (int, float)) else 'N/A'
            fin2.metric("Operating Margin", om_str)

            roe = fund_info.get('roe', 0)
            roe_str = f"{roe * 100:.1f}%" if isinstance(roe, (int, float)) else 'N/A'
            fin3.metric("ROE", roe_str)

            roa = fund_info.get('roa', 0)
            roa_str = f"{roa * 100:.1f}%" if isinstance(roa, (int, float)) else 'N/A'
            fin4.metric("ROA", roa_str)

            st.markdown("---")
            st.markdown("### 📈 Growth Metrics")

            gr1, gr2, gr3 = st.columns(3)

            rev_growth = fund_info.get('revenue_growth', 0)
            rg_str = f"{rev_growth * 100:.1f}%" if isinstance(rev_growth, (int, float)) else 'N/A'
            gr1.metric("Revenue Growth", rg_str)

            earn_growth = fund_info.get('earnings_growth', 0)
            eg_str = f"{earn_growth * 100:.1f}%" if isinstance(earn_growth, (int, float)) else 'N/A'
            gr2.metric("Earnings Growth", eg_str)

            div_yield = fund_info.get('dividend_yield', 0)
            dy_str = f"{div_yield * 100:.2f}%" if isinstance(div_yield, (int, float)) and div_yield else 'N/A'
            gr3.metric("Dividend Yield", dy_str)

            st.markdown("---")
            st.markdown("### 🎯 Analyst Targets")

            tgt1, tgt2, tgt3, tgt4 = st.columns(4)
            tgt1.metric("Target High", f"${fund_info.get('target_high', 0):,.2f}")
            tgt2.metric("Target Mean", f"${fund_info.get('target_mean', 0):,.2f}")
            tgt3.metric("Target Low", f"${fund_info.get('target_low', 0):,.2f}")
            tgt4.metric("Recommendation", fund_info.get('recommendation', 'N/A').upper())

        else:
            st.info("Fundamentals data not available for this asset.")

    with tab6:
        st.write("Calculating correlations against BTC, ETH, Gold, SPX...")
        try:
            comps = [ticker_input, "BTC-USD", "GC=F", "^GSPC"]
            comp_data = yf.download(comps, period="3mo")['Close']
            corr = comp_data.corr()
            fig_corr = px.imshow(corr, text_auto=True, template="plotly_dark", zmin=-1, zmax=1,
                                 color_continuous_scale="RdBu")
            fig_corr.update_layout(
                paper_bgcolor='rgba(30,35,41,1)',
                plot_bgcolor='rgba(30,35,41,0.5)'
            )
            st.plotly_chart(fig_corr, use_container_width=True)
        except Exception as e:
            print(f"Correlation error: {e}")
            st.error("Could not fetch correlation data.")

    with tab7:
        st.subheader("⚡ Live Paper Trading Simulation")

        lt_col1, lt_col2 = st.columns(2)
        live_active = st.session_state.get('live_enabled', False)

        with lt_col1:
            if st.button("▶ START LIVE SESSION", disabled=live_active, key="start_live"):
                st.session_state.live_enabled = True

        with lt_col2:
            if st.button("⏹ STOP SESSION", disabled=not live_active, key="stop_live"):
                st.session_state.live_enabled = False

        col_wallet, col_shares = st.columns(2)
        with col_wallet:
            st.metric("Paper Wallet", f"${st.session_state.live_cash:,.2f}")
        with col_shares:
            st.metric("Shares Held", f"{st.session_state.live_shares:.4f}")

        if st.session_state.live_history:
            st.dataframe(pd.DataFrame(st.session_state.live_history).iloc[::-1], use_container_width=True)

        if st.session_state.get('live_enabled', False):
            with st.spinner("Processing next tick..."):
                s_score = st.session_state.get('sentiment_score', 0)
                live_step_logic(ticker_input, s_score)
                time.sleep(3)
                st.rerun()

    with tab8:
        st.subheader("📢 Signal Notifications")

        chat_id = st.session_state.get('telegram_chat_id', '')

        if chat_id:
            st.success(f"✅ Telegram connected (Chat ID: {chat_id})")

            st.info(f"Current AI Confidence: **{ai_confidence * 100:.1f}%** (Min 70% required)")

            if ai_confidence >= 0.70:
                if st.button("📢 Send Signal Now", key="send_signal_btn"):
                    success = send_telegram_signal(
                        ticker_input, ai_action or 0, ai_confidence,
                        sentiment_score, current_price, current_rsi, current_macd, chat_id
                    )
                    if success:
                        st.success("✅ Signal sent!")
                    else:
                        st.error("❌ Failed")
            else:
                st.warning("⚠️ Confidence below 70% - Signal disabled")
        else:
            st.warning("⚠️ Enter Telegram Chat ID in sidebar first")
            st.markdown("""
            **How to get Chat ID:**
            1. Message `@userinfobot` on Telegram
            2. Copy the ID number it gives you
            3. Paste in sidebar under "Telegram Settings"
            """)

        st.markdown("---")
        st.markdown("### 📜 Signal History")

        last_entry = st.session_state['signal_history'][-1] if st.session_state['signal_history'] else None
        new_entry = {
            'time': datetime.now().strftime("%H:%M:%S"),
            'ticker': ticker_input,
            'action': ai_action,
            'confidence': ai_confidence,
            'sentiment': sentiment_score
        }
        if last_entry is None or (
            last_entry.get('ticker') != new_entry['ticker']
            or last_entry.get('action') != new_entry['action']
        ):
            st.session_state['signal_history'].append(new_entry)
            st.session_state['signal_history'] = st.session_state['signal_history'][-100:]

        if st.session_state['signal_history']:
            df_history = pd.DataFrame(st.session_state['signal_history'][-20:])
            st.dataframe(df_history.iloc[::-1], use_container_width=True)

else:
    st.markdown("""
    <div style='text-align: center; padding: 50px; background-color: #1E2329; border-radius: 10px;'>
        <h1 style='color: #FCD535;'>🚀 TradeMaster AI v3.0</h1>
        <p>Advanced Institutional-Grade Trading Assistant</p>
        <p style='font-size: 12px; color: #848E9C;'>Select a ticker on the left and click 'RUN ONCE' to start.</p>
    </div>
    """, unsafe_allow_html=True)

if st.session_state.get('auto_mode', False):
    time.sleep(60)
    st.rerun()