import streamlit as st
import pandas as pd
from copy import deepcopy

st.set_page_config(layout="wide")
st.title("🏦 Bank Recovery Simulator — Haircuts & Cash Floor")

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

st.sidebar.header("Regulatory Requirement")
min_cash = st.sidebar.number_input(
    "Minimum Cash Requirement",
    min_value=0.0,
    value=20.0,
    step=1.0,
    help="Regulator-mandated minimum cash to hold"
)

st.sidebar.header("Haircuts")
haircuts = {
    "Cash": 0.0,
    "HQLA": st.sidebar.slider("HQLA haircut", 0.0, 0.5, 0.05),
    "Loans": st.sidebar.slider("Loan haircut", 0.0, 0.7, 0.25),
    "RealEstate": st.sidebar.slider("RE haircut", 0.0, 0.8, 0.35),
}

st.sidebar.header("Liquidation Priority")
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
    "Withdrawals per period (comma-separated, e.g., 50,80,120,40,60,...):",
    "50,80,120"
)
withdrawals = [float(x) for x in txt.split(",")]

#########################################
# Helper Functions
#########################################

def equity(A,L):
    return sum(A.values()) - sum(L.values())

#########################################
# Run Simulation
#########################################

if st.button("Run Simulation"):

    A = deepcopy(A0)
    L = deepcopy(L0)
    bs_history = {}

    # Period 0
    bs_history["Period 0"] = {**A, **L, "Equity": equity(A,L)}

    survival = None

    for t, w in enumerate(withdrawals, 1):

        # Withdraw deposits
        L["Deposits"] -= w
        need = w

        # Liquidate assets to meet withdrawal (gross up for haircut)
        for asset in priority:
            if need <= 0:
                break
            available = A[asset]
            h = haircuts[asset]
            if available <= 0:
                continue

            sell = min(available, need / (1 - h))  # gross up for haircut
            cash_generated = sell * (1 - h)
            A[asset] -= sell
            need -= cash_generated

        # Restore minimum cash if possible (gross up for haircut)
        cash_deficit = max(min_cash - A["Cash"], 0)
        for asset in priority:
            if cash_deficit <= 0:
                break
            if asset == "Cash":
                continue
            available = A[asset]
            h = haircuts[asset]
            if available <= 0:
                continue

            sell = min(available, cash_deficit / (1 - h))  # gross up for haircut
            A[asset] -= sell
            A["Cash"] += sell * (1 - h)
            cash_deficit -= sell * (1 - h)

        # Survival breach only if withdrawals cannot be met or cash floor cannot be restored
        if need > 0 or (A["Cash"] < min_cash and all(A[a] <= 0 for a in priority if a != "Cash")):
            survival = t

        # Save balance sheet
        bs_history[f"Period {t}"] = {**A, **L, "Equity": equity(A,L)}

        # Stop if survival breach
        if survival:
            break

    #########################################
    # Balance Sheet Table
    #########################################

    df = pd.DataFrame(bs_history)
    rows_order = ["Cash","HQLA","Loans","RealEstate","Deposits","Wholesale","Equity"]
    df = df.loc[rows_order]

    # Add balance check
    asset_rows = ["Cash","HQLA","Loans","RealEstate"]
    liab_eq_rows = ["Deposits","Wholesale","Equity"]
    df.loc["Check (Assets - Liabilities+Equity)"] = df.loc[asset_rows].sum() - df.loc[liab_eq_rows].sum()

    st.subheader("📊 Balance Sheet Roll-Forward")
    st.dataframe(df, use_container_width=True)

    #########################################
    # Survival Output
    #########################################

    if survival:
        st.error(f"⚠️ Survival Breach Occurs at Period {survival}")
    else:
        st.success("✅ Bank survives all periods")

    #########################################
    # Narrative Explanation
    #########################################

    st.subheader("📖 Period-wise Narrative Explanation")
    prev_A = deepcopy(A0)
    prev_L = deepcopy(L0)

    for t, col in enumerate(df.columns):
        curr_A = {k: df.loc[k,col] for k in ["Cash","HQLA","Loans","RealEstate"]}
        curr_L = {k: df.loc[k,col] for k in ["Deposits","Wholesale"]}
        w = withdrawals[t-1] if t-1 < len(withdrawals) else 0
        sold_assets = []
        for asset in priority:
            delta = prev_A[asset] - curr_A[asset]
            if delta > 0:
                sold_assets.append(f"{delta:.2f} {asset}")
        line = f"**{col}:** Withdrawal={w}. "
        if sold_assets:
            line += f"Liquidated {'; '.join(sold_assets)}. "
        else:
            line += "No asset liquidation required. "
        line += f"Closing Cash={curr_A['Cash']:.2f} (Floor={min_cash}). "
        line += f"Closing Equity={df.loc['Equity',col]:.2f}. "
        line += f"Balance Sheet Check={df.loc['Check (Assets - Liabilities+Equity)',col]:.2f}"
        if survival and survival==t:
            line += " ⚠️ Survival breach occurs here."
        st.markdown(line)
        prev_A = curr_A
        prev_L = curr_L
