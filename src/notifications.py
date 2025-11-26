"""
Notification Service for RMA Status Changes
Handles creation and retrieval of user notifications
"""

import sqlite3
from typing import List, Dict, Optional
from datetime import datetime


class NotificationService:
    """Service for managing user notifications"""
    
    # Status display names
    STATUS_NAMES = {
        'SUBMITTED': 'Submitted',
        'VALIDATING': 'Under Validation',
        'APPROVED': 'Approved',
        'REJECTED': 'Rejected',
        'SHIPPING': 'In Transit to Warehouse',
        'RECEIVED': 'Received at Warehouse',
        'INSPECTING': 'Under Inspection',
        'INSPECTED': 'Inspection Complete',
        'DISPOSITION': 'Processing Decision',
        'PROCESSING': 'Processing Refund/Replacement',
        'COMPLETED': 'Completed',
        'CANCELLED': 'Cancelled'
    }
    
    @staticmethod
    def create_rma_status_notification(
        conn: sqlite3.Connection,
        user_id: int,
        rma_id: int,
        rma_number: str,
        old_status: Optional[str],
        new_status: str,
        disposition: Optional[str] = None
    ) -> int:
        """
        Create a notification for RMA status change
        
        Args:
            conn: Database connection
            user_id: User to notify
            rma_id: RMA request ID
            rma_number: RMA number (e.g., "RMA-2025-001234")
            old_status: Previous status (None if new RMA)
            new_status: New status
            disposition: Disposition decision (REFUND, REPAIR, etc.)
            
        Returns:
            Notification ID
        """
        status_display = NotificationService.STATUS_NAMES.get(new_status, new_status)
        
        # Generate appropriate message based on status and disposition
        if new_status == 'SUBMITTED':
            title = "Return Request Submitted"
            message = f"Your return request {rma_number} has been submitted and is awaiting review."
        elif new_status == 'APPROVED':
            title = "Return Request Approved"
            message = f"Your return request {rma_number} has been approved. Please ship the item(s) back to us."
        elif new_status == 'REJECTED':
            title = "Return Request Not Approved"
            message = f"Your return request {rma_number} could not be approved. Please check the details for more information."
        elif new_status == 'RECEIVED':
            title = "Return Received"
            message = f"We've received your return {rma_number} and will inspect it shortly."
        elif new_status == 'INSPECTING':
            title = "Return Under Inspection"
            message = f"Your return {rma_number} is currently being inspected by our team."
        elif new_status == 'INSPECTED':
            title = "Inspection Complete"
            message = f"Inspection of your return {rma_number} is complete. We're processing the next steps."
        elif new_status == 'DISPOSITION':
            # Disposition decision made - use specific message based on disposition
            if disposition == 'REFUND':
                title = "Refund Approved"
                message = f"Your return {rma_number} has been approved for a refund. We're processing your refund now."
            elif disposition == 'REPAIR':
                title = "Repair Approved"
                message = f"Your item {rma_number} will be repaired. We'll notify you once the repair is complete."
            elif disposition == 'REPLACEMENT':
                title = "Replacement Approved"
                message = f"Your return {rma_number} has been approved for a replacement. We're preparing your replacement order."
            elif disposition == 'STORE_CREDIT':
                title = "Store Credit Approved"
                message = f"Your return {rma_number} has been approved for store credit. The credit will be added to your account shortly."
            elif disposition == 'REJECT':
                title = "Return Decision: Not Approved"
                message = f"After review, your return {rma_number} cannot be processed. The item will remain with you."
            else:
                title = "Return Being Processed"
                message = f"Your return {rma_number} is being processed. We'll update you soon."
        elif new_status == 'PROCESSING':
            # Processing the disposition
            if disposition == 'REFUND':
                title = "Refund Processing"
                message = f"Your refund for {rma_number} is being processed. You'll receive it within 3-5 business days."
            elif disposition == 'REPAIR':
                title = "Item Under Repair"
                message = f"Your item {rma_number} is currently being repaired by our technicians."
            elif disposition == 'REPLACEMENT':
                title = "Replacement Processing"
                message = f"We're preparing your replacement order for {rma_number}."
            elif disposition == 'STORE_CREDIT':
                title = "Store Credit Processing"
                message = f"We're adding store credit to your account for {rma_number}."
            else:
                title = "Processing Your Return"
                message = f"Your return {rma_number} is being processed."
        elif new_status == 'COMPLETED':
            # Completed - use disposition-specific message
            if disposition == 'REFUND':
                title = "Refund Completed"
                message = f"Your refund for {rma_number} has been completed. Thank you!"
            elif disposition == 'REPAIR':
                title = "Repair Completed"
                message = f"Your item {rma_number} has been repaired and shipped back to you. Thank you!"
            elif disposition == 'REPLACEMENT':
                title = "Replacement Sent"
                message = f"Your replacement for {rma_number} has been shipped. Thank you!"
            elif disposition == 'STORE_CREDIT':
                title = "Store Credit Issued"
                message = f"Store credit for {rma_number} has been added to your account. Thank you!"
            elif disposition == 'REJECT':
                title = "Return Closed"
                message = f"Your return request {rma_number} has been closed."
            else:
                title = "Return Completed"
                message = f"Your return {rma_number} has been completed. Thank you for your patience!"
        elif new_status == 'CANCELLED':
            title = "Return Cancelled"
            message = f"Your return request {rma_number} has been cancelled."
        else:
            title = "Return Status Update"
            message = f"Your return {rma_number} status has been updated to: {status_display}"
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, type, title, message, rma_id, rma_number)
            VALUES (?, 'RMA_STATUS', ?, ?, ?, ?)
        """, (user_id, title, message, rma_id, rma_number))
        conn.commit()
        
        return cursor.lastrowid
    
    @staticmethod
    def get_user_notifications(
        conn: sqlite3.Connection,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get notifications for a user
        
        Args:
            conn: Database connection
            user_id: User ID
            unread_only: If True, only return unread notifications
            limit: Maximum number of notifications to return
            
        Returns:
            List of notification dictionaries
        """
        query = """
            SELECT 
                id, type, title, message, rma_id, rma_number,
                is_read, read_at, created_at
            FROM notifications
            WHERE user_id = ?
        """
        params = [user_id]
        
        if unread_only:
            query += " AND is_read = 0"
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        notifications = []
        for row in cursor.fetchall():
            notifications.append({
                'id': row[0],
                'type': row[1],
                'title': row[2],
                'message': row[3],
                'rma_id': row[4],
                'rma_number': row[5],
                'is_read': bool(row[6]),
                'read_at': row[7],
                'created_at': row[8]
            })
        
        return notifications
    
    @staticmethod
    def get_unread_count(conn: sqlite3.Connection, user_id: int) -> int:
        """Get count of unread notifications for a user"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM notifications
            WHERE user_id = ? AND is_read = 0
        """, (user_id,))
        
        result = cursor.fetchone()
        return result[0] if result else 0
    
    @staticmethod
    def mark_as_read(conn: sqlite3.Connection, notification_id: int, user_id: int) -> bool:
        """
        Mark a notification as read
        
        Args:
            conn: Database connection
            notification_id: Notification ID
            user_id: User ID (for security check)
            
        Returns:
            True if successful
        """
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notifications
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ? AND is_read = 0
        """, (notification_id, user_id))
        conn.commit()
        
        return cursor.rowcount > 0
    
    @staticmethod
    def mark_all_as_read(conn: sqlite3.Connection, user_id: int) -> int:
        """
        Mark all notifications as read for a user
        
        Returns:
            Number of notifications marked as read
        """
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notifications
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND is_read = 0
        """, (user_id,))
        conn.commit()
        
        return cursor.rowcount
    
    @staticmethod
    def delete_notification(conn: sqlite3.Connection, notification_id: int, user_id: int) -> bool:
        """
        Delete a notification
        
        Args:
            conn: Database connection
            notification_id: Notification ID
            user_id: User ID (for security check)
            
        Returns:
            True if successful
        """
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM notifications
            WHERE id = ? AND user_id = ?
        """, (notification_id, user_id))
        conn.commit()
        
        return cursor.rowcount > 0
