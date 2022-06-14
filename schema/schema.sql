-- MySQL dump 10.13  Distrib 8.0.29, for Linux (x86_64)
--
-- Host: localhost    Database: invoices
-- ------------------------------------------------------
-- Server version	8.0.29-0ubuntu0.20.04.3

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `client`
--

DROP TABLE IF EXISTS `client`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `client` (
  `ID` mediumint unsigned NOT NULL AUTO_INCREMENT,
  `clientNumber` mediumint unsigned NOT NULL,
  `name` varchar(100) CHARACTER SET utf8mb3 COLLATE utf8_general_ci NOT NULL,
  `city` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8_general_ci NOT NULL,
  `postalCode` varchar(10) CHARACTER SET utf8mb3 COLLATE utf8_general_ci NOT NULL,
  `email` varchar(100) CHARACTER SET utf8mb3 COLLATE utf8_general_ci NOT NULL,
  `telephone` varchar(30) CHARACTER SET utf8mb3 COLLATE utf8_general_ci NOT NULL,
  `address` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8_general_ci NOT NULL,
  PRIMARY KEY (`ID`),
  UNIQUE KEY `ID_UNIQUE` (`ID`),
  KEY `clientnumber` (`clientNumber`)
) ENGINE=InnoDB AUTO_INCREMENT=41 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `companydetails`
--

DROP TABLE IF EXISTS `companydetails`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `companydetails` (
  `ID` tinyint unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `telephone` varchar(30) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `address` varchar(100) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `postalCode` varchar(10) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `city` varchar(200) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `country` varchar(50) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `vat` varchar(20) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `kvk` varchar(20) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `bankAccount` varchar(25) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `bank` varchar(20) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `bankCity` varchar(200) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `invoiceprefix` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb3 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `invoice`
--

DROP TABLE IF EXISTS `invoice`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoice` (
  `ID` int unsigned NOT NULL AUTO_INCREMENT,
  `sequenceNumber` char(11) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `companydetails` tinyint unsigned NOT NULL,
  `dateCreated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `dateDue` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
  `title` varchar(80) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `client` mediumint unsigned NOT NULL,
  `status` enum('new','sent','paid','reservation','canceled') CHARACTER SET utf8mb3 COLLATE utf8_general_ci NOT NULL DEFAULT 'new',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `sequenceNumber` (`sequenceNumber`),
  KEY `status` (`status`),
  KEY `fk_invoice_1_idx` (`client`),
  KEY `fk_invoice_2_idx` (`companydetails`),
  CONSTRAINT `fk_invoice_1` FOREIGN KEY (`client`) REFERENCES `client` (`ID`),
  CONSTRAINT `fk_invoice_2` FOREIGN KEY (`companydetails`) REFERENCES `companydetails` (`ID`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=431 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`invoices`@`localhost`*/ /*!50003 TRIGGER `invoice_BEFORE_INSERT` BEFORE INSERT ON `invoice` FOR EACH ROW BEGIN
	IF new.status = 'reservation' AND SUBSTRING(new.sequenceNumber, 1, 2) != 'PF'
    THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A pro forma invoice sequencenumber must start with a PF prefix.';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;

--
-- Table structure for table `invoicePayment`
--

DROP TABLE IF EXISTS `invoicePayment`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoicePayment` (
  `ID` mediumint NOT NULL AUTO_INCREMENT,
  `invoice` int NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `platform` varchar(45) DEFAULT NULL,
  `creationTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID`),
  KEY `fk_invoicePayment_1_idx` (`invoice`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`invoices`@`localhost`*/ /*!50003 TRIGGER `invoicePayment_AFTER_INSERT` AFTER INSERT ON `invoicePayment` FOR EACH ROW BEGIN
    CALL CalculateInvoiceTotalPrice(new.invoice, @total_due);
    CALL CalculateInvoicePaymentTotalPrice(new.invoice, @total_paid);
	IF ((select @total_paid) >= (select @total_due))
    THEN UPDATE invoice SET invoice.status = 'paid' WHERE invoice.ID = new.invoice AND invoice.status != 'canceled';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;

--
-- Table structure for table `invoiceProduct`
--

DROP TABLE IF EXISTS `invoiceProduct`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoiceProduct` (
  `ID` int unsigned NOT NULL AUTO_INCREMENT,
  `invoice` int unsigned NOT NULL,
  `price` decimal(8,2) NOT NULL,
  `vat_percentage` smallint NOT NULL,
  `name` varchar(45) CHARACTER SET utf8mb3 COLLATE utf8_unicode_ci NOT NULL,
  `quantity` mediumint NOT NULL,
  `sku` varchar(45) COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`ID`),
  KEY `invoice` (`invoice`),
  CONSTRAINT `product_ibfk_1` FOREIGN KEY (`invoice`) REFERENCES `invoice` (`ID`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb3 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `mollieTransaction`
--

DROP TABLE IF EXISTS `mollieTransaction`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mollieTransaction` (
  `ID` mediumint NOT NULL AUTO_INCREMENT,
  `invoice` int unsigned NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `status` enum('paid','expired','failed','open','pending','refunded','chargeback','settled','authorized','canceled') NOT NULL,
  `description` text,
  `creationTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updateTime` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID`),
  KEY `fk_mollieTransaction_1_idx` (`invoice`),
  CONSTRAINT `fk_mollieTransaction_1` FOREIGN KEY (`invoice`) REFERENCES `invoice` (`ID`) ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `paymentPlatform`
--

DROP TABLE IF EXISTS `paymentPlatform`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `paymentPlatform` (
  `ID` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(45) NOT NULL,
  PRIMARY KEY (`ID`),
  UNIQUE KEY `name_UNIQUE` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `proFormaSequenceTable`
--

DROP TABLE IF EXISTS `proFormaSequenceTable`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `proFormaSequenceTable` (
  `ID` smallint NOT NULL AUTO_INCREMENT,
  `sequenceNumber` varchar(11) NOT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user`
--

DROP TABLE IF EXISTS `user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user` (
  `ID` mediumint unsigned NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL,
  `password` char(100) NOT NULL,
  `active` enum('true','false') NOT NULL DEFAULT 'true',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `email` (`email`),
  KEY `login` (`email`,`password`,`active`),
  KEY `active` (`active`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping events for database 'invoices'
--

--
-- Dumping routines for database 'invoices'
--
/*!50003 DROP PROCEDURE IF EXISTS `CalculateInvoicePaymentTotalPrice` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`invoices`@`localhost` PROCEDURE `CalculateInvoicePaymentTotalPrice`(IN invoice int, OUT total_paid DECIMAL(10,2))
BEGIN
	SET total_paid = (SELECT sum(amount) total_paid
	FROM invoicePayment
	WHERE invoicePayment.invoice = invoice);
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `CalculateInvoiceTotalPrice` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`invoices`@`localhost` PROCEDURE `CalculateInvoiceTotalPrice`(IN invoice int, OUT total_due DECIMAL(10, 2))
BEGIN
	SET total_due = (SELECT ROUND(SUM(p.price * p.quantity * (1+p.vat_percentage/100)), 2) as totaal
	FROM invoice AS inv
	LEFT JOIN invoiceProduct as p ON p.invoice = inv.ID
	WHERE inv.ID = invoice);
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2022-05-24 12:48:04
