// src/app/services/PriceService.ts
 
const API_BASE = "http://localhost:5000";

export type PricePredictionInput = {
  area_sqm:       number;
  neighborhood:   string;
  property_type:  string;
  classification?: string;
  plan_no?:        string;
  parcel_no?:      string;
  year?:           number;
  month?:          number;
};


export type PricePredictionResult = {
  price_per_sqm:    number;
  total_price:      number;
  price_range:      { low: number; high: number };
  demand_indicator: string;
  demand_basis:     string;
  below_market_pct: number;
  max_bid:          number;
  annual_growth:    number;
};

export type PropertyRecommendation = {
  rank:               number;
  property_type:      string;
  price_per_sqm:      number;
  total_value:        number;
  real_avg_sqm:       number | null;
  tx_count:           number;
  confidence:         string;
  market_share:       number;
  value_multiplier:   number;
  value_increase_pct: number;
  profit:             number | null;   // null if no budget provided
  roi:                number | null;   // null if no budget provided
  has_roi:            boolean;
};

export type RecommendResult = {
  area:               number;
  neighborhood:       string;
  classification:     string;
  current_type:       string;
  global_land_avg:    number;
  has_roi:            boolean;
  land_price:         number;
  development_budget: number;
  total_investment:   number | null;
  recommendations:    PropertyRecommendation[];
  best_use:           string;
  best_value:         number;
  best_multiplier:    number;
  best_roi:           number | null;
};

export type RecommendInput = Omit<PricePredictionInput, "property_type"> & {
  property_type?:      string;   
  land_price?:         number;
  development_budget?: number;
};

export const PriceService = {

  // ── Predict single property price ─────────────────────────────────────────
  async predict(input: PricePredictionInput): Promise<PricePredictionResult> {
    const res = await fetch(`${API_BASE}/predict`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        area_sqm:       input.area_sqm,
        neighborhood:   input.neighborhood,
        property_type:  input.property_type,
        classification: input.classification ?? "سكني",
        plan_no:        input.plan_no   ?? "0",
        parcel_no:      input.parcel_no ?? "0",
        year:           input.year  ?? new Date().getFullYear(),
        month:          input.month ?? new Date().getMonth() + 1,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error ?? "تعذر الحصول على تقييم السعر");
    }
    return res.json();
  },

  // ── Recommend best land use ────────────────────────────────────────────────
  async recommend(input: RecommendInput): Promise<RecommendResult> {
    const res = await fetch(`${API_BASE}/recommend`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        area_sqm:           input.area_sqm,
        neighborhood:       input.neighborhood,
        property_type:      input.property_type  ?? "",
        classification:     input.classification ?? "سكني",
        plan_no:            input.plan_no   ?? "0",
        parcel_no:          input.parcel_no ?? "0",
        year:               input.year  ?? new Date().getFullYear(),
        month:              input.month ?? new Date().getMonth() + 1,
        land_price:         input.land_price         ?? 0,
        development_budget: input.development_budget ?? 0,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error ?? "تعذر الحصول على التوصية");
    }
    return res.json();
  },

  // ── Get neighborhoods list ─────────────────────────────────────────────────
  async getNeighborhoods(): Promise<string[]> {
    const res = await fetch(`${API_BASE}/neighborhoods`);
    if (!res.ok) throw new Error("تعذر تحميل قائمة الأحياء");
    return res.json();
  },

  // ── Format price as 2.4M or 650K ─────────────────────────────────────────
  formatPrice(value: number): string {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000)     return `${(value / 1_000).toFixed(0)}K`;
    return value.toLocaleString("en-US");
  },
};