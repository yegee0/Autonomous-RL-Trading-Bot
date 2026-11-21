# Autonomous-RL-Trading-Bot

This project is a professional-grade autonomous trading assistant that combines Reinforcement Learning, Technical Analysis, and Market Sentiment Analysis. The system scans market data, calculates advanced technical indicators, and generates AI-driven buy/sell signals.

## Key Features

* **PPO-Based Decision Engine:** Autonomous decision-making using deep neural networks trained with the Stable Baselines3 PPO algorithm.
* **Market Intelligence:** Real-time financial news scanning, Reddit discussion tracking, and sentiment analysis using FinBERT.
* **Advanced Risk Management:** Implementation of Kelly Criterion, Volatility Scaling, and dynamic Position Sizing to protect capital.
* **Integrated Alert System:** Real-time push notifications of AI decisions and trading signals via Telegram.
* **Live Paper Trading:** Strategy testing using live market data within a simulated paper trading environment.

## Technical Stack

* **RL Environment:** Custom Gymnasium implementation (StockTradingEnv).
* **Data Source:** Real-time and historical price data provided via yfinance.
* **Technical Indicators:** Calculation of RSI, MACD, Bollinger Bands, ATR, OBV, and other quantitative metrics.
* **UI/UX:** Interactive dashboard built with Streamlit and advanced financial charting using Plotly.

## Quick Start

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
## Technical Notes and Usage

* **Execution Command:** The command `streamlit run app/app.py` initializes a local web server and triggers essential setup functions such as `apply_styles()` and `init_session_state()` within the main application file.
* **Dependencies:** It is critical that all libraries listed in `requirements.txt`—specifically `stable-baselines3` and `torch`—are installed correctly to prevent errors during model loading in `rl_agent.py`.
* **Sidebar Integration:** The user interface utilizes sidebar components for core functionalities including model training (`train_agent`), asset selection, and Telegram notification configuration via the `SignalBroadcaster`.
* **Directory Structure:** The application expects a specific directory structure for saving and loading AI models; specifically, it utilizes the `models/trained/` path for storing `.zip` and `.pkl` files.
