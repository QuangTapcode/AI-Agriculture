/* ============================================================
DỰ ÁN: HỆ THỐNG AI HỖ TRỢ NÔNG DÂN
DỰ BÁO THU HOẠCH VÀ ĐỊNH GIÁ NÔNG SẢN
Cơ sở dữ liệu: SQL Server
Phiên bản: 1.1
Ngày cập nhật: 05/2026
Mô tả: Full schema + seed data cho hệ thống AgriAI
FIX: Đổi tất cả enum CHECK constraint sang ASCII để tránh lỗi
     VARCHAR vs NVARCHAR khi Python/pyodbc INSERT dữ liệu.
     Mapping: 'Loai 1','Loai 2','Loai 3' | 'Ban buon','Ban le','Xuat khau'
              'Lua gao','Trai cay','Rau cu','Cong nghiep','Khac'
              'Dang trong','Sap thu hoach','Da thu hoach','That mua'
============================================================ */

-- ============================================================
-- BƯỚC 1: TẠO DATABASE
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'NongNghiepAI')
BEGIN
    CREATE DATABASE NongNghiepAI;
    PRINT N'✓ Đã tạo database NongNghiepAI';
END
GO

USE NongNghiepAI;
GO

-- ============================================================
-- BƯỚC 2: XÓA BẢNG CŨ (nếu chạy lại script)
-- ============================================================

-- Bước 2a: Xóa tất cả FK constraints trong DB trước để tránh lỗi phụ thuộc
-- (bao gồm cả bảng do ORM tự tạo: Seasons, Notifications, UserSettings, ...)
DECLARE @dropFK NVARCHAR(MAX) = N''
SELECT @dropFK += N'ALTER TABLE ' + QUOTENAME(OBJECT_NAME(fk.parent_object_id))
               + N' DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';' + CHAR(10)
FROM sys.foreign_keys fk
IF LEN(@dropFK) > 0
    EXEC sp_executesql @dropFK
GO

-- Bước 2b: Xóa các bảng ORM (Seasons, Notifications, UserSettings, ...)
IF OBJECT_ID('NotificationDeliveries',  'U') IS NOT NULL DROP TABLE NotificationDeliveries;
IF OBJECT_ID('Notifications',           'U') IS NOT NULL DROP TABLE Notifications;
IF OBJECT_ID('NotificationPreferences', 'U') IS NOT NULL DROP TABLE NotificationPreferences;
IF OBJECT_ID('UserSettings',            'U') IS NOT NULL DROP TABLE UserSettings;
IF OBJECT_ID('Seasons',                 'U') IS NOT NULL DROP TABLE Seasons;
IF OBJECT_ID('DashboardCache',          'U') IS NOT NULL DROP TABLE DashboardCache;
IF OBJECT_ID('RegionalPriceSnapshots',  'U') IS NOT NULL DROP TABLE RegionalPriceSnapshots;
IF OBJECT_ID('AirQualityObservations',  'U') IS NOT NULL DROP TABLE AirQualityObservations;
IF OBJECT_ID('DataSources',             'U') IS NOT NULL DROP TABLE DataSources;
GO

-- Bước 2c: Xóa các bảng chính
IF OBJECT_ID('HarvestForecastResults','U') IS NOT NULL DROP TABLE HarvestForecastResults;
IF OBJECT_ID('AIConversations',       'U') IS NOT NULL DROP TABLE AIConversations;
IF OBJECT_ID('QualityRecords',        'U') IS NOT NULL DROP TABLE QualityRecords;
IF OBJECT_ID('AlertNotifications',    'U') IS NOT NULL DROP TABLE AlertNotifications;
IF OBJECT_ID('AlertSubscriptions',    'U') IS NOT NULL DROP TABLE AlertSubscriptions;
IF OBJECT_ID('PriceForecastResults',  'U') IS NOT NULL DROP TABLE PriceForecastResults;
IF OBJECT_ID('PriceHistory',          'U') IS NOT NULL DROP TABLE PriceHistory;
IF OBJECT_ID('MarketPrices',          'U') IS NOT NULL DROP TABLE MarketPrices;
IF OBJECT_ID('PricingRequests',       'U') IS NOT NULL DROP TABLE PricingRequests;
IF OBJECT_ID('MarketSuggestions',     'U') IS NOT NULL DROP TABLE MarketSuggestions;
IF OBJECT_ID('HarvestSchedule',       'U') IS NOT NULL DROP TABLE HarvestSchedule;
IF OBJECT_ID('WeatherData',           'U') IS NOT NULL DROP TABLE WeatherData;
IF OBJECT_ID('CropTypes',             'U') IS NOT NULL DROP TABLE CropTypes;
IF OBJECT_ID('Users',                 'U') IS NOT NULL DROP TABLE Users;
GO

