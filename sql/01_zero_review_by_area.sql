-- 按行政区统计「零需求房源」的比例
--
-- 业务问题
--     44% 的房源整年没有评论。这是地理造成的吗？
--     是不是某些行政区的问题特别严重？
--
-- 为什么用比例而不是绝对数
--     曼哈顿的零评论房源有 9,103 套，Staten Island 只有 203 套，差 45 倍。
--     但曼哈顿的房源总数本身就是岛上的 41 倍 —— 用绝对数比会得出错误结论。
--     必须换算成比例：率 = 部分 ÷ 全体。
--
-- 结论
--     五个区的零评论率集中在 61%~66%，极差仅 5.3 个百分点。
--     → 零需求房源不是地理现象，在全城均匀分布。
--     → 排除「地理」这个假设，转向房型 / 房东类型 / 价格 / 持证情况。

SELECT
    neighbourhood_group_cleansed                                   AS 行政区,

    COUNT(*)                                                       AS 总房源数,

    -- COUNT 只能数全部行；要数「满足条件的行」，用 SUM + CASE
    -- CASE WHEN 条件 THEN 1 ELSE 0 END —— 满足记 1，不满足记 0
    -- 再 SUM 加起来，就等于满足条件的行数
    SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END)     AS 零评论房源数,

    -- 先乘 100.0（带小数点的 100）再除，避免 MySQL 做整数除法把结果变成 0
    ROUND(
        100.0 * SUM(CASE WHEN number_of_reviews_ltm = 0 THEN 1 ELSE 0 END)
        / COUNT(*),
        1
    )                                                              AS 零评论率百分比

FROM listings
GROUP BY neighbourhood_group_cleansed
ORDER BY 零评论率百分比 DESC;
