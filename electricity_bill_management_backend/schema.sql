CREATE DATABASE IF NOT EXISTS electricity_bill_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE electricity_bill_db;

-- For a clean first-time installation, run this file in a new project database.
CREATE TABLE IF NOT EXISTS CONSUMER (
  Consumer_ID INT AUTO_INCREMENT PRIMARY KEY,
  Name VARCHAR(100) NOT NULL,
  Phone VARCHAR(20) NOT NULL,
  Email VARCHAR(120) NOT NULL,
  UNIQUE KEY uq_consumer_email (Email)
);

CREATE TABLE IF NOT EXISTS CONSUMER_ADDRESS (
  Consumer_ID INT NOT NULL,
  Consumer_Address VARCHAR(255) NOT NULL,
  PRIMARY KEY (Consumer_ID, Consumer_Address),
  CONSTRAINT fk_address_consumer FOREIGN KEY (Consumer_ID)
    REFERENCES CONSUMER(Consumer_ID) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS CONNECTION_DETAILS (
  Connection_ID INT AUTO_INCREMENT PRIMARY KEY,
  Connection_Type ENUM('Domestic','Commercial','Industrial') NOT NULL,
  Status ENUM('Active','Inactive') NOT NULL DEFAULT 'Active',
  Meter_No VARCHAR(50) NOT NULL UNIQUE,
  Consumer_ID INT NOT NULL,
  CONSTRAINT fk_connection_consumer FOREIGN KEY (Consumer_ID)
    REFERENCES CONSUMER(Consumer_ID) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS USAGE_RECORD (
  Record_ID INT AUTO_INCREMENT PRIMARY KEY,
  Read_Date DATE NOT NULL,
  Units_Consumed DECIMAL(10,2) NOT NULL,
  Connection_ID INT NOT NULL,
  CONSTRAINT chk_units_nonnegative CHECK (Units_Consumed >= 0),
  CONSTRAINT fk_usage_connection FOREIGN KEY (Connection_ID)
    REFERENCES CONNECTION_DETAILS(Connection_ID) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS BILL (
  Bill_ID INT AUTO_INCREMENT PRIMARY KEY,
  Payment_Status ENUM('Pending','Paid','Overdue') NOT NULL DEFAULT 'Pending',
  Subsidy DECIMAL(10,2) NOT NULL DEFAULT 0,
  Energy_Charge DECIMAL(10,2) NOT NULL,
  Final_Amount DECIMAL(10,2) NOT NULL,
  Due_Date DATE NOT NULL,
  Bill_Date DATE NOT NULL,
  Record_ID INT NOT NULL UNIQUE,
  CONSTRAINT chk_subsidy_nonnegative CHECK (Subsidy >= 0),
  CONSTRAINT chk_energy_nonnegative CHECK (Energy_Charge >= 0),
  CONSTRAINT chk_amount_nonnegative CHECK (Final_Amount >= 0),
  CONSTRAINT fk_bill_usage FOREIGN KEY (Record_ID)
    REFERENCES USAGE_RECORD(Record_ID) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS SLAB_BREAKDOWN (
  Breakdown_ID INT AUTO_INCREMENT PRIMARY KEY,
  Rate DECIMAL(10,2) NOT NULL,
  Units_In_Slab DECIMAL(10,2) NOT NULL,
  Slab_Range VARCHAR(50) NOT NULL,
  Slab_Amount DECIMAL(10,2) NOT NULL,
  Bill_ID INT NOT NULL,
  CONSTRAINT chk_rate_nonnegative CHECK (Rate >= 0),
  CONSTRAINT chk_slab_units_nonnegative CHECK (Units_In_Slab >= 0),
  CONSTRAINT chk_slab_amount_nonnegative CHECK (Slab_Amount >= 0),
  CONSTRAINT fk_slab_bill FOREIGN KEY (Bill_ID)
    REFERENCES BILL(Bill_ID) ON DELETE RESTRICT ON UPDATE CASCADE,
  INDEX idx_slab_bill (Bill_ID)
);

-- Illustrative dummy data. Do not use these tariff amounts as official KSEB rates.
INSERT INTO CONSUMER (Name,Phone,Email) VALUES
('Anu Krishnan','9876543210','anu.demo@example.com'),
('Rahul Nair','9876543211','rahul.demo@example.com'),
('Meera Das','9876543212','meera.demo@example.com');

INSERT INTO CONSUMER_ADDRESS (Consumer_ID,Consumer_Address) VALUES
(1,'House 12, Ernakulam, Kerala'),
(2,'Green Villa, Thrissur, Kerala'),
(3,'Rose House, Kottayam, Kerala');

INSERT INTO CONNECTION_DETAILS (Connection_Type,Status,Meter_No,Consumer_ID) VALUES
('Domestic','Active','MTR-DEMO-1001',1),
('Domestic','Active','MTR-DEMO-1002',2),
('Commercial','Active','MTR-DEMO-1003',3);

INSERT INTO USAGE_RECORD (Read_Date,Units_Consumed,Connection_ID) VALUES
('2026-10-01',120,1),
('2026-10-02',245,2),
('2026-10-03',45,3);

-- Energy charges based on the example progressive slabs:
-- 120 units = (50*3.25)+(50*4.15)+(20*5.25) = ₹475.00
-- 245 units = (50*3.25)+(50*4.15)+(100*5.25)+(45*6.50) = ₹1,187.50
-- 45 units = 45*3.25 = ₹146.25
INSERT INTO BILL (Payment_Status,Subsidy,Energy_Charge,Final_Amount,Due_Date,Bill_Date,Record_ID) VALUES
('Pending',20.00,475.00,455.00,'2026-10-25','2026-10-11',1),
('Paid',0.00,1187.50,1187.50,'2026-10-26','2026-10-12',2),
('Pending',10.00,146.25,136.25,'2026-10-27','2026-10-12',3);

INSERT INTO SLAB_BREAKDOWN (Rate,Units_In_Slab,Slab_Range,Slab_Amount,Bill_ID) VALUES
(3.25,50,'0–50 units',162.50,1),
(4.15,50,'51–100 units',207.50,1),
(5.25,20,'101–200 units',105.00,1),
(3.25,50,'0–50 units',162.50,2),
(4.15,50,'51–100 units',207.50,2),
(5.25,100,'101–200 units',525.00,2),
(6.50,45,'Above 200 units',292.50,2),
(3.25,45,'0–50 units',146.25,3);
