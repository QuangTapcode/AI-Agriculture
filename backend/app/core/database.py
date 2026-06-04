from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings


SQLITE_FALLBACK_URL = "sqlite:///./agri_ai.db"


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _build_engine(database_url: str):
    return create_engine(
        database_url,
        connect_args=_connect_args(database_url),
        pool_pre_ping=not database_url.startswith("sqlite"),
    )


def _create_configured_engine():
    try:
        return _build_engine(settings.DATABASE_URL), settings.DATABASE_URL
    except (ImportError, ModuleNotFoundError):
        if settings.ENVIRONMENT.lower() == "production":
            raise
        return _build_engine(SQLITE_FALLBACK_URL), SQLITE_FALLBACK_URL


engine, active_database_url = _create_configured_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _is_sqlite() -> bool:
    return active_database_url.startswith("sqlite")


def _quote_sqlite_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sqlite_table_name(conn, table_name: str) -> str | None:
    return conn.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND lower(name) = lower(:table_name)"
        ),
        {"table_name": table_name},
    ).scalar()


def _sqlite_columns(conn, table_name: str) -> set[str]:
    quoted_table = _quote_sqlite_identifier(table_name)
    rows = conn.exec_driver_sql(f"PRAGMA table_info({quoted_table})").fetchall()
    return {row[1] for row in rows}


def _sqlite_rename_table(conn, source_table: str, target_table: str) -> str:
    legacy_table = target_table
    suffix = 1
    while _sqlite_table_name(conn, legacy_table):
        suffix += 1
        legacy_table = f"{target_table}_{suffix}"
    conn.exec_driver_sql(
        "ALTER TABLE "
        f"{_quote_sqlite_identifier(source_table)} "
        f"RENAME TO {_quote_sqlite_identifier(legacy_table)}"
    )
    return legacy_table


def _migrate_legacy_sqlite_users() -> str | None:
    """Move the old lowercase users table out of the way before create_all().

    Older local databases used a lowercase `users` table with columns like
    `id` and `full_name`. SQLite resolves table names case-insensitively, so
    that table prevents SQLAlchemy from creating the current `Users` table.
    """
    if not _is_sqlite():
        return None

    with engine.begin() as conn:
        users_table = _sqlite_table_name(conn, "Users")
        if not users_table:
            return None
        if "UserID" in _sqlite_columns(conn, users_table):
            return None
        return _sqlite_rename_table(conn, users_table, "legacy_users")


def _copy_legacy_sqlite_users(legacy_table: str | None) -> None:
    if not legacy_table or not _is_sqlite():
        return

    with engine.begin() as conn:
        if not _sqlite_table_name(conn, "Users"):
            return
        legacy_columns = _sqlite_columns(conn, legacy_table)
        if not {"id", "full_name", "password_hash"}.issubset(legacy_columns):
            return

        quoted_legacy = _quote_sqlite_identifier(legacy_table)
        conn.exec_driver_sql(
            f"""
            INSERT OR IGNORE INTO "Users"
                ("UserID", "FullName", "Email", "PhoneNumber", "ZaloID",
                 "PasswordHash", "Role", "Region", "IsActive", "IsVerified",
                 "CreatedAt", "UpdatedAt")
            SELECT
                id,
                full_name,
                email,
                phone_number,
                zalo_id,
                password_hash,
                COALESCE(role, 'farmer'),
                region,
                COALESCE(is_active, 1),
                COALESCE(is_verified, 0),
                COALESCE(created_at, CURRENT_TIMESTAMP),
                COALESCE(updated_at, CURRENT_TIMESTAMP)
            FROM {quoted_legacy}
            """
        )


def _switch_to_sqlite_fallback():
    global engine, active_database_url
    engine = _build_engine(SQLITE_FALLBACK_URL)
    active_database_url = SQLITE_FALLBACK_URL
    SessionLocal.configure(bind=engine)


