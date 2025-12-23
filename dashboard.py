import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from collections import Counter
import emoji
import re
import numpy as np

# Pagina Configuratie
st.set_page_config(page_title="WhatsApp Statistieken", layout="wide", page_icon="🦁")

# --- DATA LADEN ---
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect('chat_data.db')
        query = "SELECT * FROM messages"
        df = pd.read_sql_query(query, conn)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        conn.close()
        return df
    except Exception as e:
        st.error(f"Kan database niet laden. Foutmelding: {e}")
        return pd.DataFrame()

# --- HULP FUNCTIES ---
def extract_emojis(text):
    return [c for c in text if c in emoji.EMOJI_DATA]

def count_unique_words(text_series):
    all_text = " ".join(text_series.dropna().astype(str)).lower()
    words = re.findall(r'\b\w+\b', all_text)
    return len(set(words))

def get_streak(dates):
    if len(dates) == 0: return 0
    dates = sorted(list(set(dates)))
    longest_streak = 0
    current_streak = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i-1]).days == 1:
            current_streak += 1
        else:
            longest_streak = max(longest_streak, current_streak)
            current_streak = 1
    return max(longest_streak, current_streak)

def main():
    st.title("🦁 Het Grote WhatsApp Dashboard")
    df = load_data()

    if df.empty:
        st.warning("Geen data gevonden. Draai eerst het parser-script.")
        return

    # --- FILTER SYSTEM ERUIT ---
    df = df[df['sender'] != 'System']

    # --- SIDEBAR & FILTERS ---
    st.sidebar.header("⚙️ Instellingen")
    
    # 1. WEERGAVE TOGGLE
    view_mode = st.sidebar.radio(
        "Weergave Modus", 
        ["Absolute Aantallen (123)", "Relatief (% van eigen berichten)"]
    )
    is_relative = view_mode == "Relatief (% van eigen berichten)"
    
    # 2. GEBRUIKERS FILTER
    users = st.sidebar.multiselect("Selecteer Deelnemers", df['sender'].unique(), default=df['sender'].unique())
    df_filtered = df[df['sender'].isin(users)].copy()
    
    # Pre-calculate totals
    user_totals_dict = df_filtered['sender'].value_counts().to_dict()
    total_group_msgs = len(df_filtered)

    # --- TABS INDELING ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Overzicht", 
        "🧪 Het Lab", 
        "🧠 Gedragsanalyse", 
        "🎉 De Feestzone", 
        "🔍 Archief"
    ])

    # Hulpfunctie voor grafieken
    def render_chart(data, x_col, y_col, title, color_scale='Viridis', orientation='h', force_absolute=False, explanation=None, custom_relative_label=None):
        df_chart = data.copy()
        label = "Aantal"
        text_format = ".0f"

        if is_relative and not force_absolute:
            def calculate_percentage(row):
                user_total = user_totals_dict.get(row['User'], 1)
                if user_total == 0: return 0
                return (row['Value'] / user_total) * 100

            df_chart['Value'] = df_chart.apply(calculate_percentage, axis=1)
            label = custom_relative_label if custom_relative_label else "% van eigen berichten"
            text_format = ".1f"

        height = max(350, len(df_chart) * 30)
        
        fig = px.bar(df_chart, x='Value', y='User', orientation=orientation, 
                     title=title, color='Value', color_continuous_scale=color_scale,
                     labels={'Value': label}, text_auto=text_format)
        
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=height)
        st.plotly_chart(fig, use_container_width=True)
        
        if explanation:
            st.caption(f"ℹ️ {explanation}")

    # === TAB 1: OVERZICHT ===
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Totaal Berichten", df_filtered.shape[0])
        c2.metric("Polls Aangemaakt", df_filtered['is_poll'].sum())
        c3.metric("Media Gedeeld", df_filtered['has_media'].sum())
        days_active = (df_filtered['timestamp'].max() - df_filtered['timestamp'].min()).days
        c4.metric("Dagen Actief", days_active if days_active > 0 else 1)
        st.markdown("---")
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.subheader("Activiteit over tijd")
            df_filtered['date_only'] = df_filtered['timestamp'].dt.date
            daily = df_filtered.groupby('date_only').size().reset_index(name='count')
            fig_line = px.line(daily, x='date_only', y='count', markers=True, labels={'date_only': 'Datum', 'count': 'Berichten'})
            st.plotly_chart(fig_line, use_container_width=True)
        with col_right:
            st.subheader("De Ranglijst")
            top_users = df_filtered['sender'].value_counts().reset_index()
            top_users.columns = ['User', 'Value']
            lbl = "Aantal berichten"
            if is_relative:
                top_users['Value'] = (top_users['Value'] / total_group_msgs) * 100
                lbl = "% Marktaandeel"
            fig_bar = px.bar(top_users, x='Value', y='User', orientation='h', color='Value', labels={'Value': lbl}, text_auto='.0f')
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)
            st.caption("ℹ️ Simpelweg: wie heeft de meeste berichten gestuurd in deze selectie?")

    # === TAB 2: HET LAB ===
    with tab2:
        st.markdown("### 🧪 Experimentele Statistieken")
        
        # Data berekeningen
        df_filtered['prev_sender'] = df_filtered['sender'].shift(1)
        double_texts = df_filtered[df_filtered['sender'] == df_filtered['prev_sender']].groupby('sender').size().reset_index(name='Value')
        double_texts.columns = ['User', 'Value']
        
        night_msgs = df_filtered[(df_filtered['timestamp'].dt.hour >= 0) & (df_filtered['timestamp'].dt.hour < 6)]
        night_counts = night_msgs['sender'].value_counts().reset_index(name='Value')
        night_counts.columns = ['User', 'Value']

        questions = df_filtered[df_filtered['message_content'].str.contains(r'\?', na=False)]
        q_counts = questions['sender'].value_counts().reset_index(name='Value')
        q_counts.columns = ['User', 'Value']

        shouts = df_filtered[df_filtered['message_content'].str.match(r'^[^a-z]*[A-Z]{3,}[^a-z]*$', na=False)]
        shout_counts = shouts['sender'].value_counts().reset_index(name='Value')
        shout_counts.columns = ['User', 'Value']

        links = df_filtered[df_filtered['message_content'].str.contains(r'http|www\.', case=False, na=False)]
        link_counts = links['sender'].value_counts().reset_index(name='Value')
        link_counts.columns = ['User', 'Value']

        swear_words_list = [
            'kut', 'godver', 'tering', 'tyfus', 'kanker', 'kk', 'kkr', 'gvd', 
            'fack', 'fuck', 'shit', 'verdomme', 'lul', 'pik', 'eikel', 'slet', 
            'hoer', 'flikker', 'mongool', 'debiel', 'teringlijer', 'hufter'
        ]
        swear_pattern = r'|'.join([r'\b' + w for w in swear_words_list]) + r'|kut|kanker|tering'
        swears = df_filtered[df_filtered['message_content'].str.contains(swear_pattern, case=False, na=False)]
        swear_counts = swears['sender'].value_counts().reset_index(name='Value')
        swear_counts.columns = ['User', 'Value']

        df_speed = df_filtered.sort_values('timestamp').copy()
        df_speed['time_diff'] = df_speed['timestamp'].diff().dt.total_seconds()
        speed_msgs = df_speed[(df_speed['sender'] != df_speed['prev_sender']) & (df_speed['time_diff'] < 14400) & (df_speed['time_diff'] > 0)]
        avg_speed = speed_msgs.groupby('sender')['time_diff'].mean().reset_index(name='Value')
        avg_speed.columns = ['User', 'Value']
        avg_speed['Value'] = avg_speed['Value'] / 60 

        negatives = df_filtered[df_filtered['message_content'].str.contains(r'\b(nee|niet|geen|nooit|nopes|niks)\b', case=False, na=False)]
        neg_counts = negatives['sender'].value_counts().reset_index(name='Value')
        neg_counts.columns = ['User', 'Value']

        streak_data = []
        for user in users:
            user_dates = df_filtered[df_filtered['sender'] == user]['timestamp'].dt.date.tolist()
            streak = get_streak(user_dates)
            streak_data.append({'User': user, 'Value': streak})
        streak_df = pd.DataFrame(streak_data)
        streak_df = streak_df.sort_values('Value', ascending=True)

        # --- GRID LAYOUT ---
        c1, c2 = st.columns(2)
        with c1: render_chart(
            double_texts, 'Value', 'User', "👯 De Dubbele Texter", "Purp",
            explanation="Aantal keren dat iemand 2+ berichten achter elkaar stuurde zonder onderbreking."
        )
        with c2: render_chart(
            night_counts, 'Value', 'User', "🦉 De Nachtdienst", "Magma",
            explanation="Berichten verstuurd tussen 00:00 en 06:00 's nachts."
        )

        c3, c4 = st.columns(2)
        with c3: render_chart(
            q_counts, 'Value', 'User', "❓ De Vragensteller", "Teal",
            explanation="Aantal berichten met een vraagteken (?)."
        )
        with c4: render_chart(
            shout_counts, 'Value', 'User', "📢 De Schreeuwer", "Reds",
            explanation="Berichten die volledig in HOOFDLETTERS zijn geschreven."
        )

        c5, c6 = st.columns(2)
        with c5: render_chart(
            link_counts, 'Value', 'User', "🔗 De Linkstrooier", "Blues",
            explanation="Berichten die een webadres (http/www) bevatten."
        )
        with c6: 
            render_chart(
                swear_counts, 'Value', 'User', "🤬 De Vloekpot", "Oranges",
                explanation="Berichten met scheldwoorden (kut, kk, gvd, etc.)."
            )
            with st.expander("Woordenlijst check"):
                all_text_blob = " ".join(df_filtered['message_content'].dropna().astype(str)).lower()
                matches = re.findall(swear_pattern, all_text_blob)
                if matches:
                    top_swears = Counter(matches).most_common(5)
                    st.write("**Top 5 gebruikt:**")
                    st.write(pd.DataFrame(top_swears, columns=['Woord', 'Aantal']))

        c7, c8 = st.columns(2)
        with c7: 
            avg_speed_sorted = avg_speed.sort_values('Value', ascending=False)
            fig_speed = px.bar(avg_speed_sorted, x='Value', y='User', orientation='h', 
                               title="⚡ De Snelheidsduivel (Snelste bovenaan)", color='Value', color_continuous_scale='RdYlGn_r')
            st.plotly_chart(fig_speed, use_container_width=True)
            with st.expander("ℹ️ Uitleg formule"):
                st.write("Gemiddelde tijd in minuten tussen een vorig bericht en jouw reactie (binnen 4 uur). Zelf-reacties tellen niet.")
                
        with c8: render_chart(
            neg_counts, 'Value', 'User', "📉 De Negativiteits-index", "Gray",
            explanation="Berichten met ontkennende woorden zoals 'nee', 'niet', 'geen'."
        )

        c9, c10 = st.columns(2)
        with c9: 
            fig_streak = px.bar(streak_df, x='Value', y='User', orientation='h', 
                                title="🔥 Langste 'Streak' (Dagen)", color='Value', color_continuous_scale='Hot', labels={'Value': 'Dagen'})
            st.plotly_chart(fig_streak, use_container_width=True)
            st.caption("ℹ️ Maximaal aantal dagen achter elkaar dat iemand iets in de groep zei.")
        with c10:
            st.empty()

    # === TAB 3: DIEPTE ANALYSE ===
    with tab3:
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.subheader("👻 De Reanimator")
            df_sorted = df_filtered.sort_values('timestamp')
            df_sorted['time_diff_obj'] = df_sorted['timestamp'].diff()
            revivals = df_sorted[df_sorted['time_diff_obj'] > pd.Timedelta(hours=6)]
            if not revivals.empty:
                reviver_counts = revivals['sender'].value_counts().reset_index(name='Value')
                reviver_counts.columns = ['User', 'Value']
                render_chart(
                    reviver_counts, 'Value', 'User', "Aantal Reanimaties", "Purples",
                    explanation="Berichten gestuurd nadat het 6+ uur stil was."
                )
            else: st.info("Geen stiltes gevonden.")

        with col_a2:
            st.subheader("🍻 Weekend Strijders")
            df_filtered['is_weekend'] = df_filtered['timestamp'].dt.dayofweek >= 5
            weekend_counts = df_filtered[df_filtered['is_weekend'] == True]['sender'].value_counts().reset_index(name='Value')
            weekend_counts.columns = ['User', 'Value']
            render_chart(
                weekend_counts, 'Value', 'User', "Berichten in het weekend", "Inferno",
                explanation="Aantal berichten op Zaterdag of Zondag."
            )

        st.markdown("---")
        col_a3, col_a4 = st.columns(2)
        with col_a3:
            st.subheader("📏 De Spraakwaterval")
            # 1. Berekenen
            df_filtered['word_count'] = df_filtered['message_content'].apply(lambda x: len(str(x).split()))
            avg_len = df_filtered.groupby('sender')['word_count'].mean().reset_index()
            avg_len.columns = ['User', 'Value']
            
            # 2. SORTEREN (Nieuwe toevoeging)
            avg_len = avg_len.sort_values('Value', ascending=True)

            fig_len = px.bar(avg_len, x='Value', y='User', orientation='h', color='Value', color_continuous_scale='Teal', labels={'Value': 'Woorden'})
            st.plotly_chart(fig_len, use_container_width=True)
            with st.expander("ℹ️ Wat betekent dit?"):
                st.write("""
                **Gemiddeld aantal woorden per bericht.**
                * Dit is altijd een absoluut gemiddelde, de Relatief-knop heeft hier geen invloed op.
                * Een hoog cijfer betekent dat iemand vaak lange teksten typt.
                """)

        with col_a4:
            st.subheader("🧠 De Woordenschat")
            vocab_data = []
            for user in users:
                user_msgs = df_filtered[df_filtered['sender'] == user]['message_content']
                # Bereken uniek vs totaal
                all_text_str = " ".join(user_msgs.dropna().astype(str)).lower()
                all_words = re.findall(r'\b\w+\b', all_text_str)
                total_word_count = len(all_words)
                unique_word_count = len(set(all_words))
                vocab_data.append({'User': user, 'Value': unique_word_count, 'TotalWords': total_word_count})
            
            vocab_df = pd.DataFrame(vocab_data)
            
            # 3. LOGICA VOOR WOORDENSCHAT (Nieuwe toevoeging)
            if is_relative:
                # Relatief: Unieke woorden PER bericht (of per 100 woorden, maar we doen hier score)
                # We gebruiken de bestaande render_chart die deelt door Aantal Berichten.
                # Unieke woorden / Aantal Berichten = "Nieuwe woorden per keer dat je iets zegt"
                # Dit is een maatstaf voor diversiteit.
                render_chart(
                    vocab_df, 'Value', 'User', "Woordenschat Diversiteit", "Viridis", force_absolute=False,
                    custom_relative_label="Unieke woorden per bericht",
                    explanation="In de relatieve modus delen we het aantal unieke woorden door jouw totaal aantal berichten. Een hoge score betekent dat je heel gevarieerd praat en niet steeds hetzelfde zegt."
                )
            else:
                # Absoluut: Gewoon wie de meeste woorden kent
                render_chart(
                    vocab_df, 'Value', 'User', "Totaal Unieke Woorden", "Viridis", force_absolute=True,
                    explanation="Het totaal aantal woorden dat jij hebt gebruikt die je nog niet eerder had gebruikt. Natuurlijk wint degene met de meeste berichten hier vaak."
                )

    # === TAB 4: FEESTZONE ===
    with tab4:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.subheader("☁️ Woordenwolk")
            stopwords = set(['de', 'het', 'een', 'en', 'is', 'dat', 'van', 'ik', 'te', 'niet', 'op', 'voor', 'media', 'omitted', 'in', 'je', 'met', 'als', 'die', 'zijn', 'maar', 'heb', 'er', 'aan', 'om', 'dan'])
            text_content = " ".join(df_filtered['message_content'].dropna().astype(str))
            try:
                wc = WordCloud(width=800, height=400, background_color ='white', stopwords=stopwords).generate(text_content)
                fig_wc, ax = plt.subplots()
                ax.imshow(wc, interpolation='bilinear')
                ax.axis("off")
                st.pyplot(fig_wc)
                st.caption("De meest gebruikte woorden in de chat (groot = vaak gebruikt).")
            except ValueError: st.info("Niet genoeg tekst.")
        with col_f2:
            st.subheader("😂 Emoji Analyse")
            all_emojis_list = []
            for msg in df_filtered['message_content'].dropna():
                all_emojis_list.extend(extract_emojis(msg))
            if all_emojis_list:
                emoji_counts = Counter(all_emojis_list).most_common(10)
                emoji_df = pd.DataFrame(emoji_counts, columns=['Emoji', 'Count'])
                fig_emoji = px.pie(emoji_df, names='Emoji', values='Count', hole=0.3)
                st.plotly_chart(fig_emoji, use_container_width=True)
                st.caption("De 10 meest gebruikte emoji's.")

    # === TAB 5: ARCHIEF ===
    with tab5:
        search_query = st.text_input("Zoek in berichten")
        if search_query:
            results = df_filtered[df_filtered['message_content'].str.contains(search_query, case=False, na=False)]
            st.dataframe(results[['timestamp', 'sender', 'message_content']].sort_values(by='timestamp', ascending=False), use_container_width=True)
        else:
            st.dataframe(df_filtered[['timestamp', 'sender', 'message_content']].head(100), use_container_width=True)

if __name__ == "__main__":
    main()