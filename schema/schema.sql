-- MySQL dump 10.13  Distrib 8.0.28, for Linux (x86_64)
--
-- Host: 127.0.0.1    Database: invoices
-- ------------------------------------------------------
-- Server version	8.0.28-0ubuntu0.20.04.3

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
  `name` varchar(100) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `city` varchar(45) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `postalCode` varchar(10) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `email` varchar(100) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `telephone` varchar(30) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  `address` varchar(45) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  PRIMARY KEY (`ID`),
  UNIQUE KEY `ID_UNIQUE` (`ID`),
  KEY `clientnumber` (`clientNumber`)
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `client`
--

LOCK TABLES `client` WRITE;
/*!40000 ALTER TABLE `client` DISABLE KEYS */;
INSERT INTO `client` VALUES (19,1,'test','test','test','test','test','test'),(20,2,'test','test','test','test','test','test'),(21,3,'test','test','test','test','test','test'),(22,1,'test123','test','test','test','test','test'),(23,1,'peer','test','test','test','test','test');
/*!40000 ALTER TABLE `client` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `invoice`
--

DROP TABLE IF EXISTS `invoice`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `invoice` (
  `ID` int unsigned NOT NULL AUTO_INCREMENT,
  `sequenceNumber` char(8) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `dateCreated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `dateDue` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
  `title` varchar(80) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `client` mediumint unsigned NOT NULL,
  `status` enum('new','sent','paid') CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `reservation` tinyint NOT NULL DEFAULT '0',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `sequenceNumber` (`sequenceNumber`),
  KEY `status` (`status`),
  KEY `fk_invoice_1_idx` (`client`),
  CONSTRAINT `fk_invoice_1` FOREIGN KEY (`client`) REFERENCES `client` (`ID`)
) ENGINE=InnoDB AUTO_INCREMENT=73 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `invoice`
--

LOCK TABLES `invoice` WRITE;
/*!40000 ALTER TABLE `invoice` DISABLE KEYS */;
INSERT INTO `invoice` VALUES (70,'2022-001','2022-05-03 12:29:46','2022-05-16 22:00:00','Een mooie invoice','Invoice omschrijving',19,'new',0),(71,'2022-002','2022-05-03 12:30:24','2022-05-16 22:00:00','Een mooie invoice','Invoice omschrijving',19,'new',0),(72,'2022-003','2022-05-03 12:49:22','2022-05-16 22:00:00','Een mooie invoice','Invoice omschrijving',19,'new',0);
/*!40000 ALTER TABLE `invoice` ENABLE KEYS */;
UNLOCK TABLES;

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
  `name` varchar(45) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
  `quantity` mediumint NOT NULL,
  PRIMARY KEY (`ID`),
  KEY `invoice` (`invoice`),
  CONSTRAINT `product_ibfk_1` FOREIGN KEY (`invoice`) REFERENCES `invoice` (`ID`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=32 DEFAULT CHARSET=utf8mb3 COLLATE=utf8_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `invoiceProduct`
--

LOCK TABLES `invoiceProduct` WRITE;
/*!40000 ALTER TABLE `invoiceProduct` DISABLE KEYS */;
INSERT INTO `invoiceProduct` VALUES (27,70,100.00,21,'product_name',7),(28,71,100.00,21,'product_name',7),(29,72,100.00,21,'product_name',7),(30,72,50.00,21,'Something',3),(31,72,12.00,21,'Apple',1000);
/*!40000 ALTER TABLE `invoiceProduct` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping events for database 'invoices'
--

--
-- Dumping routines for database 'invoices'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2022-05-03 14:52:00
