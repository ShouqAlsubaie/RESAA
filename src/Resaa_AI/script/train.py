import os
import warnings
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from catboost import CatBoostRegressor, Pool

warnings.filterwarnings("ignore")


# ══════════════════════════════════════════════════════════════════════════════
# MODEL A — Property Price Prediction (Jeddah Real Estate)
# ══════════════════════════════════════════════════════════════════════════════

DATA_PATH = "src/Resaa_AI/data/raw/Jeddah.xlsx"

COLUMN_RENAME = {
    "التصنيف":                 "classification",
    "النوع":                   "property_type",
    "سعر الصفقة (ريال)":       "deal_price",
    "المساحة (متر مربع)":      "area_sqm",
    "سعر المتر المربع (ريال)":  "price_per_sqm",
    "تاريخ الصفقة":            "deal_date",
    "الحي":                    "neighborhood",
    "المخطط":                  "plan_no",
    "القطعة":                  "parcel_no",
}
TARGET = "price_per_sqm"
AREA   = "area_sqm"


# 1. LOAD & CLEAN 
df = pd.read_excel(
    DATA_PATH,
    engine="openpyxl",
    dtype={"القطعة": str, "المخطط": str},
)
print(f"Raw rows : {len(df):,}")

# Keep only the columns we need
df = df[list(COLUMN_RENAME.keys())].rename(columns=COLUMN_RENAME)
df = df.drop_duplicates()

# Basic price/area filters
df = df[
    (df["deal_price"]   >= 50_000) &
    (df[TARGET]         >= 50)     &
    (df[AREA]           >  0)
].dropna(subset=[AREA]).reset_index(drop=True)

# Remove outliers per property type (IQR)
def remove_outliers(df, col):
    groups = []
    for _, g in df.groupby("property_type"):
        q1, q3 = g[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        groups.append(g[(g[col] >= q1 - 1.5 * iqr) & (g[col] <= q3 + 1.5 * iqr)])
    return pd.concat(groups).reset_index(drop=True)

df = remove_outliers(df, TARGET)
df = remove_outliers(df, AREA)
print(f"After cleaning : {len(df):,}")


# 2. FEATURE ENGINEERING
# Date features
df["deal_date"] = pd.to_datetime(df["deal_date"], dayfirst=True, errors="coerce")
df["year"]      = df["deal_date"].dt.year.fillna(2024).astype(int)
df["month"]     = df["deal_date"].dt.month.fillna(1).astype(int)
df = df.drop(columns=["deal_date"])

# Clean text
for col in ["neighborhood", "plan_no", "parcel_no"]:
    df[col] = df[col].astype(str).str.strip()

# Log area
df["log_area"]     = np.log1p(df[AREA])

# Area relative to the neighborhood median
df["area_vs_nbhd"] = df[AREA] / (df.groupby("neighborhood")[AREA].transform("median") + 1)

# Converts month (1-12) into sin/cos so model understands
df["sin_month"]    = np.sin(2 * np.pi * df["month"] / 12)
df["cos_month"]    = np.cos(2 * np.pi * df["month"] / 12)

df.to_csv("src/Resaa_AI/data/cleaned/Jeddah_preprocessed.csv", index=False, encoding="utf-8-sig")

# ── 3. PREPARE X & y ─────────────────────────────────────────────────────────

y = np.log1p(df[TARGET].values)

X = df.drop(columns=["deal_price", TARGET])

A_CAT_COLS = ["classification", "property_type", "neighborhood", "plan_no", "parcel_no"]
for col in A_CAT_COLS:
    X[col] = X[col].astype(str)
a_cat_idx = [X.columns.get_loc(c) for c in A_CAT_COLS]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"Train / test : {len(X_train):,} / {len(X_test):,}")
# ── 4. TRAIN

model_a = CatBoostRegressor(
    iterations            = 3000,
    learning_rate         = 0.03,
    depth                 = 8,
    l2_leaf_reg           = 3,
    loss_function         = "RMSE",
    eval_metric           = "RMSE",
    random_seed           = 42,
    verbose               = False,
    early_stopping_rounds = 100,
)

