-- 有效短租供给漏斗
--
-- 为什么要有这个文件
--     5,540 是「短租型挂牌」，不等于「当前可订、且有过需求」的有效供给。
--     本文件把 5,540 再拆一层，回答：真正可订且有需求的短租到底有多少？
--
-- 口径
--     短租型       minimum_nights < 30
--     可订         availability_365 > 0
--     有需求       number_of_reviews_ltm > 0
--     有效短租供给 短租型 + 可订 + 有需求
--
-- 预期结果（2026-06 快照）
--     全部挂牌 30,259；短租型 5,540（18.3%）；可订短租 5,118（16.9%）；
--     有需求短租 4,184（13.8%）；有效短租供给 4,050（13.4%）；
--     有收入短租 4,009（13.2%，占短租 72.4%）。
--
-- 注意
--     这是对 5,540 的再拆解，不是修正；5,540 / 18.3% / 72.4% 仍然成立。

-- ============================================================
--  查询 1：漏斗总数
-- ============================================================
SELECT
    COUNT(*) AS 全部挂牌,
    SUM(CASE WHEN minimum_nights < 30 THEN 1 ELSE 0 END) AS 短租型挂牌,
    SUM(CASE WHEN minimum_nights < 30 AND availability_365 > 0 THEN 1 ELSE 0 END) AS 可订短租,
    SUM(CASE WHEN minimum_nights < 30 AND number_of_reviews_ltm > 0 THEN 1 ELSE 0 END) AS 有需求短租,
    SUM(CASE WHEN minimum_nights < 30 AND availability_365 > 0
                  AND number_of_reviews_ltm > 0 THEN 1 ELSE 0 END) AS 有效短租供给,
    SUM(CASE WHEN minimum_nights < 30 AND estimated_revenue_l365d > 0 THEN 1 ELSE 0 END) AS 有收入短租
FROM listings;

-- ============================================================
--  查询 2：漏斗占比（分母统一为全部挂牌 30,259）
-- ============================================================
SELECT
    ROUND(100.0 * SUM(CASE WHEN minimum_nights < 30 THEN 1 ELSE 0 END) / COUNT(*), 2) AS 短租型占比,
    ROUND(100.0 * SUM(CASE WHEN minimum_nights < 30 AND availability_365 > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS 可订短租占比,
    ROUND(100.0 * SUM(CASE WHEN minimum_nights < 30 AND number_of_reviews_ltm > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS 有需求短租占比,
    ROUND(100.0 * SUM(CASE WHEN minimum_nights < 30 AND availability_365 > 0
                              AND number_of_reviews_ltm > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS 有效短租供给占比,
    ROUND(100.0 * SUM(CASE WHEN minimum_nights < 30 AND estimated_revenue_l365d > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS 有收入短租占比
FROM listings;

-- ============================================================
--  查询 3：5,540 套短租的互斥拆解（五组相加 = 5,540）
-- ============================================================
SELECT
    CASE
        WHEN availability_365 = 0 AND number_of_reviews_ltm = 0
            THEN '1. 不可订 + 零评论'
        WHEN availability_365 = 0 AND number_of_reviews_ltm > 0
            THEN '2. 不可订 + 有评论'
        WHEN availability_365 > 0 AND number_of_reviews_ltm = 0
            THEN '3. 可订 + 零评论'
        WHEN availability_365 > 0 AND number_of_reviews_ltm > 0
             AND estimated_revenue_l365d > 0
            THEN '4. 可订 + 有评论 + 有收入'
        WHEN availability_365 > 0 AND number_of_reviews_ltm > 0
             AND (estimated_revenue_l365d IS NULL OR estimated_revenue_l365d = 0)
            THEN '5. 可订 + 有评论 + 无收入'
    END AS 分组,
    COUNT(*) AS 房源数
FROM listings
WHERE minimum_nights < 30
GROUP BY 分组
ORDER BY 分组;

-- ============================================================
--  查询 4（可选）：按房型看有效短租供给
-- ============================================================
SELECT
    room_type AS 房型,
    COUNT(*) AS 短租型挂牌,
    SUM(CASE WHEN availability_365 > 0 AND number_of_reviews_ltm > 0 THEN 1 ELSE 0 END) AS 有效短租供给,
    ROUND(100.0 * SUM(CASE WHEN availability_365 > 0 AND number_of_reviews_ltm > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS 有效率
FROM listings
WHERE minimum_nights < 30
GROUP BY room_type
ORDER BY 短租型挂牌 DESC;
