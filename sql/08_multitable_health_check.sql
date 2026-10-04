-- 多表体检：做 Join 之前必须先做的完整性检查
--
-- 业务问题
--     calendar（1115 万行）和 reviews（99 万行）刚导入 MySQL。
--     在把它们 Join 到 listings 之前，必须先确认：
--     这两张表干净吗？Join 之后会不会悄悄丢数据？
--
-- 为什么这步不能省
--     单表分析时，脏数据只会影响那一张表。
--     但 Join 时，外键对不上的行会【静默消失】—— 数据少了你都不知道。
--
-- 检查结果
--     ✅ 缺失值    无
--     ✅ 重复行    无
--     ⚠️ 孤儿记录  calendar 0.97%、reviews 0.97%（见下）
--     ✅ 日期类型  已是 DATE，无需转换
--
--     【阶段 1】日期范围
--         listings.last_scraped : 2026-06-14 ~ 2026-06-23   ← 跨了 10 天
--         calendar.date         : 2026-06-14 ~ 2027-06-22
--         reviews.date          : 2009-05-25 ~ 2026-06-22
--
--         ⚠️ 重要发现：所谓「2026-06-14 快照」其实不是某个时刻，
--            而是平台花 10 天分批抓下来的。这解释了两件事：
--              ① 评论日期"超过"快照日期 —— 6/22 抓的那批，评论自然记到 6/22
--              ② 孤儿记录的来源 —— 抓取期间有房源被下架
--
--     【阶段 2】孤儿记录（listing_id 在子表有、在 listings 没有）
--         calendar   296 个 listing_id / 108,040 行 / 0.97%
--         reviews    239 个 listing_id /   9,618 行 / 0.97%
--
--         两张表比例都是 0.97% → 系统性机制，不是随机丢失
--
--     【结论：不洗】
--         孤儿记录反映的是真实现象（房源抓取期间下架），洗掉等于掩盖事实。
--         正确做法是 Join 时用 INNER JOIN 让它自然过滤，
--         并在报告中声明「Join 会导致约 1% 的数据损失」。

-- ============================================================
--  检查 1：孤儿记录数
-- ============================================================
-- 先对子表取 DISTINCT listing_id 再 Join，避免对上千万行做连接
SELECT COUNT(*) AS calendar孤儿房源数
FROM (SELECT DISTINCT listing_id FROM calendar) d
LEFT JOIN listings l ON d.listing_id = l.id
WHERE l.id IS NULL;

SELECT COUNT(*) AS reviews孤儿房源数
FROM (SELECT DISTINCT listing_id FROM reviews) d
LEFT JOIN listings l ON d.listing_id = l.id
WHERE l.id IS NULL;

-- ============================================================
--  检查 2：孤儿行数（评估 Join 会丢多少数据）
-- ============================================================
-- SELECT COUNT(*) AS 孤儿行数,
--        ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM calendar), 2) AS 占比
-- FROM calendar c LEFT JOIN listings l ON c.listing_id = l.id
-- WHERE l.id IS NULL;

-- ============================================================
--  检查 3：重复行
-- ============================================================
-- SELECT COUNT(*) AS 重复的组合数 FROM (
--     SELECT listing_id, date FROM calendar
--     GROUP BY listing_id, date HAVING COUNT(*) > 1
-- ) x;

-- ============================================================
--  检查 4：日期范围
-- ============================================================
-- SELECT MIN(last_scraped), MAX(last_scraped) FROM listings;
-- SELECT MIN(date), MAX(date) FROM calendar;
-- SELECT MIN(date), MAX(date) FROM reviews;
