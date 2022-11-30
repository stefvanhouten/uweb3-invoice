CREATE TABLE `vatRules` (
    `ID` tinyint NOT NULL AUTO_INCREMENT,
    `company_vat` decimal(10, 2) NOT NULL,
    `personal_vat` decimal(10, 2) NOT NULL,
    `created` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`ID`)
) ENGINE = InnoDB AUTO_INCREMENT = 2 DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
