"""
visualization.py - GELIŞTIRILMIŞ VERSIYON v3.0
✅ Advanced charting
✅ Depth chart (order book)
✅ Performance metrics
✅ Error handling
✅ Fixed hoverinfo issues
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import textwrap
import numpy as np
import pandas as pd
from typing import Optional


def plot_advanced_chart(df, show_tech=True, show_volume=True):
    """
    İleri seviye OHLC + teknik analiz şeması

    Parameters:
    -----------
    df : pd.DataFrame
        OHLCV + indikatörler
    show_tech : bool
        Teknik indikatörleri göster
    show_volume : bool
        Volume göster
    """

    if df is None or df.empty:
        st.error("❌ Veri yok")
        return

    try:
        # Subplot oluştur: 3 satır, 1 sütun
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.6, 0.2, 0.2],
            subplot_titles=('Price', 'Volume', 'RSI')
        )

        # ============ CANDLESTICK (OHLC) ============
        # FIX: hoverinfo='x+ohlc' yerine 'all' veya kaldırıyoruz
        fig.add_trace(
            go.Candlestick(
                x=df['Date'],
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='OHLC',
                increasing_line_color='#0ECB81',
                decreasing_line_color='#F6465D',
            ),
            row=1, col=1
        )

        # ============ TEKNİK İNDİKATÖRLER ============
        if show_tech:
            # SMA20
            if 'SMA20' in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df['Date'],
                        y=df['SMA20'],
                        line=dict(color='orange', width=2),
                        name='SMA20',
                        hovertemplate='SMA20: %{y:.2f}<extra></extra>'
                    ),
                    row=1, col=1
                )

            # SMA50
            if 'SMA50' in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df['Date'],
                        y=df['SMA50'],
                        line=dict(color='blue', width=1.5),
                        name='SMA50',
                        hovertemplate='SMA50: %{y:.2f}<extra></extra>'
                    ),
                    row=1, col=1
                )

            # Bollinger Bands
            if 'BB_Upper' in df.columns and 'BB_Lower' in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df['Date'],
                        y=df['BB_Upper'],
                        line=dict(color='gray', dash='dot', width=1),
                        showlegend=False,
                        hovertemplate='BB Upper: %{y:.2f}<extra></extra>'
                    ),
                    row=1, col=1
                )

                fig.add_trace(
                    go.Scatter(
                        x=df['Date'],
                        y=df['BB_Lower'],
                        line=dict(color='gray', dash='dot', width=1),
                        fill='tonexty',
                        fillcolor='rgba(128,128,128,0.1)',
                        showlegend=False,
                        hovertemplate='BB Lower: %{y:.2f}<extra></extra>'
                    ),
                    row=1, col=1
                )

        # ============ VOLUME ============
        if show_volume and 'Volume' in df.columns:
            # Renk: yeşil (yükseliş) / kırmızı (düşüş)
            colors = []
            for i in range(len(df)):
                if df.iloc[i]['Close'] >= df.iloc[i]['Open']:
                    colors.append('#0ECB81')
                else:
                    colors.append('#F6465D')

            fig.add_trace(
                go.Bar(
                    x=df['Date'],
                    y=df['Volume'],
                    marker_color=colors,
                    showlegend=False,
                    name='Volume',
                    hovertemplate='Volume: %{y:,.0f}<extra></extra>'
                ),
                row=2, col=1
            )

        # ============ RSI ============
        if 'RSI' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['Date'],
                    y=df['RSI'],
                    line=dict(color='purple', width=2),
                    name='RSI (14)',
                    hovertemplate='RSI: %{y:.1f}<extra></extra>'
                ),
                row=3, col=1
            )

            # Overbought/Oversold lines
            fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)

        # ============ LAYOUT ============
        fig.update_layout(
            height=700,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            title_text="Advanced Market Analysis",
            paper_bgcolor='rgba(30,35,41,1)',
            plot_bgcolor='rgba(30,35,41,0.5)',
            font=dict(color='#EAECEF'),
            margin=dict(l=50, r=50, t=80, b=50),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # Y axis labels
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        fig.update_yaxes(title_text="RSI", row=3, col=1)

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Chart hatası: {str(e)}")


def render_ai_decision_card(action, confidence, sentiment_score, ticker):
    """
    AI karar kartı (renkli, responsive)

    Parameters:
    -----------
    action : int
        0-6 arası action
    confidence : float
        0-1 arası confidence
    sentiment_score : float
        -1 ile 1 arasında sentiment
    ticker : str
        Sembol
    """

    try:
        # Action'u int'e çevir
        if hasattr(action, '__iter__'):
            action = int(action[0])
        else:
            action = int(action)

        # Action'u signal'e çevir
        action_signals = {
            0: ("HOLD / NEUTRAL", "signal-hold", "⸟", "#FCD535", "Market direction uncertain"),
            1: ("WEAK BUY", "signal-buy", "🚀", "#0ECB81", "AI suggests accumulation (25%)"),
            2: ("STRONG BUY", "signal-buy", "🚀", "#0ECB81", "AI suggests accumulation (50%)"),
            3: ("VERY STRONG BUY", "signal-buy", "🚀", "#0ECB81", "AI suggests accumulation (100%)"),
            4: ("WEAK SELL", "signal-sell", "📉", "#F6465D", "AI suggests reducing position (25%)"),
            5: ("STRONG SELL", "signal-sell", "📉", "#F6465D", "AI suggests reducing position (50%)"),
            6: ("VERY STRONG SELL", "signal-sell", "📉", "#F6465D", "AI suggests reducing position (100%)"),
        }

        s_text, s_class, s_icon, s_glow, desc = action_signals.get(action, (
            "UNKNOWN", "signal-hold", "?", "#FCD535", "Unknown signal"))

        # HTML Card
        html_code = textwrap.dedent(f"""
            <div class="ai-decision-card" style="border-left: 5px solid {s_glow};">
              <div class="decision-left">
                <span class="sub-text">🤖 AI SIGNAL</span>
                <div class="{s_class} signal-badge" style="font-size: 24px;">
                  {s_icon} {s_text}
                </div>
                <p class="sub-text" style="margin-top:5px;">{desc}</p>
              </div>

              <div class="decision-right">
                <div class="stat-box">
                  <span class="stat-label">AI CONFIDENCE</span>
                  <span class="stat-value" style="color: {s_glow};">{confidence * 100:.1f}%</span>
                </div>
                <div class="stat-box">
                  <span class="stat-label">SENTIMENT SCORE</span>
                  <span class="stat-value">{sentiment_score:+.2f}</span>
                </div>
              </div>
            </div>
        """)

        st.markdown(html_code, unsafe_allow_html=True)

        # TradingView Linki
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            trade_url = f"https://www.tradingview.com/chart/?symbol={ticker}"
            st.link_button(
                f"📊 Analyze {ticker} on TradingView",
                trade_url,
                type="primary",
                use_container_width=True
            )

    except Exception as e:
        st.error(f"❌ Decision card hatası: {str(e)}")


def plot_depth_chart(order_book_df):
    """
    Order Book Depth Chart (Bids/Asks)

    Parameters:
    -----------
    order_book_df : pd.DataFrame
        Order book verileri
    """

    # Validasyonlar
    if order_book_df is None:
        st.info("📈 Order Book analizi crypto varlıklar için (BTC-USD, ETH-USD, vb)")
        return

    if not isinstance(order_book_df, pd.DataFrame):
        st.warning("⚠️ Geçersiz order book veri formatı")
        return

    if order_book_df.empty:
        st.info("📈 Order Book verisi yok")
        return

    required_cols = ['Type', 'Price', 'Total']
    if not all(col in order_book_df.columns for col in required_cols):
        st.warning(f"⚠️ Gerekli sütunlar eksik: {required_cols}")
        return

    try:
        # Veriyi ayır - robust filtering
        bid_data = order_book_df[
            order_book_df['Type'].str.contains('Bid', case=False, na=False, regex=False)
        ].copy()
        ask_data = order_book_df[
            order_book_df['Type'].str.contains('Ask', case=False, na=False, regex=False)
        ].copy()

        if bid_data.empty or ask_data.empty:
            st.info("📈 Eksik order book verisi (Bids ve Asks lazım)")
            return

        # Numeric dönüştür
        bid_data['Price'] = pd.to_numeric(bid_data['Price'], errors='coerce')
        bid_data['Total'] = pd.to_numeric(bid_data['Total'], errors='coerce')
        ask_data['Price'] = pd.to_numeric(ask_data['Price'], errors='coerce')
        ask_data['Total'] = pd.to_numeric(ask_data['Total'], errors='coerce')

        # NaN'ları kaldır
        bid_data = bid_data.dropna(subset=['Price', 'Total'])
        ask_data = ask_data.dropna(subset=['Price', 'Total'])

        if bid_data.empty or ask_data.empty:
            st.warning("⚠️ Geçerli order book verisi yok")
            return

        # Graph oluştur
        fig = go.Figure()

        # Bids (Yeşil) - Alıcılar
        fig.add_trace(
            go.Scatter(
                x=bid_data['Price'].values,
                y=bid_data['Total'].values,
                mode='lines',
                fill='tozeroy',
                name='Bids (Buyers)',
                line=dict(color='#0ECB81', width=2),
                fillcolor='rgba(14, 203, 129, 0.3)',
                hovertemplate='<b>Price:</b> $%{x:.2f}<br><b>Volume:</b> %{y:.2f}<extra></extra>'
            )
        )

        # Asks (Kırmızı) - Satıcılar
        fig.add_trace(
            go.Scatter(
                x=ask_data['Price'].values,
                y=ask_data['Total'].values,
                mode='lines',
                fill='tozeroy',
                name='Asks (Sellers)',
                line=dict(color='#F6465D', width=2),
                fillcolor='rgba(246, 70, 93, 0.3)',
                hovertemplate='<b>Price:</b> $%{x:.2f}<br><b>Volume:</b> %{y:.2f}<extra></extra>'
            )
        )

        # Layout
        fig.update_layout(
            title="📊 Market Depth (Order Book)",
            xaxis_title="Price (USD)",
            yaxis_title="Cumulative Volume",
            template="plotly_dark",
            height=400,
            hovermode="x unified",
            paper_bgcolor="rgba(30,35,41,1)",
            plot_bgcolor="rgba(30,35,41,0.5)",
            font=dict(color="#EAECEF", size=11),
            margin=dict(l=50, r=50, t=50, b=50),
        )

        st.plotly_chart(fig, use_container_width=True)

        st.caption("🎯 Green area = Buyers (Bids) | Red area = Sellers (Asks)")

    except Exception as e:
        st.error(f"❌ Depth chart hatası: {str(e)}")
        print(f"DEBUG: {type(e).__name__}: {e}")


def plot_backtest_results(report):
    """
    Backtest sonuçlarını görselleştir

    Parameters:
    -----------
    report : Dict
        Backtest raporu
    """

    if not report:
        st.warning("⚠️ Backtest sonucu yok")
        return

    try:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Total Return",
                f"{report.get('Total Return %', 0):.2f}%"
            )

        with col2:
            st.metric(
                "Sharpe Ratio",
                f"{report.get('Sharpe Ratio', 0):.2f}"
            )

        with col3:
            st.metric(
                "Max Drawdown",
                f"{report.get('Max Drawdown %', 0):.2f}%"
            )

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Win Rate",
                f"{report.get('Win Rate %', 0):.1f}%"
            )

        with col2:
            st.metric(
                "Final Balance",
                f"${report.get('Final Balance', 0):,.0f}"
            )

    except Exception as e:
        st.error(f"❌ Backtest visualize hatası: {str(e)}")


def plot_equity_curve(equity_values, prices=None):
    """
    Equity curve (net worth) şeması

    Parameters:
    -----------
    equity_values : list/array
        Net worth zaman serisi
    prices : list/array
        Fiyat zaman serisi (karşılaştırma için)
    """

    if not equity_values:
        st.warning("⚠️ Equity verisi yok")
        return

    try:
        fig = go.Figure()

        # Equity curve
        fig.add_trace(
            go.Scatter(
                y=equity_values,
                mode='lines',
                name='Equity',
                line=dict(color='#0ECB81', width=2),
                fill='tozeroy',
                fillcolor='rgba(14, 203, 129, 0.2)',
                hovertemplate='$%{y:,.0f}<extra></extra>'
            )
        )

        # Buy & Hold karşılaştırması
        if prices is not None and len(prices) > 0:
            initial_price = prices[0]
            bh_equity = [initial_price * (p / initial_price) * 10000 for p in prices]

            fig.add_trace(
                go.Scatter(
                    y=bh_equity,
                    mode='lines',
                    name='Buy & Hold',
                    line=dict(color='#F6465D', width=2, dash='dash'),
                    hovertemplate='$%{y:,.0f}<extra></extra>'
                )
            )

        fig.update_layout(
            title="📈 Equity Curve",
            yaxis_title="Net Worth ($)",
            xaxis_title="Days",
            template="plotly_dark",
            height=400,
            hovermode="x unified",
            paper_bgcolor="rgba(30,35,41,1)",
            plot_bgcolor="rgba(30,35,41,0.5)",
            font=dict(color="#EAECEF"),
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Equity curve hatası: {str(e)}")


def plot_correlation_heatmap(corr_matrix, title="Correlation Matrix"):
    """
    Korelasyon matrisi heatmap

    Parameters:
    -----------
    corr_matrix : pd.DataFrame
        Korelasyon matrisi
    title : str
        Başlık
    """

    try:
        import plotly.express as px

        fig = px.imshow(
            corr_matrix,
            text_auto=True,
            template="plotly_dark",
            aspect="auto",
            color_continuous_scale="RdBu",
            zmin=-1, zmax=1
        )

        fig.update_layout(
            title=title,
            height=500,
            paper_bgcolor='rgba(30,35,41,1)',
            plot_bgcolor='rgba(30,35,41,0.5)',
            font=dict(color='#EAECEF')
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Heatmap hatası: {str(e)}")


def plot_returns_distribution(returns, title="Returns Distribution"):
    """
    Getiri dağılımı histogramı

    Parameters:
    -----------
    returns : pd.Series
        Getiri serisi
    title : str
        Başlık
    """

    try:
        import plotly.express as px

        fig = px.histogram(
            returns,
            nbins=50,
            title=title,
            template="plotly_dark"
        )

        fig.update_layout(
            xaxis_title="Return",
            yaxis_title="Frequency",
            paper_bgcolor='rgba(30,35,41,1)',
            plot_bgcolor='rgba(30,35,41,0.5)',
            font=dict(color='#EAECEF')
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Histogram hatası: {str(e)}")


if __name__ == "__main__":
    print("✅ visualization.py yüklendi")
    print("Functions:")
    print("  - plot_advanced_chart()")
    print("  - render_ai_decision_card()")
    print("  - plot_depth_chart()")
    print("  - plot_backtest_results()")
    print("  - plot_equity_curve()")
    print("  - plot_correlation_heatmap()")
    print("  - plot_returns_distribution()")