def _apply_lightweight_schema_upgrades() -> None:
    """Add columns introduced after the classroom SQL script for local demos."""
    column_upgrades = {
        "WeatherData": {
            "Latitude": "FLOAT NULL",
            "Longitude": "FLOAT NULL",
            "WindSpeed": "FLOAT NULL",
            "UVIndex": "FLOAT NULL",
            "Pressure": "FLOAT NULL",
            "WeatherCode": "INTEGER NULL" if _is_sqlite() else "INT NULL",
            "SourceName": "VARCHAR(100) NULL",
            "SourceURL": "VARCHAR(500) NULL",
            "SourceUpdatedAt": "DATETIME NULL",
            "FetchedAt": "DATETIME NULL",
            "IsRealtime": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
            "IsMock": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
        },
        "WeatherForecasts": {
            "SourceName": "VARCHAR(100) NULL",
            "SourceURL": "VARCHAR(500) NULL",
            "SourceUpdatedAt": "DATETIME NULL",
            "FetchedAt": "DATETIME NULL",
            "IsRealtime": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
            "IsMock": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
        },
        "AIConversations": {
            "ContextSnapshot": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
            "Provider": "VARCHAR(50) NULL",
            "ModelName": "VARCHAR(100) NULL",
            "TokenUsage": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
        },
        "AlertNotifications": {
            "Channel": "VARCHAR(20) NULL",
            "Receiver": "VARCHAR(255) NULL",
            "Status": "VARCHAR(30) NULL",
            "ProviderMessageID": "VARCHAR(100) NULL",
            "ErrorMessage": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
        },
        "AlertSubscriptions": {
            "Receiver": "VARCHAR(255) NULL",
        },
        "WeatherAlerts": {
            "UserID": "INTEGER NULL" if _is_sqlite() else "INT NULL",
            "NotifyMethod": "VARCHAR(20) NOT NULL DEFAULT 'Email'",
            "Receiver": "VARCHAR(255) NULL",
            "LastTriggered": "DATETIME NULL",
            "LastValue": "FLOAT NULL",
        },
        "QualityRecords": {
            "DefectDetails": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
            "ModelVersion": "VARCHAR(100) NULL",
            "InferenceTimeMs": "FLOAT NULL",
            "ImageWidth": "INTEGER NULL" if _is_sqlite() else "INT NULL",
            "ImageHeight": "INTEGER NULL" if _is_sqlite() else "INT NULL",
            "SuggestedPriceSource": "VARCHAR(100) NULL",
        },
        "MarketPrices": {
            "SourceType": "VARCHAR(50) NULL",
            "ObservedAt": "DATETIME NULL",
            "FetchedAt": "DATETIME NULL",
            "ConfidenceScore": "FLOAT NULL",
            "IsRealtime": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
            "IsMock": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
            "Metadata": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
        },
        "MarketNews": {
            "Content": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
            "URL": "VARCHAR(500) NULL",
            "FetchedAt": "DATETIME NULL",
            "CropTags": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
            "RegionTags": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
            "ImpactLevel": "VARCHAR(20) NULL",
            "ImpactScore": "FLOAT NULL",
            "IsRealtime": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
            "IsMock": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
            "Metadata": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
        },
        "MarketAnalysisResults": {
            "SourceName": "VARCHAR(120) NULL",
            "SourceURL": "VARCHAR(500) NULL",
            "FetchedAt": "DATETIME NULL",
            "IsRealtime": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
            "IsMock": "BOOLEAN NULL DEFAULT 0" if _is_sqlite() else "BIT NULL DEFAULT 0",
            "Status": "VARCHAR(30) NULL",
            "ErrorMessage": "TEXT NULL" if _is_sqlite() else "NVARCHAR(MAX) NULL",
        },
    }
    if _is_sqlite():
        with engine.begin() as conn:
            for requested_table, columns in column_upgrades.items():
                table_name = _sqlite_table_name(conn, requested_table)
                if not table_name:
                    continue
                existing = _sqlite_columns(conn, table_name)
                for column, ddl in columns.items():
                    if column not in existing:
                        conn.exec_driver_sql(
                            f"ALTER TABLE {_quote_sqlite_identifier(table_name)} "
                            f"ADD COLUMN {_quote_sqlite_identifier(column)} {ddl}"
                        )
        return

    if active_database_url.startswith("mssql"):
        with engine.begin() as conn:
            for table_name, columns in column_upgrades.items():
                for column, ddl in columns.items():
                    conn.execute(
                        text(
                            f"IF COL_LENGTH('{table_name}', :column_name) IS NULL "
                            f"ALTER TABLE {table_name} ADD {column} {ddl}"
                        ),
                        {"column_name": column},
                    )
        _apply_mssql_unicode_upgrades()
        _fix_mssql_alert_type_constraint()


