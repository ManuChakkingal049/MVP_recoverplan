import streamlit as st
import pandas as pd
from copy import deepcopy

st.set_page_config(layout="wide")
st.title("🏦 Bank Recovery Simulator — Balance Sheet Roll Forward")

#########################################
# Sidebar Inputs
#########################################

st.sidebar.header("Opening Balance Sheet")

A0 = {
    "Cash": st.sidebar.number_input("Cash", 100.0),
    "HQLA": st.sidebar.number_input("HQLA Securities", 200.0),
    "Loans": st.sidebar.number_input("Loans", 400.0),
    "RealEstate": st.sidebar.number_input("Real Estate", 200.0),
}

L0 = {
    "Deposits": st.sidebar.number_input("Deposits", 600.0),
    "Wholesale": st.sidebar.number_input("Wholesale Funding", 150.0),
}

#########################################
# Haircuts
#########################################

st.sidebar.header("Haircuts")

haircuts = {
    "Cash": 0.0,
    "HQLA": st.sidebar.slider("HQLA haircut", 0.0, 0.5, 0.05),
    "Loans": st.sidebar.slider("Loan haircut", 0.0, 0.7, 0.25),
    "RealEstate": st.sidebar.slider("RE haircut", 0.0, 0.8, 0.35),
}

#########################################
# Liquidation Priority
#########################################

priority = st.sidebar.multiselect(
    "Liquidation Priority",
    ["Cash","HQLA","Loans","RealEstate"],
    default=["Cash","HQLA","Loans","RealEstate"]
)

#########################################
# Withdrawals
#########################################

st.header("Withdrawal Scenario")

txt = st.text_input(
    "Withdrawals per period (comma-separated, e.g., 50,80,120)",
    "50,80,120"
)

withdrawals = [float(x) for x in txt.split(",")]

#########################################
# Helper Functions
#########################################

def equity(A,L):
    return sum(A.values()) - sum(L.values())

def LCR(A,outflow):
    hqla = A["Cash"] + A["HQLA"]*(1-haircuts["HQLA"])
    return hqla/max(outflow,1)

#########################################
# Run Simulation
#########################################

if st.button("Run Simulation"):

    A = deepcopy(A0)
    L = deepcopy(L0)

    # store balance sheets by period
    bs_history = {}

    # Period 0 (Opening)
    bs_history["Period 0"] = {
        **A,
        **L,
        "Equity": equity(A,L)
    }

    survival=None

    for t,w in enumerate(withdrawals,1):

        # Deposit withdrawal
        L["Deposits"] -= w

        need = w

        # Liquidate assets
        for asset in priority:

            if need<=0:
                break

            avail=A[asset]
            h=haircuts[asset]

            sell=min(avail, need/(1-h))

            A[asset]-=sell
            cash=sell*(1-h)
            need-=cash

        # Compute metrics
        e = equity(A,L)
        lcr = LCR(A,w)

        # Save balance sheet
        bs_history[f"Period {t}"] = {
            **A,
            **L,
            "Equity": e
        }

        # Survival trigger
        if e<=0 or lcr<1:
            survival=t
            break

    #########################################
    # Create Balance Sheet Table
    #########################################

    df = pd.DataFrame(bs_history)

    # Order rows nicely
    order = [
        "Cash","HQLA","Loans","RealEstate",
        "Deposits","Wholesale",
        "Equity"
    ]

    df = df.loc[order]

    # Add Balance Check row
    asset_rows = ["Cash","HQLA","Loans","RealEstate"]
    liab_eq_rows = ["Deposits","Wholesale","Equity"]

    df.loc["Check (Assets - Liabilities+Equity)"] = df.loc[asset_rows].sum() - df.loc[liab_eq_rows].sum()

    #########################################
    # Display Balance Sheet
    #########################################

    st.subheader("📊 Balance Sheet Roll-Forward")
    st.dataframe(df, use_container_width=True)

    #########################################
    # Survival Output
    #########################################

    if survival:
        st.error(f"⚠️ Survival Horizon = {survival} periods")
    else:
        st.success("✅ Bank survives all periods")

    #########################################
    # Narrative Explanation
    #########################################

    st.subheader("📖 Period-wise Narrative Explanation")

    narrative = []
    prev_A = deepcopy(A0)
    prev_L = deepcopy(L0)

    for t,col in enumerate(df.columns):

        if col.startswith("Period"):
            curr_A = {k: df.loc[k,col] for k in ["Cash","HQLA","Loans","RealEstate"]}
            curr_L = {k: df.loc[k,col] for k in ["Deposits","Wholesale"]}

            # Withdrawal for this period
            w = withdrawals[t-1] if t>0 and t-1<len(withdrawals) else 0

            # Assets sold
            sold_assets=[]
            for asset in priority:
                delta = prev_A[asset] - curr_A[asset]
                if delta>0:
                    sold_assets.append(f"{delta:.2f} {asset}")

            # Equity change
            equity_change = df.loc["Equity",col] - df.loc["Equity","Period 0"] if t==0 else df.loc["Equity",col] - prev_A["Cash"] - prev_A["HQLA"] - prev_A["Loans"] - prev_A["RealEstate"] + prev_L["Deposits"] + prev_L["Wholesale"] # approximate

            line = f"**{col}:** Withdrawal={w}. "
            if sold_assets:
                line += f"Liquidated {'; '.join(sold_assets)}. "
            else:
                line += "No asset liquidation required. "
            line += f"Closing Equity={df.loc['Equity',col]:.2f}. "
            line += f"Balance Sheet Check (Assets-Liabilities+Equity)={df.loc['Check (Assets - Liabilities+Equity)',col]:.2f}"

            # Survival trigger explanation
            if survival and survival==t:
                line += " ⚠️ Survival breach occurs here."

            narrative.append(line)

            prev_A = curr_A
            prev_L = curr_L

    for line in narrative:
        st.markdown(line)
