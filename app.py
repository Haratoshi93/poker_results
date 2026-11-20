import html
import math
import os

import pandas as pd
import streamlit as st

# スマホでも見やすい中央寄せレイアウト
st.set_page_config(page_title="Poker Rating Dashboard", page_icon="♠️", layout="centered")

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


def build_hero_summary_html(df_raw: pd.DataFrame, df_history: pd.DataFrame, df_summary: pd.DataFrame) -> str:
    """ヒーローバナー内に表示する現在の1位と対戦実績バッジのHTMLを組み立てる。"""
    if df_summary.empty or df_raw.empty:
        return '<p class="poker-hero-sub">Poker Rating Dashboard — 対戦データを読み込むと最新順位が表示されます</p>'

    rounded_ratings = df_summary['Rating'].round(0)
    top_score = int(rounded_ratings.max())
    top_players = df_summary.loc[rounded_ratings == top_score, 'Player'].tolist()
    top_names = "・".join(html.escape(str(name)) for name in top_players)
    total_rounds = int(df_raw[['Date', 'Round']].drop_duplicates().shape[0])
    latest_date = html.escape(str(df_history['Date'].iloc[-1])) if not df_history.empty else "-"

    return (
        f'<div class="poker-hero-meta">'
        f'<span class="poker-hero-badge">👑 現在の1位: {top_names} ({top_score} pt)</span>'
        f'<span class="poker-hero-stat">全 {total_rounds} ラウンド / 最終プレイ {latest_date}</span>'
        f'</div>'
    )


df_raw, df_history, df_summary = load_and_calc_ratings()
hero_meta_html = build_hero_summary_html(df_raw, df_history, df_summary)

st.markdown(
    f"""
<style>
:root {{
  --in-oklab: ;
}}
@supports (background: linear-gradient(in oklab, white, black)) {{
  :root {{
    --in-oklab: in oklab;
  }}
}}
.poker-hero {{
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgba(212, 175, 55, 0.45);
  background: #0B1310 url("app/static/poker-hero-poster.jpg?v=5") center / cover no-repeat;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.45), 0 16px 36px rgba(0, 0, 0, 0.6);
  margin-bottom: 1rem;
  padding: 1.75rem 1.4rem 1.45rem;
}}
.poker-hero-video {{
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  pointer-events: none;
  z-index: 0;
}}
.poker-hero-overlay {{
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(to bottom var(--in-oklab), rgba(8, 16, 13, 0.45), rgba(8, 16, 13, 0.85));
}}
.poker-hero-content {{
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}}
.poker-hero-top {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}}
.poker-hero-title {{
  margin: 0 !important;
  padding: 0 !important;
  font-size: clamp(1.55rem, 4.5vw, 2.2rem) !important;
  font-weight: 700 !important;
  line-height: 1.2 !important;
  color: #F3EFE6 !important;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.75);
}}
.poker-motion-toggle {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-height: 28px;
  min-width: 28px;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  background: rgba(11, 19, 16, 0.72);
  border: 1px solid rgba(212, 175, 55, 0.45);
  color: #F3EFE6;
  font-size: 0.75rem;
  line-height: 1.2;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}}
.poker-motion-checkbox {{
  accent-color: #D4AF37;
  width: 15px;
  height: 15px;
  margin: 0;
  cursor: pointer;
}}
.poker-motion-toggle:has(.poker-motion-checkbox:focus-visible) {{
  outline: 2px solid #D4AF37;
  outline-offset: 2px;
}}
.poker-hero:has(.poker-motion-checkbox:checked) .poker-hero-video {{
  display: none;
}}
@media (prefers-reduced-motion: reduce) {{
  .poker-hero-video {{
    display: none !important;
  }}
  .poker-motion-toggle {{
    display: none;
  }}
}}
.poker-hero-meta {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.85rem;
}}
.poker-hero-badge {{
  display: inline-flex;
  align-items: center;
  padding: 0.3rem 0.75rem;
  border-radius: 999px;
  background: rgba(212, 175, 55, 0.16);
  border: 1px solid rgba(212, 175, 55, 0.55);
  color: #F6DF91;
  font-size: 0.88rem;
  font-weight: 600;
}}
.poker-hero-stat {{
  color: #D6D1C4;
  font-size: 0.84rem;
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.75);
}}
.poker-hero-sub {{
  margin: 0;
  color: #D6D1C4;
  font-size: 0.9rem;
}}
[data-testid="stMetric"] {{
  background-color: #13221C;
  border: 1px solid rgba(212, 175, 55, 0.35);
  border-radius: 12px;
  padding: 0.85rem 1rem;
}}
hr {{
  border: none;
  height: 1px;
  background: linear-gradient(to right, transparent, rgba(212, 175, 55, 0.45), transparent);
  margin: 1.5rem 0;
}}
</style>
<div class="poker-hero">
<video class="poker-hero-video" autoplay loop muted playsinline preload="metadata" poster="app/static/poker-hero-poster.jpg?v=5" aria-hidden="true">
<source src="app/static/poker-hero-bg.mp4?v=5" type="video/mp4">
</video>
<div class="poker-hero-overlay" aria-hidden="true"></div>
<div class="poker-hero-content">
<div class="poker-hero-top">
<h1 class="poker-hero-title">♠️ Poker Rating</h1>
<label class="poker-motion-toggle">
<input type="checkbox" class="poker-motion-checkbox">
<span>静止画にする</span>
</label>
</div>
{hero_meta_html}
</div>
</div>
""",
    unsafe_allow_html=True,
)

with st.expander("ℹ️ レーティングのルール（仕組み）", expanded=False):
    st.markdown("""
    - **初期スタート**: 全員 `1000 pt` からスタートします。
    - **ポイントの増減**: 自分の現在のレートから「これくらいチップを稼げるはず」という期待値が計算され、実際の獲得チップがそれを上回ればプラスに、下回ればマイナスになります。
    - **強者への勝利**: 自分よりレートが高い（格上の）人がいるゲームで勝ち残ると、より多くのポイントを奪うことができます。
    """)

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
            chart = (
                alt.Chart(df_chart)
                .mark_line(point=True)
                .encode(
                    x=alt.X('Game:O', sort=game_order, title="ゲーム (日付とラウンド)", axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y('Rating:Q', scale=alt.Scale(zero=False), title="レート"),
                    color=alt.Color('Player:N', legend=alt.Legend(title="プレイヤー")),
                    # マウスオーバー時のみ線を太く、濃くする（他は薄くする）
                    opacity=alt.condition(highlight, alt.value(1.0), alt.value(0.2)),
                    size=alt.condition(highlight, alt.value(3), alt.value(1)),
                    tooltip=['Game', 'Player', alt.Tooltip('Rating:Q', format='.0f')]
                )
                .add_params(highlight)
                .configure_view(strokeOpacity=0)
                .properties(background="transparent")
            )
            
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
