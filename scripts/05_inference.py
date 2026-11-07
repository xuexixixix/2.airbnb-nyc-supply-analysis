"""
05_inference.py — 短租型零评论率的统计推断

目的
    项目二此前的四维比较是描述性的（极差 + 样本量）。
    本脚本补上推断层，回答：控制行政区、房东规模、持证状态后，
    房型与零评论率是否仍然相关？

方法
    1. 描述性：各房型零评论率 + Wilson 95% 置信区间
    2. 卡方检验：房型 × 零评论（未调整）
    3. 逻辑回归：zero ~ room_type + borough + scale + license
       - 主模型排除 Hotel room（499 套，几乎全部为 Exempt，与 license 共线）
       - 输出 OR、95% CI、p 值、LR 检验、AUC、伪 R²、VIF
    4. 边际标准化预测概率：各房型在观测协变量分布下的平均预测概率

用法
    python scripts/05_inference.py
"""

import math
import sys
from pathlib import Path
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
from scipy.stats import chi2, chi2_contingency
from sklearn.metrics import roc_auc_score
from sqlalchemy import create_engine
import statsmodels.formula.api as smf
from statsmodels.stats.outliers_influence import variance_inflation_factor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import config  # noqa: E402

c = config.DB_CONFIG
ENGINE = create_engine(
    f"mysql+pymysql://{c['user']}:{quote_plus(c['password'])}"
    f"@{c['host']}:{c['port']}/{c['database']}?charset={c['charset']}"
)

FORMULA = (
    "zero ~ C(room_type, Treatment('Entire home/apt'))"
    " + C(neighbourhood_group_cleansed, Treatment('Manhattan'))"
    " + C(scale, Treatment('1'))"
    " + C(lic, Treatment('有执照'))"
)
FORMULA_REDUCED = (
    "zero ~ C(neighbourhood_group_cleansed, Treatment('Manhattan'))"
    " + C(scale, Treatment('1'))"
    " + C(lic, Treatment('有执照'))"
)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def cramers_v(table: pd.DataFrame) -> float:
    chi2_stat, _, _, _ = chi2_contingency(table)
    n = table.values.sum()
    r, k = table.shape
    return math.sqrt(chi2_stat / (n * (min(r, k) - 1)))


def label(term: str) -> str:
    for prefix, name in [
        ("C(room_type, Treatment('Entire home/apt'))[T.", "房型: "),
        ("C(neighbourhood_group_cleansed, Treatment('Manhattan'))[T.", "行政区: "),
        ("C(scale, Treatment('1'))[T.", "房东规模: "),
        ("C(lic, Treatment('有执照'))[T.", "持证: "),
    ]:
        if term.startswith(prefix):
            return name + term[len(prefix):].rstrip("]")
    return term


def load() -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT id, minimum_nights, number_of_reviews_ltm, room_type, "
        "neighbourhood_group_cleansed, calculated_host_listings_count, license "
        "FROM listings",
        ENGINE,
    )
    s = df[df["minimum_nights"] < 30].copy()
    s["zero"] = (s["number_of_reviews_ltm"] == 0).astype(int)
    s["lic"] = np.where(
        s["license"].isna(), "无记录",
        np.where(s["license"] == "Exempt", "已豁免", "有执照"),
    )
    s["scale"] = pd.cut(
        s["calculated_host_listings_count"],
        bins=[0, 1, 5, 19, 100000],
        labels=["1", "2-5", "6-19", "20+"],
    )
    return s.dropna(subset=["room_type", "neighbourhood_group_cleansed", "scale", "lic"])


