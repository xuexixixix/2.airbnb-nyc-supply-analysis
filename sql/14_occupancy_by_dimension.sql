-- 出租率辅助分析（仅用于同类型内部相对比较，不报绝对值）
--
-- 口径
--     出租率 = estimated_occupancy_l365d / 365
--     该字段是 Inside Airbnb 用评论数反推的估算值：
--       1. 零值与 number_of_reviews_ltm = 0 100% 重合
--       2. 上限 70%（实测最大 69.86%）
--       3. 对低销量房源存在低估
--     因此本查询只做「短租/长租 × 房型」的相对比较，不作为主指标。
--
-- 预期结果（2026-06 快照）
--     短租整租 49.7%（仅 >0 为 54.9%）；短租独立间 38.1%（50.4%）；
--     长租整租 10.0%（35.7%）；长租独立间 7.3%（33.7%）。
--     短租 Hotel room 4.1%（17.9%）——与 77.2% 零评论一致，基本未运营。

-- ============================================================
--  查询 1：短租/长租 × 房型的出租率
-- ============================================================
SELECT
    CASE
        WHEN minimum_nights >= 30 THEN '长租型'
        WHEN minimum_nights < 30 THEN '短租型'
        ELSE '缺失'
    END AS 类型,
    room_type AS 房型,
    COUNT(*) AS 房源数,
    ROUND(AVG(estimated_occupancy_l365d / 365) * 100, 1) AS 平均出租率_含零,
    ROUND(AVG(CASE WHEN estimated_occupancy_l365d > 0
                   THEN estimated_occupancy_l365d / 365 END) * 100, 1) AS 平均出租率_仅大于零,
    SUM(CASE WHEN estimated_occupancy_l365d = 0 THEN 1 ELSE 0 END) AS 零间夜房源数
FROM listings
GROUP BY 类型, 房型
ORDER BY 类型, 房源数 DESC;

-- ============================================================
--  查询 2：上限校验（应等于 69.86，约 70%）
-- ============================================================
SELECT ROUND(MAX(estimated_occupancy_l365d) / 365 * 100, 2) AS 最大出租率
FROM listings;