model_a.fit(
    Pool(X_train, y_train, cat_features=a_cat_idx),
    eval_set=Pool(X_test,  y_test,  cat_features=a_cat_idx),
    use_best_model=True,
)

model_a.save_model("src/Resaa_AI/models/price_model.cbm")


# ── 5. EVALUATE ───────────────────────────────────────────────────────────────
y_pred_log = model_a.predict(Pool(X_test, cat_features=a_cat_idx))

# Convert back from log scale
yr     = np.expm1(y_test)       # actual prices
yp     = np.expm1(y_pred_log)   # predicted prices

n      = len(yr)             # number of test samples
y_mean = np.mean(yr)         # mean of actual prices
p      = X_test.shape[1]     # number of features

# ── Basic metrics ─────────────────────────────────────────────────────────────
mae       = mean_absolute_error(yr, yp)
mse       = mean_squared_error(yr, yp)
rmse      = np.sqrt(mse)
r2        = r2_score(y_test, y_pred_log)
mape      = np.mean(np.abs((yr - yp) / yr)) * 100

# ── Residuals ─────────────────────────────────────────────────────────────────
residuals = yr - yp

# ── SSE, SSR, SST ─────────────────────────────────────────────────────────────
SSE = np.sum(residuals ** 2)          # Sum of Squared Errors
SST = np.sum((yr - y_mean) ** 2)      # Sum of Squared Total
SSR = np.sum((yp - y_mean) ** 2)      # Sum of Squared Regression

# ── Additional metrics ────────────────────────────────────────────────────────
r2_manual     = 1 - (SSE / SST)                                    # R² from scratch
r2_adj        = 1 - (1 - r2_manual) * (n - 1) / (n - p - 1)       # Adjusted R²
SEE           = np.sqrt(SSE / (n - p - 1))                         # Standard Error of Estimate
med_ae        = np.median(np.abs(residuals))                        # Median Absolute Error
sse_sst_check = abs((SSR + SSE) - SST)
max_error     = np.max(np.abs(residuals))                           # Max single error
w10           = np.mean(np.abs((yr - yp) / yr) <= 0.10) * 100      # Within 10%
w20           = np.mean(np.abs((yr - yp) / yr) <= 0.20) * 100      # Within 20%

print(f"""
╔══════════════════════════════════════════════════════╗
║      Model A — CatBoost Evaluation Report            ║
╠══════════════════════════════════════════════════════╣
║  Test samples (n)     : {n:,}
║  Features (p)         : {p}
║  Mean actual price    : {y_mean:,.0f} SAR/m²
╠══════════════════════════════════════════════════════╣
║  SUM OF SQUARES                                      ║
║  SSE                  : {SSE:,.0f}
║  SSR                  : {SSR:,.0f}
║  SST                  : {SST:,.0f}
║  SSR + SSE diff       : {sse_sst_check:,.0f}
╠══════════════════════════════════════════════════════╣
║  STANDARD METRICS                                    ║
║  R²   (sklearn)       : {r2:.4f}
║  R²   (manual)        : {r2_manual:.4f}
║  Adjusted R²          : {r2_adj:.4f}
║  MSE                  : {mse:,.0f}
║  RMSE                 : {rmse:,.0f} SAR/m²
║  MAE                  : {mae:,.0f} SAR/m²
║  Median Abs Error     : {med_ae:,.0f} SAR/m²
║  Std Error (SEE)      : {SEE:,.0f}
║  Max Error            : {max_error:,.0f} SAR/m²
║  MAPE                 : {mape:.2f}%
╠══════════════════════════════════════════════════════╣
║  TOLERANCE                                           ║
║  Within 10% error     : {w10:.1f}%
║  Within 20% error     : {w20:.1f}%
╚══════════════════════════════════════════════════════╝
""")


# ══════════════════════════════════════════════════════════════════════════════
# MODEL B — Auction Starting Price Strategy (Soum Auctions)
# ══════════════════════════════════════════════════════════════════════════════

B_DATA_PATH = "src/Resaa_AI/data/cleaned/soum_base_cleaned.csv"


