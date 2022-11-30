ALTER TABLE
    `client`
ADD
    COLUMN `residential` tinyint(1) NOT NULL DEFAULT 0;

DROP TABLE IF EXISTS `vatRules`;
