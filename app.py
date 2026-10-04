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
        last_delta = player_history['DeltaRating'].iloc[-1] if not player_history.empty else 0
        summary_data.append({
            'Player': player,
            'Rating': rating,
            'LastDelta': last_delta,
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
    # 確実に小数点第1位まで表示されるようにフォーマット
    df_summary['Rating'] = df_summary['Rating'].map(lambda x: f"{x:.1f}")
    df_summary['HighestRating'] = df_summary['HighestRating'].map(lambda x: f"{x:.1f}")
    # トレンド（直近の変動）を見やすくフォーマット
    df_summary['LastDelta'] = df_summary['LastDelta'].map(lambda x: f"📈 +{x:.1f}" if x > 0 else (f"📉 {x:.1f}" if x < 0 else "➖ 0.0"))
    
    # 1画面に縦並びで表示
    st.subheader("🏆 総合レーティングランキング")
    display_cols = ['ランク', 'Player', 'Rating', 'LastDelta', 'GamesPlayed', 'HighestRating']
    rename_dict = {
        'Player': 'プレイヤー',
        'Rating': '現在のレート',
        'LastDelta': '直近の変動',
        'GamesPlayed': '参加回数',
        'HighestRating': '過去最高レート'
    }
    st.dataframe(
        df_summary[display_cols].rename(columns=rename_dict), 
        width="stretch", 
        hide_index=True,
        column_config={
            "ランク": st.column_config.TextColumn("ランク", width="small"),
            "プレイヤー": st.column_config.TextColumn("プレイヤー", width="medium"),
            "現在のレート": st.column_config.TextColumn("現在のレート", width="small"),
            "直近の変動": st.column_config.TextColumn("直近の変動", width="small"),
            "参加回数": st.column_config.NumberColumn("参加回数", width="small"),
            "過去最高レート": st.column_config.TextColumn("過去最高レート", width="small"),
        }
    )
        
    st.markdown("---")

    st.subheader("📈 レート推移")
    if not df_history.empty:
        hist = df_history.copy()
        hist['Game'] = hist['Date'].astype(str) + " R" + hist['Round'].astype(str)
        game_order = list(dict.fromkeys(hist['Game']))
        chart_data = hist.pivot_table(index='Game', columns='Player', values='NewRating', aggfunc='last')
        chart_data = chart_data.reindex(game_order)
        start_row = pd.DataFrame({p: [INITIAL_RATING] for p in chart_data.columns}, index=["開始"])
        chart_data = pd.concat([start_row, chart_data]).ffill()
        chart_data.index = range(len(chart_data))
        chart_data.index.name = "通算ゲーム数"
        st.line_chart(chart_data)
        st.caption("横軸の対応: " + " / ".join(f"{i+1}={g}" for i, g in enumerate(game_order)))
            
    st.markdown("---")

    st.subheader("🔥 最新ゲーム分析")
    if not df_history.empty:
        latest_date = df_history['Date'].iloc[-1]
        latest_round = df_history['Round'].iloc[-1]
        st.markdown(f"**最終プレイ: {latest_date} (Round {latest_round})**")
        
        latest_game = df_history[(df_history['Date'] == latest_date) & (df_history['Round'] == latest_round)]
        
        top_gainers = latest_game.sort_values('DeltaRating', ascending=False).head(3)
        cols = st.columns(len(top_gainers))
        for i, (_, row) in enumerate(top_gainers.iterrows()):
            with cols[i]:
                st.metric(label=row['Player'], value=f"{row['NewRating']:.1f}", delta=f"{row['DeltaRating']:.1f}")
        
        show_cols = ['Player', 'FinalChips', 'ActualShare(%)', 'DeltaRating']
        disp = latest_game[show_cols].sort_values('DeltaRating', ascending=False).copy()
        disp['ActualShare(%)'] = disp['ActualShare(%)'].round(1).astype(str) + "%"
        disp['DeltaRating'] = disp['DeltaRating'].map(lambda x: f"📈 +{x:.1f}" if x > 0 else (f"📉 {x:.1f}" if x < 0 else "➖ 0.0"))
        disp = disp.rename(columns={'Player': 'プレイヤー', 'FinalChips': '最終チップ', 'ActualShare(%)': 'チップ占有率', 'DeltaRating': 'レート変動'})
        
        st.dataframe(
            disp, 
            width="stretch", 
            hide_index=True,
            column_config={
                "プレイヤー": st.column_config.TextColumn("プレイヤー", width="medium"),
                "最終チップ": st.column_config.NumberColumn("最終チップ", width="small"),
                "チップ占有率": st.column_config.TextColumn("チップ占有率", width="small"),
                "レート変動": st.column_config.TextColumn("レート変動", width="medium"),
            }
        )