# ── 1. LOAD & CLEAN ───────────────────────────────────────────────────────────
df_b = pd.read_csv(B_DATA_PATH)
print(f"\n[Model B] Original data: {df_b.shape[0]:,} rows, {df_b.shape[1]} columns")

B_TARGET = "highest_bid"

LEAKAGE_COLS = ["end_time", "total_sales", "price_per_sqm", "area_log"]
df_b = df_b.drop(columns=[c for c in LEAKAGE_COLS if c in df_b.columns], errors="ignore")

df_b["start_time"] = pd.to_datetime(df_b["start_time"], errors="coerce")
df_b = df_b[df_b["start_time"].notna()].copy()
df_b = df_b[df_b[B_TARGET].notna()  & (df_b[B_TARGET]      > 0)].copy()
df_b = df_b[df_b["start_price"].notna() & (df_b["start_price"] > 0)].copy()
df_b = df_b[df_b["area"].notna()    & (df_b["area"]         > 0)].copy()

if "duration_hours" in df_b.columns:
    upper_dur = df_b["duration_hours"].quantile(0.99)
    df_b["duration_hours"] = df_b["duration_hours"].clip(lower=1, upper=upper_dur)
else:
    df_b["duration_hours"] = 48.0

df_b = df_b.drop_duplicates().reset_index(drop=True)
print(f"[Model B] After cleaning: {df_b.shape[0]:,} rows")


# ── 2. FEATURE ENGINEERING ────────────────────────────────────────────────────
df_b["sale_ratio"]        = (df_b[B_TARGET] / df_b["start_price"]).clip(lower=1.0)
b_ratio_cap               = df_b["sale_ratio"].quantile(0.99)
df_b["sale_ratio_capped"] = df_b["sale_ratio"].clip(upper=b_ratio_cap)

def b_map_time_period(hour):
    if 6 <= hour <= 11:    return "morning"
    elif 12 <= hour <= 16: return "afternoon"
    elif 17 <= hour <= 21: return "evening"
    else:                  return "night"

def b_month_part(dt):
    if dt.day <= 10:   return "beginning_month"
    elif dt.day <= 20: return "middle_month"
    else:              return "end_month"

df_b["time_period"]  = df_b["start_hour"].apply(b_map_time_period)
df_b["day_group"]    = np.where(df_b["start_dayofweek"].isin([4, 5]), "weekend", "weekday")
df_b["month_part"]   = df_b["start_time"].apply(b_month_part)
df_b["season_group"] = df_b["start_quarter"].apply(lambda q: f"Q{int(q)}")

df_b["is_weekend"] = df_b["start_dayofweek"].isin([4, 5]).astype(int)
df_b["is_morning"] = df_b["start_hour"].between(6,  11).astype(int)
df_b["is_evening"] = df_b["start_hour"].between(17, 21).astype(int)

df_b["start_price_log"]    = np.log1p(df_b["start_price"])
df_b["area_log"]           = np.log1p(df_b["area"])
df_b["duration_log"]       = np.log1p(df_b["duration_hours"])
df_b["start_price_per_sqm"]= df_b["start_price"] / (df_b["area"] + 1)
df_b["area_x_price"]       = df_b["area"] * df_b["start_price"]

df_b["hour_sin"]  = np.sin(2 * np.pi * df_b["start_hour"]   / 24)
df_b["hour_cos"]  = np.cos(2 * np.pi * df_b["start_hour"]   / 24)
df_b["month_sin"] = np.sin(2 * np.pi * df_b["start_month"]  / 12)
df_b["month_cos"] = np.cos(2 * np.pi * df_b["start_month"]  / 12)

df_b["area_bucket"]        = pd.qcut(df_b["area"],        q=5, duplicates="drop").astype(str)
df_b["start_price_bucket"] = pd.qcut(df_b["start_price"], q=5, duplicates="drop").astype(str)

def b_group_rare(series, min_count=8):
    series = series.fillna("Unknown").astype(str).str.strip()
    vc     = series.value_counts()
    keep   = vc[vc >= min_count].index
    return series.where(series.isin(keep), "Other")