PRINT N'✓ Đã xóa các bảng cũ';
GO

-- ============================================================
-- BƯỚC 3: TẠO CÁC BẢNG
-- ============================================================

-- --------------------------------------------------------------
-- BẢNG 1: Người dùng
-- --------------------------------------------------------------
CREATE TABLE Users (
    UserID          INT             PRIMARY KEY IDENTITY(1,1),
    FullName        NVARCHAR(100)   NOT NULL,
    Email           NVARCHAR(100)   UNIQUE,
    PhoneNumber     NVARCHAR(20),
    ZaloID          NVARCHAR(100),
    PasswordHash    NVARCHAR(255)   NOT NULL,
    Role            NVARCHAR(20)    DEFAULT 'farmer'
                    CHECK (Role IN ('farmer', 'admin', 'expert')),
    Region          NVARCHAR(100),
    IsActive        BIT             DEFAULT 1,
    IsVerified      BIT             DEFAULT 0,
    CreatedAt       DATETIME        DEFAULT GETDATE(),
    UpdatedAt       DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng Users';

-- --------------------------------------------------------------
-- BẢNG 2: Loại nông sản
-- FIX: Category dùng ASCII ('Lua gao','Trai cay','Rau cu','Cong nghiep','Khac')
-- --------------------------------------------------------------
CREATE TABLE CropTypes (
    CropID              INT             PRIMARY KEY IDENTITY(1,1),
    CropName            NVARCHAR(100)   NOT NULL UNIQUE,
    CropNameEN          NVARCHAR(100),
    Category            NVARCHAR(50)    NOT NULL
                        CHECK (Category IN ('Lua gao', 'Trai cay', 'Rau cu', 'Cong nghiep', 'Khac')),
    GrowthDurationDays  INT,
    HarvestSeason       NVARCHAR(100),
    TypicalPriceMin     DECIMAL(18,2),
    TypicalPriceMax     DECIMAL(18,2),
    Description         NVARCHAR(MAX),
    ImageURL            NVARCHAR(500),
    CreatedAt           DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng CropTypes';

-- --------------------------------------------------------------
-- BẢNG 3: Dữ liệu thời tiết
-- --------------------------------------------------------------
CREATE TABLE WeatherData (
    WeatherID       INT             PRIMARY KEY IDENTITY(1,1),
    Region          NVARCHAR(100)   NOT NULL,
    RecordDate      DATE            NOT NULL,
    TempMin         FLOAT,
    TempMax         FLOAT,
    Humidity        FLOAT,
    Rainfall        FLOAT,
    SunshineHours   FLOAT,
    WeatherDesc     NVARCHAR(100),
    CreatedAt       DATETIME        DEFAULT GETDATE(),
    CONSTRAINT UQ_Weather UNIQUE (Region, RecordDate)
);
GO
PRINT N'✓ Đã tạo bảng WeatherData';

-- --------------------------------------------------------------
-- BẢNG 4: Lịch trình thu hoạch
-- FIX: Status dùng ASCII ('Dang trong','Sap thu hoach','Da thu hoach','That mua')
-- --------------------------------------------------------------
CREATE TABLE HarvestSchedule (
    ScheduleID              INT             PRIMARY KEY IDENTITY(1,1),
    UserID                  INT             NOT NULL FOREIGN KEY REFERENCES Users(UserID),
    CropID                  INT             NOT NULL FOREIGN KEY REFERENCES CropTypes(CropID),
    PlantingDate            DATE            NOT NULL,
    AreaSize                FLOAT,
    Region                  NVARCHAR(100)   NOT NULL,
    ExpectedHarvestDate     DATE,
    ActualHarvestDate       DATE,
    EstimatedYieldKg        FLOAT,
    ActualYieldKg           FLOAT,
    FertilizerUsed          NVARCHAR(200),
    PesticideUsed           NVARCHAR(200),
    Status                  NVARCHAR(50)    DEFAULT 'Dang trong'
                            CHECK (Status IN ('Dang trong', 'Sap thu hoach', 'Da thu hoach', 'That mua')),
    Notes                   NVARCHAR(MAX),
    CreatedAt               DATETIME        DEFAULT GETDATE(),
    UpdatedAt               DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng HarvestSchedule';

-- --------------------------------------------------------------
-- BẢNG 5: Giá thị trường (dữ liệu cào web)
-- FIX: QualityGrade -> 'Loai 1','Loai 2','Loai 3'
--      MarketType   -> 'Ban buon','Ban le','Xuat khau'
-- --------------------------------------------------------------
CREATE TABLE MarketPrices (
    PriceID         INT             PRIMARY KEY IDENTITY(1,1),
    CropID          INT             NOT NULL FOREIGN KEY REFERENCES CropTypes(CropID),
    Region          NVARCHAR(100)   NOT NULL,
    PricePerKg      DECIMAL(18,2)   NOT NULL,
    QualityGrade    NVARCHAR(20)    DEFAULT 'Loai 1'
                    CHECK (QualityGrade IN ('Loai 1', 'Loai 2', 'Loai 3')),
    MarketType      NVARCHAR(50)    DEFAULT 'Ban le'
                    CHECK (MarketType IN ('Ban buon', 'Ban le', 'Xuat khau')),
    SourceURL       NVARCHAR(500),
    SourceName      NVARCHAR(100),
    PriceDate       DATE            NOT NULL,
    UpdatedAt       DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng MarketPrices';

-- --------------------------------------------------------------
-- BẢNG 6: Lịch sử giá (dùng cho AI dự báo)
-- --------------------------------------------------------------
CREATE TABLE PriceHistory (
    HistoryID       INT             PRIMARY KEY IDENTITY(1,1),
    CropID          INT             NOT NULL FOREIGN KEY REFERENCES CropTypes(CropID),
    Region          NVARCHAR(100)   NOT NULL,
    AvgPrice        DECIMAL(18,2)   NOT NULL,
    MinPrice        DECIMAL(18,2),
    MaxPrice        DECIMAL(18,2),
    Volume          FLOAT,
    RecordDate      DATE            NOT NULL,
    CreatedAt       DATETIME        DEFAULT GETDATE(),
    CONSTRAINT UQ_PriceHistory UNIQUE (CropID, Region, RecordDate)
);
GO
PRINT N'✓ Đã tạo bảng PriceHistory';

-- --------------------------------------------------------------
-- BẢNG 7: Kết quả dự báo giá từ AI
-- FIX: PriceTrend -> 'Tang','Giam','On dinh'
-- --------------------------------------------------------------
CREATE TABLE PriceForecastResults (
    ForecastID      INT             PRIMARY KEY IDENTITY(1,1),
    CropID          INT             NOT NULL FOREIGN KEY REFERENCES CropTypes(CropID),
    Region          NVARCHAR(100)   NOT NULL,
    ForecastDate    DATE            NOT NULL,
    PredictedPrice  DECIMAL(18,2)   NOT NULL,
    ConfidenceLow   DECIMAL(18,2),
    ConfidenceHigh  DECIMAL(18,2),
    PriceTrend      NVARCHAR(20)    CHECK (PriceTrend IN ('Tang', 'Giam', 'On dinh',
                                                          'increasing', 'decreasing', 'stable')),
    ModelVersion    NVARCHAR(50),
    GeneratedAt     DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng PriceForecastResults';

-- --------------------------------------------------------------
-- BẢNG 8: Kiểm tra chất lượng (YOLOv8)
-- FIX: AIGrade -> 'Loai 1','Loai 2','Loai 3'
-- --------------------------------------------------------------
CREATE TABLE QualityRecords (
    RecordID            INT             PRIMARY KEY IDENTITY(1,1),
    ScheduleID          INT             FOREIGN KEY REFERENCES HarvestSchedule(ScheduleID),
    UserID              INT             NOT NULL FOREIGN KEY REFERENCES Users(UserID),
    CropID              INT             NOT NULL FOREIGN KEY REFERENCES CropTypes(CropID),
    ImagePath           NVARCHAR(500)   NOT NULL,
    AIGrade             NVARCHAR(20)    CHECK (AIGrade IN ('Loai 1', 'Loai 2', 'Loai 3')),
    ConfidenceScore     FLOAT,
    DetectedIssues      NVARCHAR(MAX),
    SuggestedPriceMin   DECIMAL(18,2),
    SuggestedPriceMax   DECIMAL(18,2),
    Recommendation      NVARCHAR(MAX),
    CheckDate           DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng QualityRecords';

-- --------------------------------------------------------------
-- BẢNG 9: Đăng ký cảnh báo giá
-- FIX: AlertType -> 'Tren','Duoi','Thay doi'
-- --------------------------------------------------------------
CREATE TABLE AlertSubscriptions (
    AlertID             INT             PRIMARY KEY IDENTITY(1,1),
    UserID              INT             NOT NULL FOREIGN KEY REFERENCES Users(UserID),
    CropID              INT             NOT NULL FOREIGN KEY REFERENCES CropTypes(CropID),
    Region              NVARCHAR(100)   NOT NULL,
    TargetPrice         DECIMAL(18,2)   NOT NULL,
    AlertType           NVARCHAR(20)    DEFAULT N'Trên'
                        CHECK (AlertType IN ('Tren', 'Duoi', 'Thay doi', N'Trên', N'Dưới', N'Thay đổi')),
    NotifyMethod        NVARCHAR(20)    DEFAULT 'Email'
                        CHECK (NotifyMethod IN ('Email', 'SMS', 'Zalo', 'App')),
    IsActive            BIT             DEFAULT 1,
    LastTriggered       DATETIME,
    CreatedAt           DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng AlertSubscriptions';

-- --------------------------------------------------------------
-- BẢNG 10: Lịch sử hội thoại AI
-- FIX: Topic -> 'Gia ca','Thu hoach','Chat luong','Thoi tiet','Dich benh','Khac'
-- --------------------------------------------------------------
CREATE TABLE AIConversations (
    ConvID          INT             PRIMARY KEY IDENTITY(1,1),
    UserID          INT             FOREIGN KEY REFERENCES Users(UserID),
    SessionID       NVARCHAR(100),
    UserMessage     NVARCHAR(MAX)   NOT NULL,
    AIResponse      NVARCHAR(MAX)   NOT NULL,
    Topic           NVARCHAR(50)    CHECK (Topic IN ('Gia ca', 'Thu hoach', 'Chat luong',
                                                     'Thoi tiet', 'Dich benh', 'Khac')),
    RelatedCropID   INT             FOREIGN KEY REFERENCES CropTypes(CropID),
    CreatedAt       DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng AIConversations';

-- --------------------------------------------------------------
-- BẢNG 11: Kết quả dự báo thu hoạch từ AI
-- --------------------------------------------------------------
CREATE TABLE HarvestForecastResults (
    ForecastID              INT PRIMARY KEY IDENTITY(1,1),
    ScheduleID              INT NOT NULL FOREIGN KEY REFERENCES HarvestSchedule(ScheduleID),
    ExpectedHarvestDate     DATE NOT NULL,
    ConfidenceScore         FLOAT,
    WeatherWarning          NVARCHAR(MAX),
    LaborRecommendation     NVARCHAR(MAX),
    TransportRecommendation NVARCHAR(MAX),
    ModelVersion            NVARCHAR(50),
    GeneratedAt             DATETIME DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng HarvestForecastResults';

-- --------------------------------------------------------------
-- BẢNG 12: Lịch sử yêu cầu định giá
-- FIX: QualityGrade -> 'Loai 1','Loai 2','Loai 3'
-- --------------------------------------------------------------
CREATE TABLE PricingRequests (
    RequestID       INT             PRIMARY KEY IDENTITY(1,1),
    UserID          INT             NULL FOREIGN KEY REFERENCES Users(UserID),
    CropID          INT             NOT NULL FOREIGN KEY REFERENCES CropTypes(CropID),
    Region          NVARCHAR(100)   NOT NULL,
    QuantityKg      FLOAT           NOT NULL,
    QualityGrade    NVARCHAR(20)    CHECK (QualityGrade IN ('Loai 1', 'Loai 2', 'Loai 3')),
    SuggestedPrice  DECIMAL(18,2),
    MinPrice        DECIMAL(18,2),
    MaxPrice        DECIMAL(18,2),
    CreatedAt       DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng PricingRequests';

-- --------------------------------------------------------------
-- BẢNG 13: Kết quả tư vấn kênh bán hàng
-- FIX: QualityGrade, RecommendedChannel -> ASCII
-- --------------------------------------------------------------
CREATE TABLE MarketSuggestions (
    SuggestionID        INT             PRIMARY KEY IDENTITY(1,1),
    UserID              INT             NOT NULL FOREIGN KEY REFERENCES Users(UserID),
    CropID              INT             NOT NULL FOREIGN KEY REFERENCES CropTypes(CropID),
    Region              NVARCHAR(100)   NOT NULL,
    QuantityKg          FLOAT           NOT NULL,
    QualityGrade        NVARCHAR(20)    CHECK (QualityGrade IN ('Loai 1', 'Loai 2', 'Loai 3')),
    RecommendedChannel  NVARCHAR(50)    CHECK (RecommendedChannel IN ('Thuong lai', 'Cho dau moi', 'Xuat khau')),
    EstimatedProfit     DECIMAL(18,2),
    Reason              NVARCHAR(MAX),
    Warning             NVARCHAR(MAX),
    CreatedAt           DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng MarketSuggestions';

-- --------------------------------------------------------------
-- BẢNG 14: Lịch sử gửi thông báo
-- (SendStatus đã ASCII: 'Pending','Sent','Failed' - không đổi)
-- --------------------------------------------------------------
CREATE TABLE AlertNotifications (
    NotificationID  INT             PRIMARY KEY IDENTITY(1,1),
    AlertID         INT             NOT NULL FOREIGN KEY REFERENCES AlertSubscriptions(AlertID),
    CurrentPrice    DECIMAL(18,2),
    Message         NVARCHAR(MAX),
    NotifyMethod    NVARCHAR(20),
    SendStatus      NVARCHAR(20)    DEFAULT 'Pending'
                    CHECK (SendStatus IN ('Pending', 'Sent', 'Failed')),
    SentAt          DATETIME        DEFAULT GETDATE()
);
GO
PRINT N'✓ Đã tạo bảng AlertNotifications';
GO

-- ============================================================
-- BƯỚC 4: INDEX
-- ============================================================
CREATE INDEX IDX_MarketPrices_Crop_Region   ON MarketPrices          (CropID, Region, PriceDate DESC);
CREATE INDEX IDX_PriceHistory_Crop_Region   ON PriceHistory          (CropID, Region, RecordDate DESC);
CREATE INDEX IDX_PriceForecast_Crop_Region  ON PriceForecastResults  (CropID, Region, ForecastDate);
CREATE INDEX IDX_HarvestSchedule_User       ON HarvestSchedule       (UserID, Status);
CREATE INDEX IDX_QualityRecords_User        ON QualityRecords        (UserID, CheckDate DESC);
CREATE INDEX IDX_AlertSubscriptions_Active  ON AlertSubscriptions    (IsActive, CropID);
CREATE INDEX IDX_AIConversations_User       ON AIConversations       (UserID, CreatedAt DESC);
CREATE INDEX IDX_HarvestForecast_Schedule   ON HarvestForecastResults(ScheduleID, GeneratedAt DESC);
CREATE INDEX IDX_PricingRequests_User       ON PricingRequests       (UserID, CreatedAt DESC);
CREATE INDEX IDX_MarketSuggestions_User     ON MarketSuggestions     (UserID, CreatedAt DESC);
CREATE INDEX IDX_AlertNotifications_Alert   ON AlertNotifications    (AlertID, SentAt DESC);
GO
PRINT N'✓ Đã tạo các Index';
GO

-- ============================================================
-- BƯỚC 5: SEED DATA
-- ============================================================

-- Users
INSERT INTO Users (FullName, Email, PhoneNumber, ZaloID, PasswordHash, Role, Region) VALUES
(N'Nguyễn Văn An',   'nguyenvanan@gmail.com',    '0901234567', 'zalo_001', '$2b$12$hashpassword1', 'farmer', N'Hà Nội'),
(N'Trần Thị Mỹ',     'tranthimy2205@gmail.com',  '0912345678', 'zalo_002', '$2b$12$hashpassword2', 'farmer', N'TP.HCM'),
(N'Lê Văn Bình',     'levanbinhfarmer@gmail.com','0923456789', 'zalo_003', '$2b$12$hashpassword3', 'farmer', N'Cần Thơ'),
(N'Phạm Thị Lan',    'phamthilan@gmail.com',     '0934567890', 'zalo_004', '$2b$12$hashpassword4', 'farmer', N'Đà Lạt'),
(N'Admin Hệ thống',  'admin@agriAI.vn',          '0800000001', NULL,       '$2b$12$hashpassword0', 'admin',  N'Hà Nội');
GO

-- CropTypes (Category dùng ASCII)
INSERT INTO CropTypes (CropName, CropNameEN, Category, GrowthDurationDays, HarvestSeason, TypicalPriceMin, TypicalPriceMax, Description) VALUES
(N'Lúa',        'Rice',          'Lua gao',     100, N'Tháng 5-6, 10-11', 6000,   9000,   N'Lúa nước, cây lương thực chính của Việt Nam'),
(N'Ngô',        'Corn',          'Lua gao',     90,  N'Tháng 3-4, 7-8',   5000,   8000,   N'Ngô lai, dùng làm thức ăn chăn nuôi và thực phẩm'),
(N'Cà phê',     'Coffee',        'Cong nghiep', 270, N'Tháng 11-2',       30000,  60000,  N'Cà phê Robusta và Arabica, xuất khẩu chủ lực'),
(N'Sầu riêng',  'Durian',        'Trai cay',    120, N'Tháng 5-8',        60000,  150000, N'Sầu riêng Musang King, Ri6, xuất khẩu Trung Quốc'),
(N'Xoài',       'Mango',         'Trai cay',    90,  N'Tháng 3-5',        15000,  40000,  N'Xoài cát Hòa Lộc, xoài Đài Loan'),
(N'Thanh long', 'Dragon Fruit',  'Trai cay',    30,  N'Quanh năm',        8000,   25000,  N'Thanh long ruột đỏ, ruột trắng Bình Thuận'),
(N'Rau muống',  'Water Spinach', 'Rau cu',      25,  N'Quanh năm',        5000,   12000,  N'Rau muống nước và rau muống cạn'),
(N'Cà chua',    'Tomato',        'Rau cu',      75,  N'Tháng 10-2',       8000,   20000,  N'Cà chua bi, cà chua thân gỗ'),
(N'Khoai lang', 'Sweet Potato',  'Rau cu',      100, N'Tháng 9-12',       7000,   15000,  N'Khoai lang tím, khoai lang mật'),
(N'Hồ tiêu',    'Black Pepper',  'Cong nghiep', 365, N'Tháng 1-3',        60000,  120000, N'Hồ tiêu đen Phú Quốc, Bình Phước');
GO

-- WeatherData
INSERT INTO WeatherData (Region, RecordDate, TempMin, TempMax, Humidity, Rainfall, SunshineHours, WeatherDesc) VALUES
(N'Hà Nội',  '2026-04-01', 22, 30, 75, 5.2,  6.5, N'Nắng nhẹ'),
(N'Hà Nội',  '2026-04-02', 21, 28, 80, 15.0, 3.0, N'Mưa rào'),
(N'Hà Nội',  '2026-04-03', 23, 31, 70, 0.0,  8.0, N'Nắng'),
(N'TP.HCM',  '2026-04-01', 26, 35, 65, 0.0,  9.5, N'Nắng nóng'),
(N'TP.HCM',  '2026-04-02', 25, 33, 70, 20.5, 5.0, N'Mưa chiều'),
(N'Cần Thơ', '2026-04-01', 25, 34, 72, 2.0,  8.5, N'Nắng nhẹ'),
(N'Đà Lạt',  '2026-04-01', 15, 23, 85, 8.0,  4.0, N'Sương mù buổi sáng'),
(N'Đà Nẵng', '2026-04-01', 24, 32, 68, 0.0,  9.0, N'Nắng');
GO

-- HarvestSchedule (Status dùng ASCII)
INSERT INTO HarvestSchedule (UserID, CropID, PlantingDate, AreaSize, Region, ExpectedHarvestDate, EstimatedYieldKg, Status) VALUES
(1, 1, '2026-01-15', 2.5, N'Hà Nội',  '2026-04-25', 12500, 'Sap thu hoach'),
(2, 4, '2025-12-01', 1.0, N'TP.HCM',  '2026-04-01', 8000,  'Da thu hoach'),
(3, 6, '2026-02-01', 3.0, N'Cần Thơ', '2026-03-03', 15000, 'Da thu hoach'),
(4, 3, '2025-06-01', 5.0, N'Đà Lạt',  '2026-03-01', 25000, 'Dang trong'),
(1, 8, '2026-02-15', 0.5, N'Hà Nội',  '2026-05-01', 3000,  'Dang trong');
GO

-- MarketPrices (QualityGrade, MarketType dùng ASCII)
INSERT INTO MarketPrices (CropID, Region, PricePerKg, QualityGrade, MarketType, SourceName, PriceDate) VALUES
(1, N'Hà Nội',     7500,  'Loai 1', 'Ban le',    N'agro.gov.vn',   '2026-04-24'),
(1, N'TP.HCM',     7200,  'Loai 1', 'Ban le',    N'agro.gov.vn',   '2026-04-24'),
(1, N'Cần Thơ',    6800,  'Loai 1', 'Ban buon',  N'giaviet.com',   '2026-04-24'),
(4, N'TP.HCM',     95000, 'Loai 1', 'Ban le',    N'agro.gov.vn',   '2026-04-24'),
(4, N'Cần Thơ',    85000, 'Loai 1', 'Ban buon',  N'giaviet.com',   '2026-04-24'),
(4, N'Tiền Giang', 65000, 'Loai 1', 'Ban buon',  N'agro.gov.vn',   '2026-04-24'),
(3, N'Đà Lạt',     45000, 'Loai 1', 'Xuat khau', N'vicofa.com.vn', '2026-04-24'),
(6, N'Bình Thuận', 12000, 'Loai 1', 'Ban buon',  N'agro.gov.vn',   '2026-04-24'),
(5, N'Cần Thơ',    25000, 'Loai 1', 'Ban buon',  N'agro.gov.vn',   '2026-04-24');
GO

-- PriceHistory (31 ngày cho Lúa - Hà Nội)
DECLARE @i INT = 30;
DECLARE @basePrice DECIMAL(18,2) = 7000;
WHILE @i >= 0
BEGIN
    INSERT INTO PriceHistory (CropID, Region, AvgPrice, MinPrice, MaxPrice, Volume, RecordDate)
    VALUES (
        1, N'Hà Nội',
        @basePrice + (@i * 15) + (ABS(CHECKSUM(NEWID())) % 200 - 100),
        @basePrice + (@i * 15) - 200,
        @basePrice + (@i * 15) + 300,
        500 + (ABS(CHECKSUM(NEWID())) % 100),
        DATEADD(DAY, -@i, CAST('2026-04-24' AS DATE))
    );
    SET @i = @i - 1;
END
GO

PRINT N'✓ Đã nạp dữ liệu mẫu';
GO

-- ============================================================
-- BƯỚC 6: KIỂM TRA
-- ============================================================
SELECT t.name AS TableName, p.rows AS TotalRows
FROM sys.tables t
INNER JOIN sys.partitions p ON t.object_id = p.OBJECT_ID
WHERE t.is_ms_shipped = 0 AND p.index_id IN (0,1)
ORDER BY t.name;

PRINT N'';
PRINT N'✅ Hoàn thành! Database NongNghiepAI đã sẵn sàng.';
PRINT N'';
PRINT N'📝 Bảng enum value mapping (dùng trong Python):';
PRINT N'   QualityGrade : Loai 1 / Loai 2 / Loai 3';
PRINT N'   MarketType   : Ban buon / Ban le / Xuat khau';
PRINT N'   Category     : Lua gao / Trai cay / Rau cu / Cong nghiep / Khac';
PRINT N'   Status       : Dang trong / Sap thu hoach / Da thu hoach / That mua';
PRINT N'   PriceTrend   : Tang / Giam / On dinh  (hoặc increasing/decreasing/stable)';
PRINT N'   AlertType    : Tren / Duoi / Thay doi';
PRINT N'   Topic        : Gia ca / Thu hoach / Chat luong / Thoi tiet / Dich benh / Khac';
GO
