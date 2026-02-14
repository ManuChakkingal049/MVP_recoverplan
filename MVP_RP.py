import streamlit as st
import pandas as pd
from copy import deepcopy

st.set_page_config(layout="wide")
st.title("🏦 Bank Recovery & Survival Horizon MVP")

############################################
# Sidebar — Opening Balance Sheet
############################################

st.sidebar.header("Opening Balance Sheet")

assets_input = {
    "Cash": st.sidebar.number_input("Cash", value=100.0),
    "HQLA": st.sidebar.number_input("HQLA Securities", value=200.0),
    "Loans": st.sidebar.number_input("Loans", value=400.0),
    "RealEstate": st.sidebar.number_input("Real Estate", value=200.0),
}

liabilities_input = {
    "Deposits": st.sidebar.number_input("Deposits", value=600.0),
    "Wholesale": st.sidebar.number_input("Wholesale Funding", value=150.0),
}

############################################
# Haircuts
############################################

st.sidebar.header("Liquidation Haircuts")

haircuts = {
    "Cash": 0.0,
    "HQLA": st.sidebar.slider("HQLA haircut", 0.0, 0.5, 0.05),
    "Loans": st.sidebar.slider("Loan sale haircut", 0.0, 0.7, 0.25),
    "RealEstate": st.sidebar.slider("Real Estate haircut", 0.0, 0.8, 0.35),
}

############################################
# Liquidation Priority
############################################

st.sidebar.header("Liquidation Order")

priority = st.sidebar.multiselect(
    "Select liquidation priority",
    ["Cash","HQLA","Loans","RealEstate"],
    default=["Cash","HQLA","Loans","RealEstate"]
)

############################################
# Scenario Input
############################################

st.header("Withdrawal Scenario")

mode = st.radio("Input Mode", ["Manual Input","CSV Upload"])

if mode == "Manual Input":
    txt = st.text_input(
        "Enter withdrawals per period (comma-separated)",
        "50,80,120"
    )
    withdrawals = [float(x) for x in txt.split(",")]

else:
    file = st.file_uploader("Upload CSV with column named 'withdrawal'")
    if file:
        df_up = pd.read_csv(file)
        withdrawals = df_up["withdrawal"].tolist()
    else:
        withdrawals = []

############################################
# Helper Functions
############################################

def equity(A,L):
    return sum(A.values()) - sum(L.values())

def calc_LCR(A,outflow):
    hqla_stock = A["Cash"] + A["HQLA"]*(1-haircuts["HQLA"])
    return hqla_stock / max(outflow,1)

def calc_NSFR(A,L):
    ASF = L["Deposits"]*0.9 + L["Wholesale"]*0.5
    RSF = A["Loans"]*0.85 + A["RealEstate"]
    return ASF / max(RSF,1)

############################################
# Simulation
############################################

if st.button("Run Simulation"):

    A = deepcopy(assets_input)
    L = deepcopy(liabilities_input)

    records=[]
    survival=None

    for t,w in enumerate(withdrawals,1):

        openA = A.copy()
        openL = L.copy()

        # Deposit runoff
        L["Deposits"] -= w

        need = w
        realized_loss = 0

        # Liquidation process
        for asset in priority:

            if need <= 0:
                break

            available = A[asset]
            haircut = haircuts[asset]

            if available <= 0:
                continue

            sell = min(available, need/(1-haircut))

            A[asset] -= sell
            cash_generated = sell*(1-haircut)

            realized_loss += sell*haircut
            need -= cash_generated

        # Metrics
        e = equity(A,L)
        lcr = calc_LCR(A,w)
        nsfr = calc_NSFR(A,L)

        records.append({
            "Period":t,
            "Withdrawal":w,

            # Opening balances
            "Open_Cash":openA["Cash"],
            "Open_HQLA":openA["HQLA"],
            "Open_Loans":openA["Loans"],
            "Open_RE":openA["RealEstate"],

            # Closing balances
            "Close_Cash":A["Cash"],
            "Close_HQLA":A["HQLA"],
            "Close_Loans":A["Loans"],
            "Close_RE":A["RealEstate"],

            "Deposits":L["Deposits"],
            "Wholesale":L["Wholesale"],

            "Equity":e,
            "LCR":lcr,
            "NSFR":nsfr,
            "Realized_Loss":realized_loss
        })

        # Survival triggers
        if e <= 0 or lcr < 1 or sum(A.values()) <= 0:
            survival = t
            break

    df = pd.DataFrame(records)

############################################
# Outputs
############################################

    st.subheader("📊 Balance Sheet Roll-Forward")
    st.dataframe(df, use_container_width=True)

    col1,col2 = st.columns(2)

    with col1:
        st.subheader("Liquidity Metrics")
        st.line_chart(
            df.set_index("Period")[["LCR","NSFR"]]
        )

    with col2:
        st.subheader("Equity Path")
        st.line_chart(
            df.set_index("Period")["Equity"]
        )

    st.subheader("Asset Depletion (Closing Balances)")
    st.area_chart(
        df.set_index("Period")[
            ["Close_Cash","Close_HQLA","Close_Loans","Close_RE"]
        ]
    )

    if survival:
        st.error(f"⚠️ Survival Horizon = {survival} periods")
    else:
        st.success("✅ Bank survives all periods")
