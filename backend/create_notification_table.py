"""Manually create notification table and apply US-067 changes."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def create_notification_table():
    url = "postgresql+asyncpg://postgres:SmartHandoff%40123@localhost:9000/smarthandoff"
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        # Create ENUMs
        await conn.execute(text("""
            CREATE TYPE notification_type AS ENUM ('SMS', 'EMAIL');
        """))
        await conn.execute(text("""
            CREATE TYPE notification_status AS ENUM ('PENDING', 'SENT', 'DELIVERED', 'FAILED', 'OPTED_OUT');
        """))
        print("✓ Created ENUM types")
        
        # Create table
        await conn.execute(text("""
            CREATE TABLE notification (
                id UUID PRIMARY KEY,
                idempotency_key VARCHAR(255) NOT NULL,
                type notification_type NOT NULL,
                recipient_id UUID,
                phone_or_email VARCHAR(512),
                template VARCHAR(128) NOT NULL,
                substitutions JSON,
                delivery_status notification_status NOT NULL DEFAULT 'PENDING',
                urgency_override BOOLEAN NOT NULL DEFAULT false,
                twilio_message_sid VARCHAR(64),
                sendgrid_message_id VARCHAR(128),
                retry_count SMALLINT NOT NULL DEFAULT 0,
                last_error TEXT,
                sent_at TIMESTAMPTZ,
                delivered_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """))
        print("✓ Created notification table")
        
        # Create constraints and indexes
        await conn.execute(text("""
            ALTER TABLE notification 
            ADD CONSTRAINT uq_notification_idempotency_key UNIQUE (idempotency_key);
        """))
        await conn.execute(text("""
            CREATE INDEX ix_notification_recipient_status 
            ON notification(recipient_id, delivery_status);
        """))
        await conn.execute(text("""
            CREATE INDEX ix_notification_twilio_sid 
            ON notification(twilio_message_sid);
        """))
        await conn.execute(text("""
            ALTER TABLE notification 
            ADD CONSTRAINT fk_notification_patient 
            FOREIGN KEY (recipient_id) REFERENCES patient(id) ON DELETE SET NULL;
        """))
        print("✓ Created constraints and indexes")
        
        # Add notification service revisions to alembic_version
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0001')"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0002')"))
        print("✓ Updated alembic_version with notification migrations")
    
    await engine.dispose()
    print("\n✅ Notification table created successfully!")
    print("   - Includes US-067 changes (delivery_status, urgency_override)")
    print("   - Ready for notification service to use")

if __name__ == "__main__":
    asyncio.run(create_notification_table())
