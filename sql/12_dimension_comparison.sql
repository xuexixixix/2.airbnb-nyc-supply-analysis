-- 统一口径：四个维度对「零需求」的解释力对比
--
-- 为什么要有这个文件
--     前面对四个维度分别做过分析（sql/01~07），但【口径不统一】：
--         sql/01 地理      全部房源
--         sql/02 房型      全部房源
--         sql/03 房东规模  全部房源
--         sql/05 持证      全部房源（后被 sql/07 修正为短租型内部）
--     而 sql/06 发现平台上 81.7% 的房源其实是「长租型」，与短租不是同一种商品。
--     把两种商品混在一起比较，会重演「成分效应」—— 这是本项目已经踩过一次的坑。
--
-- 所以本文件统一在【短租型】（minimum_nights < 30）内部重算全部四个维度。
--
-- 🔴 本文件推翻了发现 15、16 的结论
--     sql/01 结论「地理无差异（5.3 pp）」、sql/02 结论「房型无差异（1.3 pp）」
--     都是在混算了长租型的样本上得出的。在真正的短租内部：
--         地理极差 27.0 pp（不是 5.3）
--         房型极差 70.1 pp（不是 1.3）
--
--     稀释效应验算（在各行政区分别验证，均吻合）：
--         短租型只占全部房源的 ~19%
--         短租型内部的地理差异是 27 pp
--         19% × 27 pp ≈ 5.1 pp  ← 这正是全样本里看到的 5.3 pp
--     例：曼哈顿 0.786 × 74.5% + 0.214 × 36.4% = 66.4%（实测 66.4%）
--
-- ⚠️ 样本量警示（报告与图表中必须标注）
--     过小，不足以支撑结论：Shared room 42 套、Staten Island 54 套
--     偏小，仅供参考：      Bronx 146 套、Hotel room 499 套
--     可用：                其余各组 1,557 ~ 3,314 套
--     注：房型极差 70.1 pp 有一头来自 42 套的 Shared room；
--         排除它后极差为 67.8 pp —— 结论不变，但须说明。

-- ============================================================
--  主查询：四个维度的极差对比（统一在短租型内部）
-- ============================================================
SELECT '1. 房型'       AS 维度, ROUND(MAX(p) - MIN(p), 1) AS 极差百分点 FROM (
    SELECT 100.0 * SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END) / COUNT(*) AS p
    FROM listings WHERE minimum_nights < 30 GROUP BY room_type
) x
UNION ALL
SELECT '2. 房东规模', ROUND(MAX(p) - MIN(p), 1) FROM (
    SELECT 100.0 * SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END) / COUNT(*) AS p
    FROM listings WHERE minimum_nights < 30
    GROUP BY CASE WHEN calculated_host_listings_count = 1   THEN 1
                  WHEN calculated_host_listings_count <= 5  THEN 2
                  WHEN calculated_host_listings_count <= 19 THEN 3
                  ELSE 4 END
) x
UNION ALL
SELECT '3. 持证状态', ROUND(MAX(p) - MIN(p), 1) FROM (
    SELECT 100.0 * SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END) / COUNT(*) AS p
    FROM listings WHERE minimum_nights < 30
    GROUP BY CASE WHEN license IS NULL    THEN 1
                  WHEN license = 'Exempt' THEN 2
                  ELSE 3 END
) x
UNION ALL
SELECT '4. 地理',     ROUND(MAX(p) - MIN(p), 1) FROM (
    SELECT 100.0 * SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END) / COUNT(*) AS p
    FROM listings WHERE minimum_nights < 30
    GROUP BY neighbourhood_group_cleansed
) x
ORDER BY 极差百分点 DESC;

-- ============================================================
--  配套查询 A：各维度分组的明细（含样本量，用于标注警示）
-- ============================================================
-- 【房型】
-- SELECT room_type AS 分组, COUNT(*) AS 样本数,
--        ROUND(100.0*SUM(CASE WHEN number_of_reviews_ltm=0 THEN 1 ELSE 0 END)/COUNT(*),1) AS 零评论率
-- FROM listings WHERE minimum_nights < 30 GROUP BY room_type ORDER BY 零评论率 DESC;
--
-- 【地理】
-- SELECT neighbourhood_group_cleansed AS 分组, COUNT(*) AS 样本数,
--        ROUND(100.0*SUM(CASE WHEN number_of_reviews_ltm=0 THEN 1 ELSE 0 END)/COUNT(*),1) AS 零评论率
-- FROM listings WHERE minimum_nights < 30 GROUP BY 分组 ORDER BY 零评论率 DESC;
--
-- 【房东规模】
-- SELECT CASE WHEN calculated_host_listings_count=1 THEN '1套'
--             WHEN calculated_host_listings_count<=5 THEN '2-5套'
--             WHEN calculated_host_listings_count<=19 THEN '6-19套'
--             ELSE '20套以上' END AS 分组,
--        COUNT(*) AS 样本数,
--        ROUND(100.0*SUM(CASE WHEN number_of_reviews_ltm=0 THEN 1 ELSE 0 END)/COUNT(*),1) AS 零评论率
-- FROM listings WHERE minimum_nights < 30 GROUP BY 分组 ORDER BY 零评论率 DESC;
--
-- 【持证】
-- SELECT CASE WHEN license IS NULL THEN '无记录' WHEN license='Exempt' THEN '已豁免'
--             ELSE '有执照' END AS 分组,
--        COUNT(*) AS 样本数,
--        ROUND(100.0*SUM(CASE WHEN number_of_reviews_ltm=0 THEN 1 ELSE 0 END)/COUNT(*),1) AS 零评论率
-- FROM listings WHERE minimum_nights < 30 GROUP BY 分组 ORDER BY 零评论率 DESC;

-- ============================================================
--  配套查询 B：稀释效应验证（各行政区的长租型占比）
-- ============================================================
-- SELECT neighbourhood_group_cleansed AS 行政区, COUNT(*) AS 总计,
--        ROUND(100.0*SUM(CASE WHEN minimum_nights>=30 THEN 1 ELSE 0 END)/COUNT(*),1) AS 长租占比
-- FROM listings GROUP BY 行政区 ORDER BY 长租占比 DESC;
