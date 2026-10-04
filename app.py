import streamlit as st
import pandas as pd
import math
import os

# スマホでも見やすい中央寄せレイアウト
st.set_page_config(page_title="Poker Rating Dashboard", page_icon="♠️", layout="centered")

st.title("♠️ Poker Rating Dashboard")
st.markdown("戦績と強さ（レーティング）を可視化する公式ダッシュボードです。")

DATA_FILE = "data/results.csv"
INITIAL_RATING = 1000
K_FACTOR = 300

@st.cache_data(ttl=5)
def load_and_calc_ratings():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    df = pd.read_csv(DATA_FILE)
    if df.empty:
        return df, pd.DataFrame(), pd.DataFrame()

    ratings = {}
    history = []

    games = df.groupby(['Date', 'Round'])
    
    for (date, round_num), game_df in games:
        total_game_chips = game_df['TotalGameChips'].iloc[0]
        current_game_ratings = {}
        for player in game_df['Player']:
            if player not in ratings:
                ratings[player] = INITIAL_RATING
            current_game_ratings[player] = ratings[player]
        
        sum_expected = sum([math.pow(10, r / 400.0) for r in current_game_ratings.values()])
        
        for _, row in game_df.iterrows():
            player = row['Player']
            final_chips = row['FinalChips']
            actual_share = final_chips / total_game_chips if total_game_chips > 0 else 0
            expected_share = math.pow(10, current_game_ratings[player] / 400.0) / sum_expected
            delta_r = K_FACTOR * (actual_share - expected_share)
            
            ratings[player] += delta_r
            
            history.append({
                'Date': date,
                'Round': round_num,
                'Player': player,
                'FinalChips': final_chips,
                'ActualShare(%)': actual_share * 100,
                'DeltaRating': delta_r,
                'NewRating': ratings[player]
            })
    
    history_df = pd.DataFrame(history)
    
    summary_data = []
    for player, rating in ratings.items():
        player_history = history_df[history_df['Player'] == player]
        summary_data.append({
            'Player': player,
            'Rating': rating,
            'GamesPlayed': len(player_history),
            'HighestRating': player_history['NewRating'].max() if not player_history.empty else rating
        })
    
    summary_df = pd.DataFrame(summary_data).sort_values('Rating', ascending=False).reset_index(drop=True)
    return df, history_df, summary_df

df_raw, df_history, df_summary = load_and_calc_ratings()

if df_summary.empty:
    st.info("データがありません。")
else:
    # ランクメダルの付与
    def get_medal(rank):
        if rank == 1: return "🥇"
        if rank == 2: return "🥈"
        if rank == 3: return "🥉"
        return f"{rank}位"

    df_summary['ランク'] = (df_summary.index + 1).map(get_medal)
    df_summary['Rating'] = df_summary['Rating'].round(1)
    df_summary['HighestRating'] = df_summary['HighestRating'].round(1)
    
    # スマホで見やすいようにタブで分割
    tab1, tab2, tab3 = st.tabs(["🏆 ランキング", "📈 レート推移", "🔥 最新ゲーム分析"])
    
    with tab1:
        st.subheader("総合レーティングランキング")
        display_cols = ['ランク', 'Player', 'Rating', 'GamesPlayed', 'HighestRating']
        rename_dict = {
            'Player': 'プレイヤー',
            'Rating': '現在のレート',
            'GamesPlayed': '参加回数',
            'HighestRating': '過去最高レート'
        }
        st.dataframe(df_summary[display_cols].rename(columns=rename_dict), use_container_width=True)
        
    with tab2:
        st.subheader("プレイヤーのレート推移")
        if not df_history.empty:
            chart_data = pd.DataFrame()
            for player in df_summary['Player']:
                p_hist = df_history[df_history['Player'] == player].reset_index(drop=True)
                p_hist.index = p_hist.index + 1
                chart_data[player] = p_hist['NewRating']
            st.line_chart(chart_data)
            
    with tab3:
        st.subheader("最新ゲームの活躍度")
        if not df_history.empty:
            latest_date = df_history['Date'].iloc[-1]
            latest_round = df_history['Round'].iloc[-1]
            st.markdown(f"**最終プレイ: {latest_date} (Round {latest_round})**")
            
            latest_game = df_history[(df_history['Date'] == latest_date) & (df_history['Round'] == latest_round)]
            
            # メトリクスで目立たせる（最大3人）
            top_gainers = latest_game.sort_values('DeltaRating', ascending=False).head(3)
            cols = st.columns(len(top_gainers))
            for i, (_, row) in enumerate(top_gainers.iterrows()):
                with cols[i]:
                    st.metric(label=row['Player'], value=f"{row['NewRating']:.1f}", delta=f"{row['DeltaRating']:.1f}")
            
            st.markdown("---")
            show_cols = ['Player', 'FinalChips', 'ActualShare(%)', 'DeltaRating']
            disp = latest_game[show_cols].copy()
            disp['ActualShare(%)'] = disp['ActualShare(%)'].round(1).astype(str) + "%"
            disp['DeltaRating'] = disp['DeltaRating'].map(lambda x: f"UP ⬆️ +{x:.1f}" if x > 0 else f"DOWN ⬇️ {x:.1f}")
            disp = disp.rename(columns={'Player': 'プレイヤー', 'FinalChips': '最終チップ', 'ActualShare(%)': 'チップ占有率', 'DeltaRating': 'レート変動'})
            st.dataframe(disp.sort_values('レート変動', ascending=False), use_container_width=True)
