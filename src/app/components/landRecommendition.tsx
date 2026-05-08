import React, { useState, useEffect, useCallback } from "react";
import {
  Loader2, AlertTriangle, TrendingUp, TrendingDown,
  Home, Building2, Store, LandPlot, Calculator,
} from "lucide-react";
import { PriceService, RecommendResult } from "../services/PriceService";

type Props = {
  area_sqm:       number;
  neighborhood:   string;
  classification: string;
  property_type:  string;
  plan_no:        string;
  parcel_no:      string;
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function typeIcon(type: string) {
  if (type.includes("فيلا"))                                                                                    return <Home      className="w-4 h-4" />;
  if (type.includes("شقة") || type.includes("مبنى"))                                                           return <Building2 className="w-4 h-4" />;
  if (type.includes("تجاري") || type.includes("محل") || type.includes("مكتب") || type.includes("وحدة تجارية")) return <Store     className="w-4 h-4" />;
  return <LandPlot className="w-4 h-4" />;
}

function typeAction(type: string): string {
  if (type.includes("شقة"))          return "تطوير وحدات سكنية للبيع أو الإيجار";
  if (type.includes("فيلا"))         return "بناء فيلا سكنية وبيعها";
  if (type.includes("وحدة تجارية")) return "تطوير وحدات تجارية للبيع أو الإيجار";
  if (type.includes("محل"))          return "تطوير محلات تجارية";
  if (type.includes("مكتب"))         return "تطوير مكاتب إدارية";
  if (type.includes("مبنى"))         return "بناء مبنى سكني متعدد الطوابق";
  return                                     "بيع الأرض مباشرة دون تطوير";
}

function rankTheme(rank: number) {
  if (rank === 2) return {
    card:   "border-slate-200 bg-white",
    icon:   "bg-[#91C6BC]/20 text-[#30364F]",
    name:   "text-slate-700",
    action: "text-slate-400",
    bar:    "bg-[#91C6BC]",
  };
  return {
    card:   "border-slate-100 bg-slate-50/50",
    icon:   "bg-slate-100 text-slate-400",
    name:   "text-slate-500",
    action: "text-slate-300",
    bar:    "bg-slate-200",
  };
}

function barWidth(value: number, max: number): number {
  return Math.round((value / max) * 100);
}

function confidenceStyle(conf: string): string {
  if (conf === "عالي")  return "text-emerald-600 bg-emerald-50 border-emerald-200";
  if (conf === "متوسط") return "text-amber-600 bg-amber-50 border-amber-200";
  return "text-red-500 bg-red-50 border-red-200";
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function LandRecommendation({
  area_sqm, neighborhood, classification, property_type,
  plan_no, parcel_no, current_price,
}: Props) {
  const [result,        setResult]        = useState<RecommendResult | null>(null);
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState<string | null>(null);
  const [budgetInput,   setBudgetInput]   = useState<string>("");
  const [showBudget,    setShowBudget]    = useState(false);
  const [appliedBudget, setAppliedBudget] = useState<number>(0);

  const fetchRecommendations = useCallback((budget: number) => {
    setLoading(true);
    setError(null);
    PriceService.recommend({
      area_sqm, neighborhood, classification, property_type,
      plan_no, parcel_no,
      land_price:         current_price,
      development_budget: budget,
    })
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [area_sqm, neighborhood, classification, property_type, current_price]);

  useEffect(() => {
    fetchRecommendations(0);
  }, [fetchRecommendations]);

  const handleApplyBudget = () => {
    const budget = Number(budgetInput.replace(/,/g, ""));
    if (budget <= 0)                    { alert("الرجاء إدخال ميزانية صحيحة"); return; }
    if (budget < 100_000)               { alert("الحد الأدنى للميزانية 100,000 ر.س"); return; }
    if (budget > area_sqm * 10_000)     { alert(`الميزانية مرتفعة جداً للمساحة ${area_sqm} م²`); return; }
    setAppliedBudget(budget);
    fetchRecommendations(budget);
  };

  const maxValue     = result ? Math.max(...result.recommendations.map((r) => r.total_value)) : 1;
  const otherOptions = result?.recommendations.filter((r) => r.rank !== 1) ?? [];

  return (
    // No outer card wrapper — this sits inside AuctionDetailPage's white card
    // styled to match تحليل العقار panel
    <div className="mt-4 bg-white border border-emerald-100 rounded-xl p-6 shadow-sm space-y-6">

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-8 gap-3 text-slate-500">
          <Loader2 className="w-6 h-6 animate-spin text-emerald-500" />
          <span className="text-sm">جارٍ تحليل الخيارات الاستثمارية...</span>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="flex items-center gap-2 text-red-500 text-sm bg-red-50 p-3 rounded-lg">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-4">

        
          {/* ── Best use — rank 1 ── */}
          <div className="grid grid-cols-2 gap-6">
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-100 text-center">
              <div className="text-xs text-slate-500 font-bold mb-2">الاستخدام الأمثل</div>
              <div className="text-2xl font-black text-[#30364F]">{result.best_use}</div>
              <div className="text-[14px] text-slate-400 mt-1">{typeAction(result.best_use)}</div>
            </div>

            <div className="p-4 bg-slate-50 rounded-lg border border-slate-100 text-center">
              {result.has_roi && result.best_roi !== null ? (
                <>
                  <div className="text-xs text-slate-500 font-bold mb-2">العائد على الاستثمار</div>
                  <div className={`text-2xl font-black ${result.best_roi > 0 ? "text-emerald-600" : "text-red-500"}`}>
                    {result.best_roi > 0 ? "+" : ""}{result.best_roi}%
                  </div>
                  <div className="text-[10px] text-emerald-600 mt-1 flex items-center justify-center gap-1">
                    <TrendingUp className="w-3 h-3" /> ROI
                  </div>
                </>
              ) : (
                <>
                  <div className="text-xs text-slate-500 font-bold mb-2">مضاعف القيمة</div>
                  <div className="text-2xl font-black text-[#30364F]">
                    {result.best_multiplier}x
                  </div>
                  <div className="text-[12px] text-emerald-600 mt-1 flex items-center justify-center gap-1">
                    <TrendingUp className="w-3 h-3" /> مقارنةً بالأرض الخام
                  </div>
                </>
              )}
            </div>
          </div>

          {/* ── Other options — rank 2+ ── */}
          {otherOptions.length > 0 && (
            <div>
              <h4 className="font-bold text-sm mb-3">خيارات أخرى</h4>
              <ul className="space-y-2">
                {otherOptions.map((rec) => {
                  const t        = rankTheme(rec.rank);
                  const pct      = barWidth(rec.total_value, maxValue);
                  const isProfit = rec.roi !== null ? rec.roi > 0 : rec.value_multiplier >= 1;

                  return (
                    <li key={rec.property_type} className={`rounded-xl border p-3 ${t.card}`}>
                      <div className="flex items-start gap-3">

                        {/* Icon */}
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${t.icon}`}>
                          {typeIcon(rec.property_type)}
                        </div>

                        <div className="flex-1 min-w-0">

                          {/* Row 1: name + badge */}
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-1.5">
                              <span className={`font-bold text-sm ${t.name}`}>{rec.property_type}</span>
                              <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold border ${confidenceStyle(rec.confidence)}`}>
                                {rec.confidence}
                              </span>
                            </div>

                            {rec.has_roi && rec.roi !== null ? (
                              <span className={`text-xs font-black px-2 py-0.5 rounded-lg flex items-center gap-0.5 ${
                                rec.roi > 0 ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-500"
                              }`}>
                                {rec.roi > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                ROI: {rec.roi > 0 ? "+" : ""}{rec.roi}%
                              </span>
                            ) : (
                              <span className={`text-xs font-black px-2 py-0.5 rounded-lg flex items-center gap-0.5 ${
                                isProfit ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"
                              }`}>
                                {isProfit ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                {rec.value_multiplier}x
                              </span>
                            )}
                          </div>

                          {/* Action */}
                          <p className={`text-[11px] mb-1.5 ${t.action}`}>{typeAction(rec.property_type)}</p>

                          {/* Bar */}
                          <div className="h-1 bg-slate-100 rounded-full overflow-hidden mb-1.5">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${t.bar}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>

                          {/* Stats */}
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] text-slate-400">
                              {rec.tx_count} صفقة · {rec.market_share}% من السوق
                            </span>
                            {rec.has_roi && rec.profit !== null ? (
                              <span className={`text-[11px] font-black ${rec.profit > 0 ? "text-emerald-600" : "text-red-500"}`}>
                                {rec.profit > 0 ? "+" : ""}{PriceService.formatPrice(rec.profit)} ربح
                              </span>
                            ) : (
                              <span className="text-[11px] font-black text-slate-600">
                                {PriceService.formatPrice(rec.total_value)} ر.س
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {/* Footer */}
          <p className="text-[12px] text-slate-400 text-center border-t border-slate-100 pt-3">
            التوصيات مبنية على {result.recommendations.reduce((a, b) => a + b.tx_count, 0)} صفقة عقارية فعلية في حي {neighborhood}
          </p>
        </div>
      )}
    </div>
  );
}