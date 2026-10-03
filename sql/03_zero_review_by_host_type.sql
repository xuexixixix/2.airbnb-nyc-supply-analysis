-- 按房东规模统计「零需求房源」的比例
--
-- 业务问题
--     地理维度排除了（五个区都是 61%~66%）。
--     房型维度也排除了（整租 65.7% vs 独立间 64.4%）。
--     那是不是房东类型造成的？
--
-- 假设
--     个体房东（只有 1 套房）—— 可能是自住顺便出租，挂着试试，没人打理
--     职业房东（管几十套）  —— 靠这个吃饭，会更积极运营、更在意评价
--     如果假设成立，个体房东的零评论率应该明显高于职业房东
--
-- 字段说明
--     用 calculated_host_listings_count（房东名下房源数）
--     不用 host_listings_count / host_total_listings_count —— 这两个在本快照中全空
--
-- 结论
--     这是三个维度中【唯一】出现显著差异的（地理和房型都是均匀的）。
--
--     房东类型           总房源     零评论率
--     1. 个体房东（1套）   13,274     71.9%   ← 高
--     2. 小规模（2-5套）    6,904     54.4%   ← 低
--     3. 中规模（6-19套）   3,559     53.6%   ← 低
--     4. 职业房东（20套以上） 6,522     70.2%   ← 高
--
--     呈 U 型：两头高、中间低，极差 18.3 个百分点。
--
--     ⚠️ 但「职业房东」这一组必须打折看待：
--        6,522 套房源只来自 93 个房东（人均 70 套）。
--        这不是"一类人的规律"，而是 93 个个体的行为，样本高度集中，
--        不能直接外推为"职业房东都这样"。
--        详见 04_mega_hosts_detail.sql
--
--     → 规模化本身不是问题，经营意愿才是。

SELECT
    CASE
        WHEN calculated_host_listings_count = 1   THEN '1. 个体房东（1套）'
        WHEN calculated_host_listings_count <= 5  THEN '2. 小规模（2-5套）'
        WHEN calculated_host_listings_count <= 19 THEN '3. 中规模（6-19套）'
        ELSE                                           '4. 职业房东（20套以上）'
    END                                                            AS 房东类型,

    COUNT(*)                                                       AS 总房源数,

    SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END)     AS 零评论房源数,

    ROUND(
        100.0 * SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END)
        / COUNT(*),
        1
    )                                                              AS 零评论率百分比

FROM listings
GROUP BY 房东类型
ORDER BY 房东类型;
