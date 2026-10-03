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
--     房型也不是原因。
--     占全部房源 97.6% 的两大类几乎无差异：
--         整租 Entire home/apt  65.7%（16,808 套）
--         独立间 Private room   64.4%（12,713 套）
--     仅差 1.3 个百分点。
--
--     Hotel room（77.9%）和 Shared room（67.9%）看起来更高，
--     但样本仅 520 套和 218 套，差异可能来自随机波动，不足以支撑结论。
--
--     → 与地理维度一样，零需求房源在房型维度上也是均匀分布的。
--     → 说明这不是"某一类房源"的问题，而是普遍现象。

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
