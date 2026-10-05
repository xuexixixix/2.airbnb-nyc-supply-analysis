-- 每个房源的最后一条评论日期
--
-- 业务问题
--     那些"零需求"的房源，是一直没生意，还是曾经有过、后来死掉了？

SELECT
    l.id,
    l.room_type,
    MAX(r.date) AS 最后评论日期
FROM listings l
LEFT JOIN reviews r ON l.id = r.listing_id
GROUP BY l.id;          -- ← 分号！每条语句末尾都要有


SELECT
    COUNT(*)                                                    AS 总房源数,
    SUM(CASE WHEN 最后评论日期 IS NULL THEN 1 ELSE 0 END)        AS 从未有评论的房源数,
    ROUND(100.0 * SUM(CASE WHEN 最后评论日期 IS NULL THEN 1 ELSE 0 END)
          / COUNT(*), 1)                                        AS 占比
FROM (
    SELECT l.id, MAX(r.date) AS 最后评论日期
    FROM listings l
    LEFT JOIN reviews r ON l.id = r.listing_id
    GROUP BY l.id
) t;