def _apply_price_indexes() -> None:
    """Add UniqueConstraint and composite index to price tables for existing DBs.

    - uq_marketprices_upsert_key  : UNIQUE (CropID, Region, PriceDate, QualityGrade, MarketType)
    - ix_pricehistory_crop_region_date : INDEX (CropID, Region, RecordDate)

    Both are IF NOT EXISTS — safe to run on every startup.
    Duplicates already in the DB will cause the UNIQUE constraint to be skipped with a warning.
    """
    import logging as _log
    logger = _log.getLogger(__name__)

    if _is_sqlite():
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_marketprices_upsert_key "
                    "ON MarketPrices (CropID, Region, PriceDate, QualityGrade, MarketType)"
                )
                conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_pricehistory_crop_region_date "
                    "ON PriceHistory (CropID, Region, RecordDate)"
                )
        except Exception as exc:
            logger.warning("[schema] price indexes (SQLite): %s", exc)
        return

    if active_database_url.startswith("mssql"):
        stmts = [
            (
                "uq_marketprices_upsert_key",
                "MarketPrices",
                "IF NOT EXISTS (SELECT 1 FROM sys.indexes "
                "WHERE object_id = OBJECT_ID('MarketPrices') "
                "AND name = 'uq_marketprices_upsert_key') "
                "ALTER TABLE MarketPrices ADD CONSTRAINT uq_marketprices_upsert_key "
                "UNIQUE (CropID, Region, PriceDate, QualityGrade, MarketType)",
            ),
            (
                "ix_pricehistory_crop_region_date",
                "PriceHistory",
                "IF NOT EXISTS (SELECT 1 FROM sys.indexes "
                "WHERE object_id = OBJECT_ID('PriceHistory') "
                "AND name = 'ix_pricehistory_crop_region_date') "
                "CREATE INDEX ix_pricehistory_crop_region_date "
                "ON PriceHistory (CropID, Region, RecordDate)",
            ),
        ]
        for name, table, stmt in stmts:
            try:
                with engine.begin() as conn:
                    conn.execute(text(stmt))
            except Exception as exc:
                logger.warning(
                    "[schema] Could not add %s on %s (possible duplicate data): %s",
                    name, table, exc,
                )


