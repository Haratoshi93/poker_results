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
    # ランクの計算（四捨五入した整数値で同点を判定）
    # method='min' により、1位が2人いれば次は3位になります
    df_summary['rank_num'] = df_summary['Rating'].round(0).rank(method='min', ascending=False).astype(int)
    
    def get_medal(rank):
        if rank == 1: return "🥇"
        if rank == 2: return "🥈"
        if rank == 3: return "🥉"
        return f"{rank}位"

    df_summary['ランク'] = df_summary['rank_num'].map(get_medal)
    # 整数（四捨五入）でスッキリ表示するようにフォーマット
    df_summary['Rating'] = df_summary['Rating'].map(lambda x: f"{int(round(x))}")
    df_summary['HighestRating'] = df_summary['HighestRating'].map(lambda x: f"{int(round(x))}")
    # トレンド（直近の変動）を見やすくフォーマット
    df_summary['LastDelta'] = df_summary['LastDelta'].map(lambda x: f"📈 +{int(round(x))}" if x > 0 else (f"📉 {int(round(x))}" if x < 0 else "➖ 0"))
    
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
        import altair as alt
        hist = df_history.copy()
        hist['Game'] = hist['Date'].astype(str) + " (R" + hist['Round'].astype(str) + ")"
        game_order = ["開始"] + list(dict.fromkeys(hist['Game']))
        
        chart_data = hist.pivot_table(index='Game', columns='Player', values='NewRating', aggfunc='last')
        start_row = pd.DataFrame({p: [INITIAL_RATING] for p in chart_data.columns}, index=["開始"])
        chart_data = pd.concat([start_row, chart_data]).reindex(game_order).ffill()
        
        # Altair描画用にデータを変形
        df_chart = chart_data.reset_index().melt(id_vars='index', var_name='Player', value_name='Rating')
        df_chart = df_chart.rename(columns={'index': 'Game'})
        
        # グラフの設定（X軸をgame_orderの通りに強制ソート）
        chart = alt.Chart(df_chart).mark_line(point=True).encode(
            x=alt.X('Game:O', sort=game_order, title="ゲーム (日付とラウンド)", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('Rating:Q', scale=alt.Scale(zero=False), title="レート"),
            color=alt.Color('Player:N', legend=alt.Legend(title="プレイヤー")),
            tooltip=['Game', 'Player', alt.Tooltip('Rating:Q', format='.0f')]
        ).interactive()
        
        st.altair_chart(chart, use_container_width=True)
            
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
                st.metric(label=row['Player'], value=f"{int(round(row['NewRating']))}", delta=f"{int(round(row['DeltaRating']))}")
        
        show_cols = ['Player', 'FinalChips', 'ActualShare(%)', 'DeltaRating']
        disp = latest_game[show_cols].sort_values('DeltaRating', ascending=False).copy()
        disp['ActualShare(%)'] = disp['ActualShare(%)'].round(1).astype(str) + "%"
        disp['DeltaRating'] = disp['DeltaRating'].map(lambda x: f"📈 +{int(round(x))}" if x > 0 else (f"📉 {int(round(x))}" if x < 0 else "➖ 0"))
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
