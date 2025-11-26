-- Migration: Add Notifications System for RMA Status Changes
-- Created: 2025-11-27
-- Description: User notifications for RMA status updates

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- Notification details
    type TEXT NOT NULL DEFAULT 'RMA_STATUS' CHECK(type IN ('RMA_STATUS', 'REFUND', 'GENERAL')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    
    -- Related entity
    rma_id INTEGER,
    rma_number TEXT,
    
    -- Status
    is_read INTEGER DEFAULT 0 CHECK(is_read IN (0, 1)),
    read_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (rma_id) REFERENCES rma_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, is_read, created_at);