for col in ["city", "district", "property_type", "region"]:
    df_b[col] = df_b[col].fillna("Unknown").astype(str).str.strip()

df_b["city_grouped"]     = b_group_rare(df_b["city"],          min_count=8)
df_b["district_grouped"] = b_group_rare(df_b["district"],      min_count=8)
df_b["property_grouped"] = b_group_rare(df_b["property_type"], min_count=6)
df_b["region_grouped"]   = b_group_rare(df_b["region"],        min_count=6)


# ── 3. TIME SPLIT ─────────────────────────────────────────────────────────────
df_b      = df_b.sort_values("start_time").reset_index(drop=True)
b_split   = int(len(df_b) * 0.80)
b_train   = df_b.iloc[:b_split].copy()
b_val     = df_b.iloc[b_split:].copy()
print(f"[Model B] Train size: {len(b_train):,} | Validation size: {len(b_val):,}")


# ── 4. HISTORICAL RATIO FEATURES ─────────────────────────────────────────────
b_global_ratio = b_train["sale_ratio_capped"].mean()

def b_smooth_map(train, group_col, target_col, global_mean, min_samples=5):
    stats = train.groupby(group_col)[target_col].agg(["mean", "count"]).reset_index()
    stats["smooth"] = (
        (stats["mean"] * stats["count"] + global_mean * min_samples)
        / (stats["count"] + min_samples)
    )
    return stats.set_index(group_col)["smooth"].to_dict()

b_time_period_map = b_smooth_map(b_train, "time_period",      "sale_ratio_capped", b_global_ratio, 6)
b_day_group_map   = b_smooth_map(b_train, "day_group",        "sale_ratio_capped", b_global_ratio, 6)
b_month_part_map  = b_smooth_map(b_train, "month_part",       "sale_ratio_capped", b_global_ratio, 6)
b_season_map      = b_smooth_map(b_train, "season_group",     "sale_ratio_capped", b_global_ratio, 6)
b_ptype_map       = b_smooth_map(b_train, "property_grouped", "sale_ratio_capped", b_global_ratio, 8)
b_region_map      = b_smooth_map(b_train, "region_grouped",   "sale_ratio_capped", b_global_ratio, 8)

b_train["ptype_season_key"] = b_train["property_grouped"] + "__" + b_train["season_group"]
b_ptype_season_map = b_smooth_map(b_train, "ptype_season_key", "sale_ratio_capped", b_global_ratio, 8)

def b_apply_history(data):
    data = data.copy()
    data["ptype_season_key"]        = data["property_grouped"] + "__" + data["season_group"]
    data["time_period_ratio_hist"]  = data["time_period"].map(b_time_period_map).fillna(b_global_ratio)
    data["day_group_ratio_hist"]    = data["day_group"].map(b_day_group_map).fillna(b_global_ratio)
    data["month_part_ratio_hist"]   = data["month_part"].map(b_month_part_map).fillna(b_global_ratio)
    data["season_ratio_hist"]       = data["season_group"].map(b_season_map).fillna(b_global_ratio)
    data["ptype_ratio_hist"]        = data["property_grouped"].map(b_ptype_map).fillna(b_global_ratio)
    data["region_ratio_hist"]       = data["region_grouped"].map(b_region_map).fillna(b_global_ratio)
    data["ptype_season_ratio_hist"] = data["ptype_season_key"].map(b_ptype_season_map).fillna(b_global_ratio)
    return data

b_train = b_apply_history(b_train)
b_val   = b_apply_history(b_val)


# ── 5. PREPARE X & y ─────────────────────────────────────────────────────────
B_EXCLUDE = [
    "auction_name", "start_time", "city", "district", "region",
    "property_type", "highest_bid", "bids_count",
    "sale_ratio", "sale_ratio_capped", "ptype_season_key"
]
B_FEATURES = [c for c in b_train.columns if c not in B_EXCLUDE]

X_b_tr  = b_train[B_FEATURES].copy()
X_b_val = b_val[B_FEATURES].copy()

y_b_tr  = np.log1p(b_train["sale_ratio_capped"])
y_b_val = np.log1p(b_val["sale_ratio_capped"])