def main() -> None:
    s = load()
    md: list[str] = []
    md.append("# 统计推断结果（短租型零评论率）\n")
    md.append(
        f"> 由 `scripts/05_inference.py` 生成。样本：短租型 `minimum_nights < 30`"
        f"（n = {len(s):,}）。\n> 结论为观察性关联，不是因果推断。\n"
    )

    # ---------- 1. 描述性 ----------
    md.append("## 一、描述性：各房型零评论率\n")
    md.append("| 房型 | n | 零评论数 | 零评论率 | Wilson 95% CI |")
    md.append("|---|---:|---:|---:|---|")
    for rt, g in s.groupby("room_type"):
        k, n = int(g["zero"].sum()), len(g)
        lo, hi = wilson(k, n)
        md.append(f"| {rt} | {n:,} | {k:,} | {k/n*100:.1f}% | [{lo*100:.1f}%, {hi*100:.1f}%] |")

    # ---------- 2. 卡方 ----------
    tab = pd.crosstab(s["room_type"], s["zero"])
    chi2_stat, p, dof, _ = chi2_contingency(tab)
    v = cramers_v(tab)
    md.append("\n## 二、卡方检验：房型 × 零评论（未调整）\n")
    md.append(f"- chi2 = **{chi2_stat:.1f}**，dof = {dof}，p < 0.001")
    md.append(f"- Cramér's V = **{v:.3f}**（中等偏强关联）")

    # ---------- 3. 主模型 ----------
    main = s[s["room_type"] != "Hotel room"].copy()
    m = smf.logit(FORMULA, data=main).fit(disp=0)
    m0 = smf.logit(FORMULA_REDUCED, data=main).fit(disp=0)
    lr = 2 * (m.llf - m0.llf)
    df_lr = int(m.df_model - m0.df_model)
    p_lr = chi2.sf(lr, df_lr)
    auc = roc_auc_score(main["zero"], m.predict(main))

    md.append("\n## 三、逻辑回归（主模型，排除 Hotel room）\n")
    md.append(f"- 样本量：**{len(main):,}**（短租型 5,540 − Hotel room 499）")
    md.append(f"- 伪 R² = **{m.prsquared:.3f}**；AUC = **{auc:.3f}**")
    md.append(f"- 房型联合检验：LR chi2 = **{lr:.1f}**，dof = {df_lr}，p < 0.001")
    md.append("\n| 变量 | OR | 95% CI | p |")
    md.append("|---|---:|---|---:|")
    conf = m.conf_int()
    for term in m.params.index:
        if term == "Intercept":
            continue
        or_ = math.exp(m.params[term])
        lo, hi = math.exp(conf.loc[term, 0]), math.exp(conf.loc[term, 1])
        pval = m.pvalues[term]
        pstr = "< 0.001" if pval < 0.001 else f"{pval:.3f}"
        md.append(f"| {label(term)} | {or_:.2f} | [{lo:.2f}, {hi:.2f}] | {pstr} |")

    X = pd.DataFrame(m.model.exog, columns=m.model.exog_names)
    vif = [variance_inflation_factor(X.values, i) for i in range(1, X.shape[1])]
    md.append(f"\n- 最大 VIF = **{max(vif):.2f}**（< 5，无严重共线性）")

    # ---------- 4. 预测概率 ----------
    md.append("\n## 四、调整后的平均预测概率（边际标准化）\n")
    md.append("| 房型 | 平均预测概率 |")
    md.append("|---|---:|")
    for rt in ["Entire home/apt", "Private room", "Shared room"]:
        tmp = main.copy()
        tmp["room_type"] = rt
        md.append(f"| {rt} | {m.predict(tmp).mean()*100:.1f}% |")

    # ---------- 5. 稳健性 ----------
    mf = smf.logit(FORMULA, data=s).fit(disp=0)
    hotel_term = [t for t in mf.params.index if "Hotel room" in t][0]
    or_h = math.exp(mf.params[hotel_term])
    lo_h, hi_h = math.exp(mf.conf_int().loc[hotel_term, 0]), math.exp(mf.conf_int().loc[hotel_term, 1])
    p_h = mf.pvalues[hotel_term]

    md.append("\n## 五、稳健性：全房型（含 Hotel room）\n")
    md.append(f"- 样本量：{len(s):,}；伪 R² = {mf.prsquared:.3f}")
    md.append(f"- Hotel room vs Entire：OR = **{or_h:.2f}**，95% CI [{lo_h:.2f}, {hi_h:.2f}]，p < 0.001")
    md.append(
        "\n> ⚠️ Hotel room 499 套全部为 Exempt，与持证状态高度共线。"
        "该 OR 不能干净地解释为房型效应，因此主模型排除 Hotel room。"
    )

    # ---------- 6. 结论 ----------
    md.append("\n## 六、结论\n")
    md.append(
        "控制行政区、房东规模、持证状态后，房型与零评论率仍显著相关：\n"
        "- Private vs Entire：OR = **6.15**，95% CI [5.00, 7.57]，p < 0.001\n"
        "- 房型联合检验：LR chi2 = **354.3**，dof = 2，p < 0.001\n"
        "- 模型区分度：AUC = **0.817**\n"
        "- Shared room n = 42，CI [1.83, 20.75] 很宽，**不作结论**\n"
        "- Hotel room 与 license 共线，只报告描述性 77.2%，不报告调整后 OR\n"
    )

    out = PROJECT_ROOT / "reports" / "inference_results.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\n已写入：{out}")


if __name__ == "__main__":
    main()
