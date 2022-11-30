ALTER TABLE
    `client`
ADD
    COLUMN `residential` tinyint(1) NOT NULL DEFAULT 0,
ADD
    COLUMN `house_number` smallint NOT NULL,
ADD
    COLUMN `house_number_addition` varchar(15);

DROP TABLE IF EXISTS `vatRules`;