def _fix_mssql_alert_type_constraint() -> None:
    """Ensure AlertSubscriptions.AlertType constraint allows Vietnamese Unicode values."""
    if not active_database_url.startswith("mssql"):
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                DECLARE @cname NVARCHAR(256)
                SELECT @cname = cc.name
                FROM sys.check_constraints cc
                WHERE cc.parent_object_id = OBJECT_ID('AlertSubscriptions')
                  AND cc.definition NOT LIKE N'%Tr%n%'
                  AND cc.definition LIKE '%AlertType%'
                IF @cname IS NOT NULL
                    EXEC('ALTER TABLE AlertSubscriptions DROP CONSTRAINT [' + @cname + ']')
            """))
            conn.execute(text("""
                IF NOT EXISTS (
                    SELECT 1 FROM sys.check_constraints cc
                    WHERE cc.parent_object_id = OBJECT_ID('AlertSubscriptions')
                      AND cc.definition LIKE N'%Tr%n%'
                )
                ALTER TABLE AlertSubscriptions ADD CONSTRAINT CK_AlertSubs_AlertType_V2
                CHECK (AlertType IN (
                    'Tren', 'Duoi', 'Thay doi',
                    N'Trên', N'Dưới', N'Thay đổi'
                ))
            """))
    except Exception:
        pass


def _apply_mssql_unicode_upgrades() -> None:
    """Keep Vietnamese text columns Unicode in existing SQL Server schemas."""
    unicode_upgrades = {
        "Notifications": {
            "Title": "NVARCHAR(255) NOT NULL",
            "Message": "NVARCHAR(MAX) NOT NULL",
        },
        "NotificationDeliveries": {
            "ErrorMessage": "NVARCHAR(MAX) NULL",
        },
        "WeatherLocations": {
            "Region": "NVARCHAR(100) NOT NULL",
            "Province": "NVARCHAR(100) NULL",
            "District": "NVARCHAR(100) NULL",
            "Ward": "NVARCHAR(100) NULL",
        },
        "WeatherAlerts": {
            "Region": "NVARCHAR(100) NOT NULL",
            "Title": "NVARCHAR(200) NOT NULL",
            "Message": "NVARCHAR(MAX) NOT NULL",
            "Recommendation": "NVARCHAR(MAX) NULL",
        },
        "MarketNews": {
            "Title": "NVARCHAR(300) NOT NULL",
            "Summary": "NVARCHAR(MAX) NULL",
            "SourceName": "NVARCHAR(100) NULL",
            "Region": "NVARCHAR(100) NULL",
        },
        "MarketChannels": {
            "ChannelName": "NVARCHAR(100) NOT NULL",
            "Region": "NVARCHAR(100) NULL",
        },
        "MarketRecommendations": {
            "Region": "NVARCHAR(100) NOT NULL",
            "QualityGrade": "NVARCHAR(20) NULL",
            "RecommendedChannel": "NVARCHAR(50) NULL",
            "Reason": "NVARCHAR(MAX) NULL",
            "Warning": "NVARCHAR(MAX) NULL",
        },
        "MarketPrices": {
            "Region": "NVARCHAR(100) NOT NULL",
            "QualityGrade": "NVARCHAR(20) NULL",
            "MarketType": "NVARCHAR(50) NULL",
            "SourceName": "NVARCHAR(100) NULL",
        },
        "QualityRecords": {
            "DetectedIssues": "NVARCHAR(MAX) NULL",
            "DefectDetails": "NVARCHAR(MAX) NULL",
            "Recommendation": "NVARCHAR(MAX) NULL",
        },
        "HarvestRecords": {
            "Region": "NVARCHAR(100) NOT NULL",
            "FertilizerUsed": "NVARCHAR(200) NULL",
            "PesticideUsed": "NVARCHAR(200) NULL",
            "Status": "NVARCHAR(50) NOT NULL",
            "Notes": "NVARCHAR(MAX) NULL",
        },
        "HarvestForecastResults": {
            "WeatherWarning": "NVARCHAR(MAX) NULL",
            "LaborRecommendation": "NVARCHAR(MAX) NULL",
            "TransportRecommendation": "NVARCHAR(MAX) NULL",
        },
        "WeatherData": {
            "Region": "NVARCHAR(100) NOT NULL",
            "WeatherDesc": "NVARCHAR(100) NULL",
            "SourceName": "NVARCHAR(100) NULL",
        },
        "WeatherForecasts": {
            "Region": "NVARCHAR(100) NOT NULL",
            "WeatherDesc": "NVARCHAR(100) NULL",
            "Recommendation": "NVARCHAR(MAX) NULL",
            "SourceName": "NVARCHAR(100) NULL",
        },
        "WeatherRules": {
            "CropName": "NVARCHAR(100) NOT NULL",
            "GrowthStage": "NVARCHAR(100) NULL",
            "Message": "NVARCHAR(MAX) NOT NULL",
            "Recommendation": "NVARCHAR(MAX) NULL",
        },
        "WeatherRecommendations": {
            "Region": "NVARCHAR(100) NOT NULL",
            "CropName": "NVARCHAR(100) NULL",
            "GrowthStage": "NVARCHAR(100) NULL",
            "Decision": "NVARCHAR(100) NOT NULL",
            "Reason": "NVARCHAR(MAX) NOT NULL",
            "Timing": "NVARCHAR(100) NULL",
        },
    }
    for table_name, columns in unicode_upgrades.items():
        for column, ddl in columns.items():
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {column} {ddl}"))
            except SQLAlchemyError:
                pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create database tables for the imported SQLAlchemy models."""
    import app.models  # noqa: F401
    from app.core.seed import seed_demo_seasons, seed_demo_users, seed_market_channels

    try:
        legacy_users_table = _migrate_legacy_sqlite_users()
        Base.metadata.create_all(bind=engine)
        _apply_lightweight_schema_upgrades()
        _apply_price_indexes()
        _copy_legacy_sqlite_users(legacy_users_table)
        seed_demo_users(SessionLocal)
        seed_demo_seasons(SessionLocal)
        seed_market_channels(SessionLocal)
    except SQLAlchemyError:
        if settings.ENVIRONMENT.lower() == "production" or active_database_url.startswith("sqlite"):
            raise
        _switch_to_sqlite_fallback()
        legacy_users_table = _migrate_legacy_sqlite_users()
        Base.metadata.create_all(bind=engine)
        _apply_lightweight_schema_upgrades()
        _apply_price_indexes()
        _copy_legacy_sqlite_users(legacy_users_table)
        seed_demo_users(SessionLocal)
        seed_demo_seasons(SessionLocal)
        seed_market_channels(SessionLocal)
