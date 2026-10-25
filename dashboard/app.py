"""
dashboard/app.py
Main Streamlit application entry point.
"""
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Carbon Footprint Estimator",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Carbon Footprint Estimator — India-specific spend-based CO₂e estimation.",
    },
)

# ---------------------------------------------------------------------------
# Custom CSS — warm light theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Main background */
.stApp {
    background-color: #FAF8F5;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #F0EDE8;
    border-right: 1px solid #E0DBD4;
}

/* Metric cards */
[data-testid="metric-container"] {
    background: white;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    border: 1px solid #EDE8E1;
}

/* Headers */
h1, h2, h3 {
    color: #1A1A2E;
    font-weight: 600;
}

/* Primary button */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2D6A4F, #40916C);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s ease;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1B4332, #2D6A4F);
    box-shadow: 0 4px 12px rgba(45,106,79,0.3);
    transform: translateY(-1px);
}

/* Info/warning boxes */
.stAlert {
    border-radius: 8px;
}

/* Data tables */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}

/* Tabs */
.stTabs [data-baseweb="tab"] {
    color: #555;
    font-weight: 500;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #2D6A4F;
    border-bottom-color: #2D6A4F;
}

/* Badge */
.badge-green {
    background: #D8F3DC;
    color: #1B4332;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}
.badge-amber {
    background: #FFF3CD;
    color: #856404;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}
.badge-red {
    background: #F8D7DA;
    color: #721C24;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

/* Footer */
.footer {
    color: #999;
    font-size: 12px;
    text-align: center;
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #EDE8E1;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# DB health check (non-blocking)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _init_db():
    """Initialize DB once per server lifecycle. Returns status dict."""
    try:
        from database.connection import db_health_check
        from database.schema import initialize_db
        health = db_health_check()
        if health["ok"]:
            initialize_db()
        return health
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


# ---------------------------------------------------------------------------
# Main dashboard page
# ---------------------------------------------------------------------------

def main():
    st.title("🌿 Carbon Footprint Estimator")
    st.caption("India-specific CO₂e estimation from bank transaction data")

    # DB Status
    db_status = _init_db()
    if db_status.get("ok"):
        st.sidebar.success("✓ Database connected", icon="🟢")
    else:
        st.sidebar.warning(
            f"Database offline — upload validation still works.\n"
            f"({db_status.get('error', 'No DATABASE_URL configured.')})",
            icon="🟡",
        )

    # Sidebar navigation hint
    st.sidebar.title("Navigation")
    st.sidebar.info(
        "Use the pages in the sidebar to:\n"
        "- 📁 **Upload Transactions**\n"
        "- 📊 **View Dashboard**\n"
        "- 🔍 **Review Transactions**\n"
        "- 📚 **Methodology & Sources**"
    )

    # Hero section
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🌍 Methodology", "India-specific", help="Uses India CEA, HCES, BEE, MoEFCC factors")
    with col2:
        st.metric("📊 Routes", "A + B Hybrid", help="Spend-based and activity-based estimation")
    with col3:
        st.metric("🔒 Privacy-first", "No account data stored", help="Sensitive identifiers are rejected at upload")

    st.divider()

    st.subheader("How it works")
    cols = st.columns(4)
    steps = [
        ("1️⃣", "Upload CSV/Excel/PDF", "Bank transaction file with date, description, amount"),
        ("2️⃣", "Validate & Clean", "Check columns, reject sensitive data, normalize merchants"),
        ("3️⃣", "Categorize", "5-tier pipeline: cache → ML → dictionary → fuzzy → LLM"),
        ("4️⃣", "Estimate CO₂e", "Apply India-specific factors (CEA, HCES, BEE, MoEFCC)"),
    ]
    for col, (icon, title, desc) in zip(cols, steps):
        with col:
            st.markdown(f"**{icon} {title}**")
            st.caption(desc)

    st.divider()

    st.subheader("⚠️ Important Disclaimer")
    st.info(
        "This is a **partial estimate** based only on transactions with supported India-specific factors. "
        "Categories without a validated India factor are shown as 'Not estimated'. "
        "The total displayed is **not your complete carbon footprint**.\n\n"
        "Upload a CSV to get started →",
        icon="ℹ️"
    )

    st.markdown(
        '<div class="footer">Carbon Footprint Estimator · India factors: CEA V21.0, HCES, BEE, MoEFCC · '
        'Not a substitute for a professional lifecycle assessment.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
else:
    main()
