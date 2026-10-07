-- 按房型统计「零需求房源」的比例
--
-- 业务问题
--     44% 的房源整年没有评论。
--     地理维度已经排除了（五个行政区都是 61%~66%，没有差异）。
--     那是不是房型造成的？整租 vs 独立间的经营模式差很多。
--
-- 背景
--     整租（Entire home/apt）—— 房东把整套房出租，通常是投资行为
--     独立间（Private room）—— 房东分租一间，通常自己也住里面
--     合住（Shared room）  —— 合租床位的低价选择
--     酒店房（Hotel room） —— 酒店在平台上挂牌
--
-- 结论
--     占全部房源 97.6% 的两大类几乎无差异：
--         整租 Entire home/apt  65.7%（16,808 套）
--         独立间 Private room   64.4%（12,713 套）
--     仅差 1.3 个百分点。
--     → 当时判断：房型也不是原因，零需求在房型维度上也是均匀的。
--
-- 🚨 本结论已被推翻（2026-10-05）
--     上句的「房型无差异」同样是在【全部房源】上算的，混入了 81.7% 的长租型。
--     仅统计短租型（minimum_nights < 30，n=5,540）时：
--
--         房型              房源数    零评论率
--         Entire home/apt    1,685     9.4%
--         Private room       3,314    24.4%
--         Hotel room           499    77.2%
--         Shared room           42     7.1%
--         ─────────────────────────────────
--         极差                        70.0 个百分点
--
--     房型其实是四个维度中【差异最大】的一个，不是"无差异"。
--
--     ⚠️ 样本量警示：Shared room（42 套）、Hotel room（499 套）偏小。
--        排除 Shared room 后极差为 67.8 pp —— 结论不变，但须说明。
--
--     → 修正见 sql/12_dimension_comparison.sql
--     → 保留本文件为留痕

SELECT
    room_type                                                      AS 房型,

    COUNT(*)                                                       AS 总房源数,

    SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END)     AS 零评论房源数,

    ROUND(
        100.0 * SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END)
        / COUNT(*),
        1
    )                                                              AS 零评论率百分比

FROM listings
GROUP BY room_type
ORDER BY 零评论率百分比 DESC;
