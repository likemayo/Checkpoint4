"""
RMA (Return Merchandise Authorization) Manager

Implements the complete 7-step RMA workflow:
1. RMA Request Submission
2. Validation & Authorization
3. Return Shipping
4. Inspection & Diagnosis
5. Disposition Decision
6. Repair / Replacement / Refund
7. Closure & Reporting
"""

from __future__ import annotations
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from src.notifications import NotificationService


class RMAManager:
    """Manages the complete RMA lifecycle"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
    
    # =============================
    # STEP 1: RMA Request Submission
    # =============================
    
    def submit_rma_request(
        self,
        sale_id: int,
        user_id: int,
        reason: str,
        items: List[Dict[str, Any]],  # [{"sale_item_id": 1, "product_id": 1, "quantity": 1, "reason": "..."}]
        description: str = "",
        photo_urls: List[str] = None
    ) -> Tuple[int, str]:
        """
        Submit a new RMA request (Step 1).
        
        Returns: (rma_id, rma_number)
        """
        # Validate sale exists and belongs to user
        sale = self.conn.execute(
            "SELECT id, user_id, status FROM sale WHERE id = ? AND user_id = ?",
            (sale_id, user_id)
        ).fetchone()
        
        if not sale:
            raise ValueError("Sale not found or does not belong to user")
        
        if sale["status"] not in ("COMPLETED",):
            raise ValueError(f"Cannot return a sale with status: {sale['status']}")
        
        # Check if RMA already exists for this sale
        existing = self.conn.execute(
            "SELECT id, rma_number, status FROM rma_requests WHERE sale_id = ? AND status NOT IN ('REJECTED', 'CANCELLED', 'COMPLETED')",
            (sale_id,)
        ).fetchone()
        
        if existing:
            raise ValueError(f"An active RMA already exists for this sale: {existing['rma_number']}")
        
        # Insert RMA request (no RMA number yet; issued after validation/approval)
        cursor = self.conn.execute("""
            INSERT INTO rma_requests (
                rma_number, sale_id, user_id, reason, description, photo_urls, status
            ) VALUES (NULL, ?, ?, ?, ?, ?, 'SUBMITTED')
        """, (sale_id, user_id, reason, description, json.dumps(photo_urls or [])))
        
        rma_id = cursor.lastrowid
        
        # Insert RMA items
        for item in items:
            self.conn.execute("""
                INSERT INTO rma_items (rma_id, sale_item_id, product_id, quantity, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (rma_id, item["sale_item_id"], item["product_id"], item["quantity"], item.get("reason", "")))
        
        # Log activity
        self._log_activity(rma_id, "SUBMITTED", None, "SUBMITTED", "customer", "RMA request submitted by customer")
        
        self.conn.commit()
        return rma_id, None
    
    # =============================
    # STEP 2: Validation & Authorization
    # =============================
    
    def validate_rma_request(
        self,
        rma_id: int,
        validated_by: str,
        approve: bool,
        validation_notes: str = "",
        check_warranty: bool = True,
        check_purchase_date: bool = True
    ) -> bool:
        """
        Validate RMA request and approve/reject (Step 2).
        
        Returns: True if approved, False if rejected
        """
        rma = self._get_rma(rma_id)
        
        if rma["status"] != "SUBMITTED":
            raise ValueError(f"RMA must be in SUBMITTED status to validate (current: {rma['status']})")
        
        # Perform eligibility checks
        warranty_valid = self._check_warranty(rma["sale_id"]) if check_warranty else True
        purchase_date_valid = self._check_purchase_date(rma["sale_id"]) if check_purchase_date else True
        is_eligible = warranty_valid and purchase_date_valid
        
        new_status = "APPROVED" if (approve and is_eligible) else "REJECTED"

        # If approved and no RMA number yet, generate one now
        rma_number_to_set = None
        if new_status == "APPROVED":
            if not rma["rma_number"]:
                rma_number_to_set = self._generate_rma_number()
        
        # Update RMA request
        if rma_number_to_set:
            self.conn.execute("""
                UPDATE rma_requests 
                SET status = ?,
                    validation_notes = ?,
                    validated_by = ?,
                    validated_at = CURRENT_TIMESTAMP,
                    is_eligible = ?,
                    warranty_valid = ?,
                    purchase_date_valid = ?,
                    rma_number = ?
                WHERE id = ?
            """, (new_status, validation_notes, validated_by, is_eligible, warranty_valid, purchase_date_valid, rma_number_to_set, rma_id))
        else:
            self.conn.execute("""
                UPDATE rma_requests 
                SET status = ?,
                    validation_notes = ?,
                    validated_by = ?,
                    validated_at = CURRENT_TIMESTAMP,
                    is_eligible = ?,
                    warranty_valid = ?,
                    purchase_date_valid = ?
                WHERE id = ?
            """, (new_status, validation_notes, validated_by, is_eligible, warranty_valid, purchase_date_valid, rma_id))
        
        # Log activity
        action_note = f"Validated by {validated_by}: {'Approved' if approve else 'Rejected'}. {validation_notes}"
        if rma_number_to_set:
            self._log_activity(rma_id, "VALIDATED", "SUBMITTED", new_status, validated_by, action_note + f" | RMA#: {rma_number_to_set}")
        else:
            self._log_activity(rma_id, "VALIDATED", "SUBMITTED", new_status, validated_by, action_note)
        
        self.conn.commit()
        return approve and is_eligible
    
    # =============================
    # STEP 3: Return Shipping
    # =============================
    
    def update_shipping_info(
        self,
        rma_id: int,
        carrier: str,
        tracking_number: str,
        actor: str = "customer"
    ):
        """Update shipping information when customer ships return (Step 3)."""
        rma = self._get_rma(rma_id)
        
        if rma["status"] not in ("APPROVED", "SHIPPING"):
            raise ValueError(f"RMA must be APPROVED to update shipping (current: {rma['status']})")
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'SHIPPING',
                shipping_carrier = ?,
                tracking_number = ?,
                shipped_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (carrier, tracking_number, rma_id))
        
        self._log_activity(rma_id, "SHIPPING_UPDATED", rma["status"], "SHIPPING", actor, 
                          f"Tracking: {carrier} {tracking_number}")
        
        self.conn.commit()
    
    def mark_received(self, rma_id: int, actor: str = "warehouse"):
        """Mark item as received at warehouse (Step 3)."""
        rma = self._get_rma(rma_id)
        
        if rma["status"] != "SHIPPING":
            raise ValueError(f"RMA must be SHIPPING to mark received (current: {rma['status']})")
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'RECEIVED',
                received_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (rma_id,))
        
        self._log_activity(rma_id, "RECEIVED", "SHIPPING", "RECEIVED", actor, "Item received at warehouse")
        
        self.conn.commit()
    
    # =============================
    # STEP 4: Inspection & Diagnosis
    # =============================
    
    def start_inspection(self, rma_id: int, inspected_by: str):
        """Start inspection process (Step 4)."""
        rma = self._get_rma(rma_id)
        
        if rma["status"] != "RECEIVED":
            raise ValueError(f"RMA must be RECEIVED to start inspection (current: {rma['status']})")
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'INSPECTING',
                inspected_by = ?
            WHERE id = ?
        """, (inspected_by, rma_id))
        
        self._log_activity(rma_id, "INSPECTION_STARTED", "RECEIVED", "INSPECTING", inspected_by, "Inspection started")
        
        self.conn.commit()
    
    def complete_inspection(
        self,
        rma_id: int,
        result: str,  # DEFECTIVE, MISUSE, NORMAL_WEAR, AS_DESCRIBED
        notes: str = "",
        inspected_by: str = "QA"
    ):
        """Complete inspection with result (Step 4)."""
        rma = self._get_rma(rma_id)
        
        if rma["status"] != "INSPECTING":
            raise ValueError(f"RMA must be INSPECTING to complete (current: {rma['status']})")
        
        valid_results = ("DEFECTIVE", "MISUSE", "NORMAL_WEAR", "AS_DESCRIBED")
        if result not in valid_results:
            raise ValueError(f"Invalid inspection result. Must be one of: {valid_results}")
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'INSPECTED',
                inspection_result = ?,
                inspection_notes = ?,
                inspected_by = ?,
                inspected_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (result, notes, inspected_by, rma_id))
        
        self._log_activity(rma_id, "INSPECTION_COMPLETED", "INSPECTING", "INSPECTED", inspected_by,
                          f"Result: {result}. {notes}")
        
        self.conn.commit()
    
    # =============================
    # STEP 5: Disposition Decision
    # =============================
    
    def make_disposition(
        self,
        rma_id: int,
        disposition: str,  # REFUND, REPLACEMENT, REPAIR, REJECT, STORE_CREDIT
        reason: str = "",
        decided_by: str = "warranty_team"
    ):
        """Make disposition decision (Step 5)."""
        rma = self._get_rma(rma_id)
        
        if rma["status"] not in ("INSPECTED", "DISPOSITION"):
            raise ValueError(f"RMA must be INSPECTED to make disposition (current: {rma['status']})")
        
        valid_dispositions = ("REFUND", "REPLACEMENT", "REPAIR", "REJECT", "STORE_CREDIT")
        if disposition not in valid_dispositions:
            raise ValueError(f"Invalid disposition. Must be one of: {valid_dispositions}")
        
        # Determine next status based on disposition
        # REFUND, REPLACEMENT, STORE_CREDIT require processing -> status becomes PROCESSING
        # REPAIR, REJECT can be completed immediately -> status stays DISPOSITION until manual action
        if disposition in ("REFUND", "REPLACEMENT", "STORE_CREDIT"):
            next_status = "PROCESSING"
        else:
            next_status = "DISPOSITION"
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = ?,
                disposition = ?,
                disposition_reason = ?,
                disposition_by = ?,
                disposition_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (next_status, disposition, reason, decided_by, rma_id))
        
        self._log_activity(rma_id, "DISPOSITION_DECIDED", "INSPECTED", next_status, decided_by,
                          f"Disposition: {disposition}. {reason}. Status moved to {next_status}.")
        
        self.conn.commit()
    
    # =============================
    # STEP 6: Refund / Replacement / Repair
    # =============================
    
    def process_refund(
        self,
        rma_id: int,
        amount_cents: int,
        method: str = "ORIGINAL_PAYMENT",
        actor: str = "system"
    ) -> int:
        """Process refund (Step 6)."""
        rma = self._get_rma(rma_id)
        
        if rma["disposition"] != "REFUND":
            raise ValueError(f"RMA disposition must be REFUND (current: {rma['disposition']})")
        
        # Check if refund already exists
        existing = self.conn.execute(
            "SELECT id FROM refunds WHERE rma_id = ?", (rma_id,)
        ).fetchone()
        
        if existing:
            raise ValueError("Refund already exists for this RMA")
        
        # Create refund record
        cursor = self.conn.execute("""
            INSERT INTO refunds (rma_id, sale_id, amount_cents, method, status)
            VALUES (?, ?, ?, ?, 'PENDING')
        """, (rma_id, rma["sale_id"], amount_cents, method))
        
        refund_id = cursor.lastrowid
        
        # Update RMA
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'PROCESSING',
                refund_amount_cents = ?
            WHERE id = ?
        """, (amount_cents, rma_id))
        
        self._log_activity(rma_id, "REFUND_INITIATED", "DISPOSITION", "PROCESSING", actor,
                          f"Refund initiated: ${amount_cents/100:.2f} via {method}")
        
        self.conn.commit()
        return refund_id
    
    def _adjust_inventory_for_disposition(self, rma_id: int, disposition: str):
        """
        Adjust inventory based on disposition type.
        
        - REFUND: Restore to inventory (item returned, refunded, can be resold)
        - REPLACEMENT: Do NOT restore (item defective/damaged, will be replaced with new stock)
        - REPAIR: Do NOT restore initially (item being repaired, not available for sale)
        - REJECT: Restore to inventory (return rejected, customer keeps item, no inventory change)
        - STORE_CREDIT: Restore to inventory (item returned, credit issued, can be resold)
        """
        rma_items = self.conn.execute("""
            SELECT product_id, quantity FROM rma_items WHERE rma_id = ?
        """, (rma_id,)).fetchall()
        
        if disposition in ('REFUND', 'STORE_CREDIT'):
            # Item returned and accepted - restore to inventory
            for item in rma_items:
                self.conn.execute("""
                    UPDATE product
                    SET stock = stock + ?
                    WHERE id = ?
                """, (item["quantity"], item["product_id"]))
            return "Inventory restored (items returned and accepted)"
            
        elif disposition == 'REPLACEMENT':
            # Item defective - do NOT restore (will be replaced with new stock)
            # The replacement will decrease inventory when new item is shipped
            return "Inventory not restored (defective item, replacement will decrease stock)"
            
        elif disposition == 'REPAIR':
            # Item being repaired - do NOT restore yet (not available for sale)
            # Could be restored later after repair completion
            return "Inventory not restored (item under repair, unavailable for sale)"
            
        elif disposition == 'REJECT':
            # Return rejected - customer keeps item, no inventory change needed
            return "No inventory change (return rejected, customer keeps item)"
            
        return "No inventory adjustment"
    
    def complete_refund(
        self,
        refund_id: int,
        reference: str = "",
        success: bool = True,
        error_message: str = ""
    ):
        """Complete refund processing (Step 6)."""
        refund = self.conn.execute(
            "SELECT * FROM refunds WHERE id = ?", (refund_id,)
        ).fetchone()
        
        if not refund:
            raise ValueError("Refund not found")
        
        # Get RMA to check disposition
        rma = self.conn.execute(
            "SELECT disposition FROM rma_requests WHERE id = ?", (refund["rma_id"],)
        ).fetchone()
        
        status = "COMPLETED" if success else "FAILED"
        
        self.conn.execute("""
            UPDATE refunds
            SET status = ?,
                reference = ?,
                error_message = ?,
                processed_at = CURRENT_TIMESTAMP,
                completed_at = CASE WHEN ? = 'COMPLETED' THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE id = ?
        """, (status, reference, error_message, status, refund_id))
        
        if success:
            # Mark RMA as completed
            self.conn.execute("""
                UPDATE rma_requests
                SET status = 'COMPLETED',
                    closed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (refund["rma_id"],))
            
            # Update sale status
            self.conn.execute("""
                UPDATE sale
                SET status = 'REFUNDED'
                WHERE id = ?
            """, (refund["sale_id"],))
            
            # Adjust inventory based on disposition type
            inventory_note = self._adjust_inventory_for_disposition(refund["rma_id"], rma["disposition"])
            
            # Note: total_spent_cents tracking not implemented in user table
            # Future enhancement: track user spending history
            
            self._log_activity(refund["rma_id"], "REFUND_COMPLETED", "PROCESSING", "COMPLETED", "system",
                              f"Refund completed. Reference: {reference}. {inventory_note}.")
            
            # Notify customer
            self._notify_customer(
                refund["rma_id"], 
                "COMPLETED_REFUND", 
                f"Amount: ${refund['amount_cents']/100:.2f}. Reference: {reference}"
            )
        else:
            self._log_activity(refund["rma_id"], "REFUND_FAILED", "PROCESSING", "PROCESSING", "system",
                              f"Refund failed: {error_message}")
        
        self.conn.commit()
    
    # =============================
    # STEP 7: Closure & Reporting
    # =============================
    
    def close_rma(self, rma_id: int, actor: str = "system", notes: str = ""):
        """Close RMA case (Step 7)."""
        rma = self._get_rma(rma_id)
        
        if rma["status"] == "COMPLETED":
            return  # Already closed
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'COMPLETED',
                closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (rma_id,))
        
        self._log_activity(rma_id, "CLOSED", rma["status"], "COMPLETED", actor, f"RMA case closed. {notes}")
        
        # Update metrics
        self._update_metrics(rma_id)
        
        self.conn.commit()
    
    def process_replacement(
        self,
        rma_id: int,
        actor: str = "system"
    ) -> int:
        """
        Process replacement (Step 6).
        Creates a new order for replacement items and decreases inventory.
        """
        rma = self._get_rma(rma_id)
        
        if rma["disposition"] != "REPLACEMENT":
            raise ValueError(f"RMA disposition must be REPLACEMENT (current: {rma['disposition']})")
        
        # Get items to be replaced
        rma_items = self.conn.execute("""
            SELECT product_id, quantity FROM rma_items WHERE rma_id = ?
        """, (rma_id,)).fetchall()
        
        # Create a new sale for the replacement (simplified - in production, this would be more complex)
        cursor = self.conn.execute("""
            INSERT INTO sale (user_id, status, total_cents)
            SELECT user_id, 'COMPLETED', 0
            FROM rma_requests WHERE id = ?
        """, (rma_id,))
        
        replacement_sale_id = cursor.lastrowid
        
        # Add items to the new sale and decrease inventory
        for item in rma_items:
            product = self.conn.execute("SELECT price_cents FROM product WHERE id = ?", (item["product_id"],)).fetchone()
            
            self.conn.execute("""
                INSERT INTO sale_item (sale_id, product_id, quantity, price_cents)
                VALUES (?, ?, ?, ?)
            """, (replacement_sale_id, item["product_id"], item["quantity"], product["price_cents"]))
            
            # Decrease inventory for replacement items
            self.conn.execute("""
                UPDATE product
                SET stock = stock - ?
                WHERE id = ?
            """, (item["quantity"], item["product_id"]))
        
        # Update RMA with replacement order
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'COMPLETED',
                closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (rma_id,))
        
        self._log_activity(rma_id, "REPLACEMENT_PROCESSED", "DISPOSITION", "COMPLETED", actor,
                          f"Replacement order created: #{replacement_sale_id}. Inventory decreased for replacement items.")
        
        # Notify customer
        self._notify_customer(
            rma_id,
            "COMPLETED_REPLACEMENT",
            f"Replacement order #{replacement_sale_id} has been created and will ship soon."
        )
        
        self.conn.commit()
        return replacement_sale_id
    
    def process_store_credit(
        self,
        rma_id: int,
        amount_cents: int,
        actor: str = "system"
    ):
        """
        Process store credit (Step 6).
        Issues store credit and restores inventory.
        """
        rma = self._get_rma(rma_id)
        
        if rma["disposition"] != "STORE_CREDIT":
            raise ValueError(f"RMA disposition must be STORE_CREDIT (current: {rma['disposition']})")
        
        # In a real system, this would create a store credit record
        # For now, we'll just update the RMA and adjust inventory
        
        # Adjust inventory (store credit means item returned and accepted)
        inventory_note = self._adjust_inventory_for_disposition(rma_id, "STORE_CREDIT")
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'COMPLETED',
                refund_amount_cents = ?,
                closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (amount_cents, rma_id))
        
        self._log_activity(rma_id, "STORE_CREDIT_ISSUED", "DISPOSITION", "COMPLETED", actor,
                          f"Store credit issued: ${amount_cents/100:.2f}. {inventory_note}.")
        
        # Notify customer
        self._notify_customer(
            rma_id,
            "COMPLETED_CREDIT",
            f"${amount_cents/100:.2f} in store credit has been added to your account."
        )
        
        self.conn.commit()
    
    def process_repair(
        self,
        rma_id: int,
        actor: str = "system",
        notes: str = ""
    ):
        """
        Process repair (Step 6).
        Marks item as under repair. Inventory not restored until repair complete.
        """
        rma = self._get_rma(rma_id)
        
        if rma["disposition"] != "REPAIR":
            raise ValueError(f"RMA disposition must be REPAIR (current: {rma['disposition']})")
        # Prevent duplicate initiation
        if rma["status"] != "DISPOSITION":
            raise ValueError("Repair already initiated or invalid status for initiation")
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'PROCESSING'
            WHERE id = ?
        """, (rma_id,))
        
        self._log_activity(rma_id, "REPAIR_INITIATED", "DISPOSITION", "PROCESSING", actor,
                          f"Repair initiated. {notes}. Inventory not restored (item under repair).")
        
        self.conn.commit()
    
    def complete_repair(
        self,
        rma_id: int,
        actor: str = "system",
        notes: str = ""
    ):
        """
        Complete repair and return item to customer.
        Optionally restore inventory if item not returned to customer.
        """
        rma = self._get_rma(rma_id)
        
        if rma["disposition"] != "REPAIR":
            raise ValueError(f"RMA disposition must be REPAIR (current: {rma['disposition']})")
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'COMPLETED',
                closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (rma_id,))
        
        self._log_activity(rma_id, "REPAIR_COMPLETED", "PROCESSING", "COMPLETED", actor,
                          f"Repair completed and item returned to customer. {notes}.")
        
        # Notify customer
        self._notify_customer(
            rma_id,
            "COMPLETED_REPAIR",
            "Your repaired item has been shipped back to you."
        )
        
        self.conn.commit()
    
    def process_rejection(
        self,
        rma_id: int,
        actor: str = "system",
        notes: str = ""
    ):
        """
        Process rejection (Step 6).
        Return rejected - customer keeps item, no refund, no inventory change.
        """
        rma = self._get_rma(rma_id)
        
        if rma["disposition"] != "REJECT":
            raise ValueError(f"RMA disposition must be REJECT (current: {rma['disposition']})")
        
        # No inventory change - customer keeps the item
        inventory_note = self._adjust_inventory_for_disposition(rma_id, "REJECT")
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'COMPLETED',
                closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (rma_id,))
        
        self._log_activity(rma_id, "RETURN_REJECTED", "DISPOSITION", "COMPLETED", actor,
                          f"Return rejected. {notes}. {inventory_note}.")
        
        # Notify customer
        self._notify_customer(
            rma_id,
            "REJECTED",
            f"After review, we are unable to process your return. Reason: {notes}"
        )
        
        self.conn.commit()
    
    # =============================
    # STEP 7: Closure & Reporting
    # =============================
    
    def close_rma(self, rma_id: int, actor: str = "system", notes: str = ""):
        """Close RMA case (Step 7)."""
        rma = self._get_rma(rma_id)
        
        if rma["status"] == "COMPLETED":
            return  # Already closed
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'COMPLETED',
                closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (rma_id,))
        
        self._log_activity(rma_id, "CLOSED", rma["status"], "COMPLETED", actor, f"RMA closed. {notes}")
        
        self._update_metrics(rma_id)
        
        self.conn.commit()
    
    def cancel_rma(self, rma_id: int, actor: str = "customer", reason: str = ""):
        """Cancel RMA request."""
        rma = self._get_rma(rma_id)
        
        if rma["status"] in ("COMPLETED", "CANCELLED"):
            raise ValueError(f"Cannot cancel RMA with status: {rma['status']}")
        
        self.conn.execute("""
            UPDATE rma_requests
            SET status = 'CANCELLED',
                closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (rma_id,))
        
        self._log_activity(rma_id, "CANCELLED", rma["status"], "CANCELLED", actor, f"RMA cancelled. {reason}")
        
        self.conn.commit()
    
    # =============================
    # Query / Reporting Methods
    # =============================
    
    def get_rma(self, rma_id: int = None, rma_number: str = None) -> Optional[Dict]:
        """Get RMA details with items and activity log."""
        if rma_id:
            rma = self.conn.execute("SELECT * FROM rma_requests WHERE id = ?", (rma_id,)).fetchone()
        elif rma_number:
            rma = self.conn.execute("SELECT * FROM rma_requests WHERE rma_number = ?", (rma_number,)).fetchone()
        else:
            raise ValueError("Must provide either rma_id or rma_number")
        
        if not rma:
            return None
        
        # Get items with price at purchase from sale_item
        items = self.conn.execute("""
            SELECT 
                ri.*, 
                p.name as product_name,
                CAST(si.price_cents AS REAL) / 100.0 AS price_at_purchase
            FROM rma_items ri
            JOIN product p ON ri.product_id = p.id
            JOIN sale_item si ON ri.sale_item_id = si.id
            WHERE ri.rma_id = ?
        """, (rma["id"],)).fetchall()
        
        # Get activity log
        activities = self.conn.execute("""
            SELECT * FROM rma_activity_log
            WHERE rma_id = ?
            ORDER BY created_at DESC
        """, (rma["id"],)).fetchall()
        
        # Get refund if exists
        refund = self.conn.execute("""
            SELECT * FROM refunds WHERE rma_id = ?
        """, (rma["id"],)).fetchone()
        
        # Prepare response dicts and compute derived values expected by templates
        rma_dict = dict(rma)
        items_list = [dict(item) for item in items]

        # Compute requested refund amount (sum of quantity * price_at_purchase)
        try:
            requested_total = sum((it.get("quantity", 0) or 0) * float(it.get("price_at_purchase", 0.0) or 0.0) for it in items_list)
        except Exception:
            requested_total = 0.0
        rma_dict["requested_refund_amount"] = requested_total

        # Back-compat keys for templates
        # Map shipping_carrier -> carrier
        if "shipping_carrier" in rma_dict and rma_dict.get("shipping_carrier"):
            rma_dict["carrier"] = rma_dict.get("shipping_carrier")

        # Extract first photo_url from JSON array if present
        try:
            import json as _json
            if rma_dict.get("photo_urls"):
                photos = _json.loads(rma_dict["photo_urls"]) if isinstance(rma_dict["photo_urls"], str) else rma_dict["photo_urls"]
                if isinstance(photos, list) and photos:
                    rma_dict["photo_url"] = photos[0]
        except Exception:
            # Ignore photo parsing errors
            pass

        return {
            "rma": rma_dict,
            "items": items_list,
            "activities": [dict(activity) for activity in activities],
            "refund": dict(refund) if refund else None
        }
    
    def get_user_rmas(self, user_id: int, status: str = None) -> List[Dict]:
        """Get all RMAs for a user."""
        query = "SELECT * FROM rma_requests WHERE user_id = ?"
        params = [user_id]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        rmas = self.conn.execute(query, params).fetchall()
        return [dict(rma) for rma in rmas]
    
    def get_metrics(self, start_date: str = None, end_date: str = None) -> Dict:
        """Get RMA metrics for reporting (Step 7)."""
        query = "SELECT * FROM rma_metrics"
        params = []
        
        if start_date and end_date:
            query += " WHERE metric_date BETWEEN ? AND ?"
            params = [start_date, end_date]
        
        query += " ORDER BY metric_date DESC"
        
        metrics = self.conn.execute(query, params).fetchall()
        return [dict(m) for m in metrics]
    
    # =============================
    # Helper Methods
    # =============================
    
    def _get_rma(self, rma_id: int) -> sqlite3.Row:
        """Get RMA or raise error."""
        rma = self.conn.execute("SELECT * FROM rma_requests WHERE id = ?", (rma_id,)).fetchone()
        if not rma:
            raise ValueError(f"RMA {rma_id} not found")
        return rma
    
    def _generate_rma_number(self) -> str:
        """Generate unique RMA number."""
        # Get count for today
        today = datetime.now().strftime("%Y%m%d")
        count = self.conn.execute("""
            SELECT COUNT(*) FROM rma_requests 
            WHERE rma_number LIKE ?
        """, (f"RMA-{today}-%",)).fetchone()[0]
        
        return f"RMA-{today}-{count + 1:04d}"
    
    def _check_warranty(self, sale_id: int) -> bool:
        """Check if sale is within warranty period (e.g., 30 days)."""
        sale = self.conn.execute(
            "SELECT sale_time FROM sale WHERE id = ?", (sale_id,)
        ).fetchone()
        
        if not sale:
            return False
        
        # Default: 30 days warranty
        sale_time = datetime.fromisoformat(sale["sale_time"])
        warranty_expires = sale_time + timedelta(days=30)
        
        return datetime.now() < warranty_expires
    
    def _check_purchase_date(self, sale_id: int) -> bool:
        """Verify purchase date is valid."""
        sale = self.conn.execute(
            "SELECT sale_time FROM sale WHERE id = ?", (sale_id,)
        ).fetchone()
        
        if not sale:
            return False
        
        # Sale must exist and be in the past
        sale_time = datetime.fromisoformat(sale["sale_time"])
        return sale_time < datetime.now()
    
    def _log_activity(
        self,
        rma_id: int,
        action: str,
        old_status: Optional[str],
        new_status: str,
        actor: str,
        notes: str = "",
        metadata: Dict = None
    ):
        """Log activity to audit trail and create notifications for status changes."""
        # Log activity
        self.conn.execute("""
            INSERT INTO rma_activity_log (rma_id, action, old_status, new_status, actor, notes, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (rma_id, action, old_status, new_status, actor, notes, json.dumps(metadata or {})))
        
        # Create notification for significant status changes
        # Get RMA details including disposition for notification
        rma = self.conn.execute("""
            SELECT user_id, rma_number, disposition FROM rma_requests WHERE id = ?
        """, (rma_id,)).fetchone()
        
        if rma and new_status and new_status != old_status:
            # Status transitions that warrant notifications
            notify_statuses = [
                'SUBMITTED', 'APPROVED', 'REJECTED', 'RECEIVED', 
                'INSPECTING', 'INSPECTED', 'DISPOSITION', 'PROCESSING', 'COMPLETED', 'CANCELLED'
            ]
            
            if new_status in notify_statuses:
                try:
                    NotificationService.create_rma_status_notification(
                        conn=self.conn,
                        user_id=rma["user_id"],
                        rma_id=rma_id,
                        rma_number=rma["rma_number"],
                        old_status=old_status,
                        new_status=new_status,
                        disposition=rma["disposition"]
                    )
                except Exception as e:
                    # Don't fail the RMA operation if notification fails
                    print(f"Warning: Failed to create notification: {e}")
    
    def _notify_customer(self, rma_id: int, notification_type: str, details: str = ""):
        """
        Send notification to customer about RMA status.
        In production, this would integrate with email/SMS service.
        For now, we log it in the activity log for audit purposes.
        """
        notification_messages = {
            "APPROVED": "Your return request has been approved. Please ship your item(s) to our warehouse.",
            "RECEIVED": "We have received your returned item(s) and will begin inspection shortly.",
            "COMPLETED_REFUND": f"Your refund has been processed successfully. {details}",
            "COMPLETED_REPLACEMENT": f"Your replacement order has been created. {details}",
            "COMPLETED_REPAIR": f"Your item has been repaired and will be returned to you. {details}",
            "COMPLETED_CREDIT": f"Store credit has been issued to your account. {details}",
            "REJECTED": f"Your return request has been reviewed. {details}",
            "CANCELLED": "Your return request has been cancelled."
        }
        
        message = notification_messages.get(notification_type, details)
        
        # Log notification in activity log
        self._log_activity(
            rma_id=rma_id,
            action="CUSTOMER_NOTIFIED",
            old_status=None,
            new_status=None,
            actor="system",
            notes=f"Notification sent: {notification_type}",
            metadata={"notification_type": notification_type, "message": message}
        )
        
        # In production: Send actual email/SMS here
        # Example: email_service.send(to=customer_email, subject=..., body=message)
        
        return message
    
    def _update_metrics(self, rma_id: int):
        """Update daily metrics for completed RMA (Step 7)."""
        rma = self._get_rma(rma_id)
        metric_date = datetime.now().strftime("%Y-%m-%d")
        
        # Calculate cycle times
        if rma["created_at"] and rma["closed_at"]:
            created = datetime.fromisoformat(rma["created_at"])
            closed = datetime.fromisoformat(rma["closed_at"])
            total_cycle_hours = (closed - created).total_seconds() / 3600
        else:
            total_cycle_hours = None
        
        # Insert or update metrics
        self.conn.execute("""
            INSERT INTO rma_metrics (metric_date, total_requests, completed_requests)
            VALUES (?, 1, 1)
            ON CONFLICT(metric_date) DO UPDATE SET
                total_requests = total_requests + 1,
                completed_requests = completed_requests + 1
        """, (metric_date,))
