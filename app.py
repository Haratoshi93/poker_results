import streamlit as st
import pandas as pd
import math
import os

# スマホでも見やすい中央寄せレイアウト
st.set_page_config(page_title="Poker Rating Dashboard", page_icon="♠️", layout="centered")

st.title("♠️ Poker Rating")

with st.expander("ℹ️ レーティングのルール（仕組み）", expanded=False):
    st.markdown("""
    - **初期スタート**: 全員 `1000 pt` からスタートします。
    - **ポイントの増減**: 自分の現在のレートから「これくらいチップを稼げるはず」という期待値が計算され、実際の獲得チップがそれを上回ればプラスに、下回ればマイナスになります。
    - **強者への勝利**: 自分よりレートが高い（格上の）人がいるゲームで勝ち残ると、より多くのポイントを奪うことができます。
    """)

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
    st.subheader("🏆 総合ランキング")
    # スマホで絶対に見切れないよう、情報を結合して2列に集約する
    disp_summary = df_summary.copy()
    disp_summary['プレイヤー'] = disp_summary['ランク'] + " " + disp_summary['Player']
    disp_summary['レート (前回比)'] = disp_summary['Rating'] + " pt (" + disp_summary['LastDelta'] + ")"
    
    st.dataframe(
        disp_summary[['プレイヤー', 'レート (前回比)']], 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "プレイヤー": st.column_config.TextColumn("プレイヤー", width="medium"),
            "レート (前回比)": st.column_config.TextColumn("レート (前回比)", width="medium"),
        }
    )
        
    st.markdown("---")

    st.subheader("📈 レート推移")
    if not df_history.empty:
        import altair as alt
        
        # 全プレイヤーのリスト（ランキング順）
        all_players = df_summary['Player'].tolist()
        
        # プレイヤー絞り込み機能（デフォルトは空）
        selected_players = st.multiselect(
            "グラフに表示するプレイヤーを選択",
            options=all_players,
            default=[]
        )
        
        if not selected_players:
            st.info("プレイヤーを選択してください。")
        else:
            hist = df_history.copy()
            hist['Game'] = hist['Date'].astype(str) + " (R" + hist['Round'].astype(str) + ")"
            game_order = ["開始"] + list(dict.fromkeys(hist['Game']))
            
            # 選択されたプレイヤーのデータだけを抽出
            chart_data = hist.pivot_table(index='Game', columns='Player', values='NewRating', aggfunc='last')
            available_players = [p for p in selected_players if p in chart_data.columns]
            chart_data = chart_data[available_players]
            
            start_row = pd.DataFrame({p: [INITIAL_RATING] for p in available_players}, index=["開始"])
            chart_data = pd.concat([start_row, chart_data]).reindex(game_order).ffill()
            
            # Altair描画用にデータを変形
            df_chart = chart_data.reset_index().melt(id_vars='index', var_name='Player', value_name='Rating')
            df_chart = df_chart.rename(columns={'index': 'Game'})
            
            # マウスオーバーした線をハイライトする設定
            highlight = alt.selection_point(on='mouseover', fields=['Player'], nearest=True)
            
            # グラフの設定
            chart = alt.Chart(df_chart).mark_line(point=True).encode(
                x=alt.X('Game:O', sort=game_order, title="ゲーム (日付とラウンド)", axis=alt.Axis(labelAngle=-45)),
                y=alt.Y('Rating:Q', scale=alt.Scale(zero=False), title="レート"),
                color=alt.Color('Player:N', legend=alt.Legend(title="プレイヤー")),
                # マウスオーバー時のみ線を太く、濃くする（他は薄くする）
                opacity=alt.condition(highlight, alt.value(1.0), alt.value(0.2)),
                size=alt.condition(highlight, alt.value(3), alt.value(1)),
                tooltip=['Game', 'Player', alt.Tooltip('Rating:Q', format='.0f')]
            ).add_params(highlight)
            
            st.altair_chart(chart, use_container_width=True)
            
    st.markdown("---")

    st.subheader("🔥 最新ゲームの結果")
    if not df_history.empty:
        latest_date = df_history['Date'].iloc[-1]
        latest_round = df_history['Round'].iloc[-1]
        st.markdown(f"**最終プレイ: {latest_date} (Round {latest_round})**")
        
        latest_game = df_history[(df_history['Date'] == latest_date) & (df_history['Round'] == latest_round)]
        
        top_gainers = latest_game.sort_values('DeltaRating', ascending=False).head(3)
        cols = st.columns(len(top_gainers))
        for i, (_, row) in enumerate(top_gainers.iterrows()):
            with cols[i]:
                # レートであることが明確になるように「pt」を付与
                st.metric(label=row['Player'], value=f"{int(round(row['NewRating']))} pt", delta=f"{int(round(row['DeltaRating']))} pt")
        
        show_cols = ['Player', 'FinalChips', 'DeltaRating']
        disp = latest_game[show_cols].sort_values('DeltaRating', ascending=False).copy()
        
        # 単位を付けて混同を防ぎつつ、すべて文字列化することで表内の文字寄せ（左寄せ）を統一する
        disp['FinalChips'] = disp['FinalChips'].astype(str) + " 枚"
        disp['DeltaRating'] = disp['DeltaRating'].map(lambda x: f"📈 +{int(round(x))} pt" if x > 0 else (f"📉 {int(round(x))} pt" if x < 0 else "➖ 0 pt"))
        
        # スマホ向けにヘッダー名を極力短くして横幅を節約する（3列に絞る）
        disp = disp.rename(columns={'Player': '名前', 'FinalChips': 'チップ', 'DeltaRating': '変動'})
        
        st.dataframe(
            disp, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "名前": st.column_config.TextColumn("名前", width="medium"),
                "チップ": st.column_config.TextColumn("チップ", width="small"),
                "変動": st.column_config.TextColumn("変動", width="small"),
            }
        )
