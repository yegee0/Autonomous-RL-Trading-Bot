import streamlit as st


def apply_styles():
    st.markdown("""
    <style>
        /* 1. Google Fonts Import - IBM Plex Sans */
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

        /* 2. Global Font Settings */
        html, body, [class*="css"] {
            font-family: 'IBM Plex Sans', sans-serif !important;
            color: #EAECEF;
        }

        /* 3. Container Adjustments */
        .block-container { padding-top: 3rem; padding-bottom: 3rem; }

        /* 4. Binance Color Palette */
        :root {
            --binance-black: #1E2329;
            --binance-dark-grey: #2B3139;
            --binance-green: #0ECB81;
            --binance-red: #F6465D;
            --binance-yellow: #FCD535;
            --text-primary: #EAECEF;
            --text-secondary: #848E9C;
        }

        /* 5. Metrics Cards */
        .stMetric {
            background-color: var(--binance-black);
            padding: 15px;
            border-radius: 4px;
            border: 1px solid var(--binance-dark-grey);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stMetric label { color: var(--text-secondary) !important; font-weight: 500; }
        .stMetric [data-testid="stMetricValue"] { font-weight: 600; color: var(--text-primary); }

        /* 6. AI Decision Card (Custom Design) */
        .ai-decision-card {
            background-color: var(--binance-black);
            border: 1px solid var(--binance-dark-grey);
            border-radius: 8px;
            padding: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        }

        .decision-left {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            border-right: 1px solid var(--binance-dark-grey);
            padding-right: 30px;
            min-width: 200px;
        }

        .decision-right {
            flex-grow: 1;
            padding-left: 30px;
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }

        .signal-badge {
            font-size: 28px;
            font-weight: 700;
            padding: 8px 16px;
            border-radius: 4px;
            letter-spacing: 0.5px;
            display: inline-block;
            margin-bottom: 8px;
        }

        .signal-buy { color: var(--binance-green); background: rgba(14, 203, 129, 0.1); }
        .signal-sell { color: var(--binance-red); background: rgba(246, 70, 93, 0.1); }
        .signal-hold { color: var(--binance-yellow); background: rgba(252, 213, 53, 0.1); }

        .sub-text {
            color: var(--text-secondary);
            font-size: 14px;
            margin: 0;
        }

        .stat-box {
            background: #252A30;
            padding: 10px;
            border-radius: 4px;
        }
        .stat-label { color: var(--text-secondary); font-size: 12px; display: block; margin-bottom: 4px; }
        .stat-value { color: var(--text-primary); font-size: 16px; font-weight: 600; }

        /* 7. Buttons */
        .stButton>button {
            background-color: var(--binance-yellow);
            color: #1E2329;
            font-weight: 600;
            border: none;
            border-radius: 4px;
            height: 40px;
            transition: all 0.3s ease;
        }
        .stButton>button:hover { background-color: #FDD157; color: black; border: none; transform: translateY(-2px);}

        /* 8. Tab Settings */
        .stTabs [data-baseweb="tab-list"] { gap: 20px; border-bottom: 1px solid var(--binance-dark-grey); }
        .stTabs [data-baseweb="tab"] { font-family: 'IBM Plex Sans'; color: var(--text-secondary); }
        .stTabs [aria-selected="true"] { color: var(--binance-yellow) !important; font-weight: 600; border-bottom-color: var(--binance-yellow) !important; }

        /* 9. News Cards */
        .news-card {
            background-color: var(--binance-black);
            padding: 18px;
            border-radius: 8px;
            margin-bottom: 12px;
            border-left: 4px solid #555;
            border: 1px solid var(--binance-dark-grey);
        }
        .news-card.positive { border-left-color: var(--binance-green); }
        .news-card.negative { border-left-color: var(--binance-red); }
        .news-card.neutral { border-left-color: var(--binance-yellow); }
        .news-card h4 { margin: 0; font-size: 15px; color: var(--text-primary); font-weight: 600; }
        .news-card span { font-size: 11px; color: var(--text-secondary); }

        /* 10. Signal Cards */
        .signal-card {
            background: var(--binance-dark-grey);
            padding: 12px;
            border-radius: 6px;
            margin: 8px 0;
            border-left: 4px solid;
        }

        /* Risk Indicator */
        .risk-indicator {
            display: inline-block;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin: 5px;
        }
        .risk-low { background: rgba(14, 203, 129, 0.2); color: var(--binance-green); }
        .risk-medium { background: rgba(252, 213, 53, 0.2); color: var(--binance-yellow); }
        .risk-high { background: rgba(246, 70, 93, 0.2); color: var(--binance-red); }

        /* 11. Reddit Section Styling */
        .reddit-section {
            background: linear-gradient(135deg, rgba(255, 69, 0, 0.05) 0%, rgba(255, 90, 10, 0.02) 100%);
            border-left: 4px solid #FF4500;
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
        }
        .reddit-header {
            color: #FF4500;
            font-weight: bold;
            font-size: 18px;
            margin-bottom: 10px;
        }

        /* 12. Financial News Section Styling */
        .news-section {
            background: linear-gradient(135deg, rgba(30, 144, 255, 0.05) 0%, rgba(65, 105, 225, 0.02) 100%);
            border-left: 4px solid #1E90FF;
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
        }
        .news-header {
            color: #1E90FF;
            font-weight: bold;
            font-size: 18px;
            margin-bottom: 10px;
        }
        .news-source-badge {
            display: inline-block;
            background: rgba(30, 144, 255, 0.2);
            color: #1E90FF;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            margin: 4px 4px 4px 0;
        }
    </style>
    """, unsafe_allow_html=True)


def init_session_state():
    defaults = {
        'balance': 100000.0,
        'portfolio': {},
        'last_price': 0.0,
        'trade_history': [],
        'initial_balance': 100000.0,
        'analyzed': False,

        'live_cash': 10_000.0,
        'live_shares': 0.0,
        'live_history': [],
        'last_bar_ts': None,
        'live_enabled': False,
        'bh_start_price': None,
        'no_new_bar_count': 0,
        'last_action': None,
        'last_net': None,

        'signal_history': [],
        'ai_action': None,
        'ai_confidence': 0.0,
        'current_ticker': None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