B_CAT_COLS = X_b_tr.select_dtypes(include="object").columns.tolist()
b_cat_idx  = [X_b_tr.columns.get_loc(c) for c in B_CAT_COLS]

print(f"[Model B] Features: {len(B_FEATURES)} | Categorical: {B_CAT_COLS}")


# ── 6. TRAIN ──────────────────────────────────────────────────────────────────
model_b = CatBoostRegressor(
    iterations   = 800,
    learning_rate= 0.02,
    depth        = 4,
    l2_leaf_reg  = 10,
    loss_function= "RMSE",
    eval_metric  = "RMSE",
    random_seed  = 42,
    verbose      = 200,
    od_type      = "Iter",
    od_wait      = 120,
)

model_b.fit(
    X_b_tr,
    y_b_tr,
    cat_features=b_cat_idx,
    eval_set=(X_b_val, y_b_val),
    use_best_model=True,
)

model_b.save_model("src/Resaa_AI/models/starting_price_model.cbm")
print("[Model B] Saved → starting_price_model.cbm")

# ── Save model metadata — features, cat cols, bucket modes, global ratio ──────
# App.py reads this file at startup instead of recomputing from the CSV,
# which guarantees the exact same feature list and values used during training.
import json

_b_exclude_set = set(B_EXCLUDE)
auction_meta = {
    "features":                B_FEATURES,
    "cat_cols":                B_CAT_COLS,
    "area_bucket_mode":        str(b_train["area_bucket"].mode()[0]),
    "start_price_bucket_mode": str(b_train["start_price_bucket"].mode()[0]),
    "global_ratio":            float(b_global_ratio),
    "time_period_map":         {k: float(v) for k, v in b_time_period_map.items()},
    "day_group_map":           {k: float(v) for k, v in b_day_group_map.items()},
    "month_part_map":          {k: float(v) for k, v in b_month_part_map.items()},
    "season_map":              {k: float(v) for k, v in b_season_map.items()},
    "ptype_map":               {k: float(v) for k, v in b_ptype_map.items()},
    "region_map":              {k: float(v) for k, v in b_region_map.items()},
    "ptype_season_map":        {k: float(v) for k, v in b_ptype_season_map.items()},
    "known_cities":            sorted(b_train["city_grouped"].dropna().unique().tolist()),
    "known_districts":         sorted(b_train["district_grouped"].dropna().unique().tolist()),
    "known_properties":        sorted(b_train["property_grouped"].dropna().unique().tolist()),
    "known_regions":           sorted(b_train["region_grouped"].dropna().unique().tolist()),
}

with open("src/Resaa_AI/models/auction_model_meta.json", "w", encoding="utf-8") as f:
    json.dump(auction_meta, f, ensure_ascii=False, indent=2)

print("[Model B] Saved → auction_model_meta.json")


# ── 7. EVALUATE ───────────────────────────────────────────────────────────────
b_pred_ratio      = np.expm1(model_b.predict(X_b_val)).clip(min=1.0)
b_pred_final      = X_b_val["start_price"].values * b_pred_ratio
b_actual_final    = b_val["highest_bid"].values

b_mae  = mean_absolute_error(b_actual_final, b_pred_final)
b_rmse = np.sqrt(mean_squared_error(b_actual_final, b_pred_final))
b_r2   = r2_score(b_actual_final, b_pred_final)
b_wape = (
    np.sum(np.abs(b_actual_final - b_pred_final))
    / np.sum(np.abs(b_actual_final))
    * 100
)

print(f"""
╔══════════════════════════════════════════════════════╗
║      Model B — Auction Strategy Evaluation           ║
╠══════════════════════════════════════════════════════╣
║  Validation samples   : {len(b_actual_final):,}
╠══════════════════════════════════════════════════════╣
║  MAE                  : {b_mae:,.0f} SAR
║  RMSE                 : {b_rmse:,.0f} SAR
║  R²                   : {b_r2:.4f}
║  WAPE                 : {b_wape:.2f}%
╚══════════════════════════════════════════════════════╝
""")