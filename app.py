from collections import Counter

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API = "https://api.github.com"

st.set_page_config(page_title="GitHub Profile Analyzer", page_icon="📊", layout="wide")


def _headers():
    try:
        token = st.secrets.get("GITHUB_TOKEN")
    except Exception:
        token = None
    return {"Authorization": f"Bearer {token}"} if token else {}


@st.cache_data(ttl=600, show_spinner=False)
def get_user(username: str):
    r = requests.get(f"{API}/users/{username}", headers=_headers(), timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=600, show_spinner=False)
def get_repos(username: str):
    repos, page = [], 1
    while page <= 5:
        r = requests.get(
            f"{API}/users/{username}/repos",
            params={"per_page": 100, "page": page, "sort": "updated"},
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos += batch
        page += 1
    return repos


def repos_to_df(repos):
    return pd.DataFrame(
        [
            {
                "name": r["name"],
                "stars": r["stargazers_count"],
                "forks": r["forks_count"],
                "language": r["language"] or "Unknown",
                "updated": pd.to_datetime(r["pushed_at"]),
                "url": r["html_url"],
                "fork": r["fork"],
            }
            for r in repos
        ]
    )


st.title("📊 GitHub Profile Analyzer")
st.caption("Enter any public GitHub username to see an instant breakdown.")
username = st.text_input("GitHub username", placeholder="e.g. torvalds").strip()

if username:
    try:
        user = get_user(username)
        if user is None:
            st.error("User not found. Check the spelling and try again.")
            st.stop()
        repos = get_repos(username)
    except requests.HTTPError as e:
        st.error(f"GitHub API error (possibly rate limit): {e}")
        st.stop()
    except requests.RequestException:
        st.error("Network problem. Please try again.")
        st.stop()

    c1, c2 = st.columns([1, 4])
    c1.image(user["avatar_url"], width=140)
    c2.subheader(user.get("name") or user["login"])
    c2.write(user.get("bio") or "_No bio_")
    c2.markdown(f"[Open profile]({user['html_url']})")

    df = repos_to_df(repos)
    if df.empty:
        st.info("This user has no public repositories yet.")
        st.stop()

    own = df[~df["fork"]]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Public repos", user["public_repos"])
    m2.metric("Followers", user["followers"])
    m3.metric("Total stars", int(own["stars"].sum()))
    m4.metric("Account created", user["created_at"][:4])

    include_forks = st.checkbox("Include forked repos", value=False)
    data = df if include_forks else own

    left, right = st.columns(2)

    with left:
        st.subheader("Top languages")
        langs = Counter(data["language"])
        lang_df = pd.DataFrame(langs.items(), columns=["language", "repos"])
        st.plotly_chart(
            px.pie(lang_df, names="language", values="repos", hole=0.4),
            use_container_width=True,
        )

    with right:
        st.subheader("Most starred repos")
        top = data.sort_values("stars", ascending=False).head(8)
        fig = px.bar(top, x="stars", y="name", orientation="h")
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("All repositories")
    st.dataframe(
        data[["name", "language", "stars", "forks", "updated", "url"]]
        .sort_values("updated", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={"url": st.column_config.LinkColumn("link")},
    )

    st.download_button(
        "Download repo data (CSV)",
        data.to_csv(index=False),
        file_name=f"{username}_repos.csv",
        mime="text/csv",
    )