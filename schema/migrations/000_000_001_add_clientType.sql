ALTER TABLE
    invoices.client
ADD
    COLUMN `client_type` ENUM("Individual", "Company") DEFAULT "Individual" NOT NULL,
ADD
    COLUMN `vat_number` VARCHAR(25);
