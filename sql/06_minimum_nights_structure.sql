-- 发现平台底层结构：81.7% 的「房源」其实是长租型
--
-- 业务问题（起因）
--     查 Exempt（豁免）含义时，从 Airbnb 帮助中心与纽约 Local Law 18 查到：
--     连续租 30 天以上可豁免登记，Class B 多户住宅也可豁免。
--     于是假设：Exempt 组里应该有很多「最短入住 30 天」的房源。
--
--     验证结果 —— 完全相反：长租型集中在「无记录」组，不在 Exempt 组。
--
-- 关键观察
--     「无记录」组的 minimum_nights 分布高度集中在 30 这个数字上：
--         恰好 30 天   23,698 套   94.9%   ← 压倒性
--         1 天            358 套    1.4%
--         31 天           327 套    1.3%
--         90 天           143 套    0.6%
--
--     这不是自然分布 —— 是刻意卡在法规临界值上。
--     纽约法规管的是「30 天以下」的短租，设成 30 天即跳出适用范围。
--
-- 追问：这些房源真的在做生意吗？
--     无记录 + 最短 30 天的 23,698 套中：
--         有成交    5,551 套（23.4%）  平均年收入 $20,117，平均入住 126 间夜
--         零成交   18,147 套（76.6%）  ← 完全没有交易
--     → 不是「真长租所以没短租评论」，而是确实没有产生收入。
--
-- 结论（本项目最重要的结构发现）
--     把全部房源按最短入住天数切开：
--         长租型（≥30 天）   24,717 套（81.7%）  零评论率 74.5%   有成交仅 23.2%
--         短租型（< 30 天）    5,542 套（18.3%）  零评论率 24.5%   有成交 72.4%
--
--     ⚠️ 这推翻了 00_supply_overview.sql 里「44% 开门但没客」的表述口径：
--        那个数字把两种商品混在一起算了。真正的短租经营状况良好。

SELECT
    -- ---------- 第一部分：长短租的结构差异 ----------
    CASE WHEN minimum_nights >= 30 THEN '长租型（最短30天+）'
         ELSE                            '短租型（最短30天以下）' END AS 类型,

    COUNT(*)                                                       AS 房源数,

    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM listings), 1)   AS 占比,

    SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END)     AS 零评论房源数,

    ROUND(
        100.0 * SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END)
        / COUNT(*), 1
    )                                                              AS 零评论率,

    SUM(CASE WHEN estimated_revenue_l365d > 0 THEN 1 ELSE 0 END)   AS 有成交房源数,

    ROUND(
        100.0 * SUM(CASE WHEN estimated_revenue_l365d > 0 THEN 1 ELSE 0 END)
        / COUNT(*), 1
    )                                                              AS 有成交占比

FROM listings
GROUP BY 类型
ORDER BY 房源数 DESC;

-- ============================================================
--  配套查询（需要时单独执行）
-- ============================================================
--
-- 【查 30 天临界值的集中度】
-- SELECT minimum_nights AS 最短入住, COUNT(*) AS 房源数
-- FROM listings WHERE license IS NULL
-- GROUP BY minimum_nights ORDER BY 房源数 DESC LIMIT 10;
--
-- 【查「无记录 + 最短30天」这 23,698 套到底有没有生意】
-- SELECT
--     SUM(CASE WHEN estimated_revenue_l365d > 0 THEN 1 ELSE 0 END) AS 有收入,
--     COUNT(*) AS 总数,
--     ROUND(AVG(CASE WHEN estimated_revenue_l365d > 0
--                    THEN estimated_revenue_l365d END), 0) AS 有收入者平均收入
-- FROM listings
-- WHERE license IS NULL AND minimum_nights = 30;
