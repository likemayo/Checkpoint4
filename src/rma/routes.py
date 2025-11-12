"""RMA (Returns & Refunds) API Routes"""

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from pathlib import Path
import sqlite3
import os
from .manager import RMAManager

bp = Blueprint("rma", __name__, url_prefix="/rma", template_folder=Path(__file__).parent.joinpath("templates"))


def get_conn():
    """Get database connection."""
    root = Path(__file__).resolve().parents[2]
    db_path = os.environ.get("APP_DB_PATH", str(root / "app.sqlite"))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    """Decorator to require user login."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json:
                return jsonify({"error": "Unauthorized", "details": "Login required"}), 401
            flash("Please login to access this page", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# =============================
# STEP 1: RMA Request Submission
# =============================

@bp.route("/submit", methods=["POST"])
@login_required
def submit_rma():
    """
    Submit a new RMA request (Step 1: Customer submission).
    
    POST /rma/submit
    Body: {
        "sale_id": 123,
        "reason": "Product defective",
        "description": "Screen is cracked",
        "items": [
            {"sale_item_id": 1, "product_id": 1, "quantity": 1, "reason": "Defective"}
        ],
        "photo_urls": ["http://example.com/photo1.jpg"]
    }
    """
    user_id = session.get("user_id")
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "BadRequest", "details": "JSON body required"}), 400
    
    required_fields = ["sale_id", "reason", "items"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": "BadRequest", "details": f"Missing required field: {field}"}), 400
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        rma_id, rma_number = manager.submit_rma_request(
            sale_id=data["sale_id"],
            user_id=user_id,
            reason=data["reason"],
            items=data["items"],
            description=data.get("description", ""),
            photo_urls=data.get("photo_urls", [])
        )
        
        # Auto-validate synchronously (system rules)
        approved = manager.validate_rma_request(
            rma_id=rma_id,
            validated_by="system",
            approve=True  # will still be gated by internal checks
        )
        
        # Fetch updated RMA
        rma_data = manager.get_rma(rma_id=rma_id)
        conn.close()

        status = rma_data["rma"]["status"]
        rma_number = rma_data["rma"].get("rma_number")
        msg = (
            f"RMA validated and approved. Your RMA number is {rma_number}"
            if approved else
            "RMA submitted but failed validation. Please contact support."
        )
        
        return jsonify({
            "success": True,
            "rma_id": rma_id,
            "rma_number": rma_number,
            "status": status,
            "message": msg
        }), 201
        
    except ValueError as e:
        return jsonify({"error": "ValidationError", "details": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "ServerError", "details": str(e)}), 500


@bp.route("/my-requests", methods=["GET"])
@login_required
def get_my_rma_requests():
    """
    Get all RMA requests for the logged-in user.
    
    GET /rma/my-requests?status=SUBMITTED
    """
    user_id = session.get("user_id")
    status = request.args.get("status")
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        rmas = manager.get_user_rmas(user_id, status=status)
        
        conn.close()
        
        return jsonify({
            "success": True,
            "count": len(rmas),
            "rmas": rmas
        }), 200
        
    except Exception as e:
        return jsonify({"error": "ServerError", "details": str(e)}), 500


@bp.route("/<rma_number>", methods=["GET"])
@login_required
def get_rma_details(rma_number: str):
    """
    Get details of a specific RMA request.
    
    GET /rma/RMA-20251111-0001
    """
    user_id = session.get("user_id")
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        rma_data = manager.get_rma(rma_number=rma_number)
        
        if not rma_data:
            return jsonify({"error": "NotFound", "details": "RMA not found"}), 404
        
        # Verify user owns this RMA
        if rma_data["rma"]["user_id"] != user_id:
            return jsonify({"error": "Forbidden", "details": "You don't have access to this RMA"}), 403
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": rma_data
        }), 200
        
    except Exception as e:
        return jsonify({"error": "ServerError", "details": str(e)}), 500


# =============================
# STEP 2: Validation & Authorization (Admin only)
# =============================

@bp.route("/admin/validate/<int:rma_id>", methods=["POST"])
def admin_validate_rma(rma_id: int):
    """
    Validate and approve/reject RMA request (Step 2: Support/System validation).
    
    POST /rma/admin/validate/123
    Body: {
        "approve": true,
        "validation_notes": "Verified warranty is valid",
        "validated_by": "support_agent_01"
    }
    """
    # TODO: Add admin authentication
    data = request.get_json() or {}
    
    approve = data.get("approve", True)
    validation_notes = data.get("validation_notes", "")
    validated_by = data.get("validated_by", "system")
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        result = manager.validate_rma_request(
            rma_id=rma_id,
            validated_by=validated_by,
            approve=approve,
            validation_notes=validation_notes
        )
        
        conn.close()
        
        status_text = "approved" if result else "rejected"
        
        return jsonify({
            "success": True,
            "rma_id": rma_id,
            "approved": result,
            "message": f"RMA has been {status_text}"
        }), 200
        
    except ValueError as e:
        return jsonify({"error": "ValidationError", "details": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "ServerError", "details": str(e)}), 500


# =============================
# STEP 3: Return Shipping
# =============================

@bp.route("/<int:rma_id>/shipping", methods=["POST"])
@login_required
def update_shipping(rma_id: int):
    """
    Update shipping information (Step 3: Customer ships return).
    
    POST /rma/123/shipping
    Body: {
        "carrier": "UPS",
        "tracking_number": "1Z999AA10123456784"
    }
    """
    user_id = session.get("user_id")
    data = request.get_json() or {}
    
    carrier = data.get("carrier")
    tracking_number = data.get("tracking_number")
    
    if not carrier or not tracking_number:
        return jsonify({"error": "BadRequest", "details": "carrier and tracking_number are required"}), 400
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        # Verify user owns this RMA
        rma_data = manager.get_rma(rma_id=rma_id)
        if not rma_data or rma_data["rma"]["user_id"] != user_id:
            return jsonify({"error": "Forbidden", "details": "Access denied"}), 403
        
        manager.update_shipping_info(rma_id, carrier, tracking_number, actor=f"user_{user_id}")
        
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "Shipping information updated",
            "tracking": f"{carrier} {tracking_number}"
        }), 200
        
    except ValueError as e:
        return jsonify({"error": "ValidationError", "details": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "ServerError", "details": str(e)}), 500


@bp.route("/admin/<int:rma_id>/received", methods=["POST"])
def admin_mark_received(rma_id: int):
    """
    Mark item as received at warehouse (Step 3: Warehouse receives return).
    
    POST /rma/admin/123/received
    """
    # TODO: Add warehouse/admin authentication
    data = request.get_json() or {}
    actor = data.get("actor", "warehouse")
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        manager.mark_received(rma_id, actor=actor)
        
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "Item marked as received"
        }), 200
        
    except ValueError as e:
        return jsonify({"error": "ValidationError", "details": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "ServerError", "details": str(e)}), 500


# =============================
# STEP 4: Inspection & Diagnosis (QA/Technician)
# =============================

@bp.route("/admin/<int:rma_id>/inspect/start", methods=["POST"])
def admin_start_inspection(rma_id: int):
    """
    Start inspection (Step 4: QA starts inspection).
    
    POST /rma/admin/123/inspect/start
    Body: {"inspected_by": "qa_tech_01"}
    """
    # Accept JSON or form-encoded
    data = request.get_json(silent=True) or {}
    inspected_by = data.get("inspected_by") or request.form.get("inspected_by") or "QA"
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        manager.start_inspection(rma_id, inspected_by=inspected_by)
        
        conn.close()
        
        # If form submission (not JSON), redirect back to inspection page
        if not request.is_json:
            flash("Inspection started", "success")
            return redirect(url_for("rma.admin_inspect_page", rma_id=rma_id))
        
        return jsonify({
            "success": True,
            "message": "Inspection started"
        }), 200
        
    except ValueError as e:
        if not request.is_json:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for("rma.admin_inspect_page", rma_id=rma_id))
        return jsonify({"error": "ValidationError", "details": str(e)}), 400
    except Exception as e:
        if not request.is_json:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for("rma.admin_inspect_page", rma_id=rma_id))
        return jsonify({"error": "ServerError", "details": str(e)}), 500


@bp.route("/admin/<int:rma_id>/inspect/complete", methods=["POST"])
def admin_complete_inspection(rma_id: int):
    """
    Complete inspection with result (Step 4: QA completes inspection).
    
    POST /rma/admin/123/inspect/complete
    Body: {
        "result": "DEFECTIVE",
        "notes": "Screen is cracked as described",
        "inspected_by": "qa_tech_01"
    }
    """
    # Accept JSON or form-encoded
    data = request.get_json(silent=True) or {}
    
    result = data.get("result") or request.form.get("result")
    notes = data.get("notes") or request.form.get("notes", "")
    inspected_by = data.get("inspected_by") or request.form.get("inspected_by") or "QA"
    
    if not result:
        if not request.is_json:
            flash("Result is required", "error")
            return redirect(url_for("rma.admin_inspect_page", rma_id=rma_id))
        return jsonify({"error": "BadRequest", "details": "result is required"}), 400
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        manager.complete_inspection(rma_id, result=result, notes=notes, inspected_by=inspected_by)
        
        conn.close()
        
        # If form submission (not JSON), redirect back to inspection page
        if not request.is_json:
            flash("Inspection completed", "success")
            return redirect(url_for("rma.admin_inspect_page", rma_id=rma_id))
        
        return jsonify({
            "success": True,
            "message": "Inspection completed",
            "result": result
        }), 200
        
    except ValueError as e:
        if not request.is_json:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for("rma.admin_inspect_page", rma_id=rma_id))
        return jsonify({"error": "ValidationError", "details": str(e)}), 400
    except Exception as e:
        if not request.is_json:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for("rma.admin_inspect_page", rma_id=rma_id))
        return jsonify({"error": "ServerError", "details": str(e)}), 500


# =============================
# STEP 4: Inspection UI (QA/Technician)
# =============================

@bp.route("/admin/inspect/<int:rma_id>", methods=["GET"])
def admin_inspect_page(rma_id: int):
    """Simple admin/QA page to start/complete inspection."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        data = manager.get_rma(rma_id=rma_id)
        conn.close()
        if not data:
            flash("RMA not found", "error")
            return redirect(url_for("rma.my_returns"))
        return render_template("rma/inspect.html", rma=data["rma"], items=data["items"], activity=data.get("activities", []))
    except Exception as e:
        flash(f"Error loading inspection page: {str(e)}", "error")
        return redirect(url_for("rma.my_returns"))


# =============================
# STEP 5: Disposition Decision (Warranty Team)
# =============================

@bp.route("/admin/<int:rma_id>/disposition", methods=["POST"])
def admin_make_disposition(rma_id: int):
    """
    Make disposition decision (Step 5: Decide refund/replacement/etc).
    
    POST /rma/admin/123/disposition
    Body: {
        "disposition": "REFUND",
        "reason": "Defective product confirmed",
        "decided_by": "warranty_manager"
    }
    """
    # Accept JSON or form-encoded
    data = request.get_json(silent=True) or {}
    
    disposition = data.get("disposition") or request.form.get("disposition")
    reason = data.get("reason") or request.form.get("reason", "")
    decided_by = data.get("decided_by") or request.form.get("decided_by") or "warranty_team"
    
    if not disposition:
        if not request.is_json:
            flash("Disposition is required", "error")
            return redirect(url_for("rma.admin_disposition_page", rma_id=rma_id))
        return jsonify({"error": "BadRequest", "details": "disposition is required"}), 400
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        manager.make_disposition(rma_id, disposition=disposition, reason=reason, decided_by=decided_by)
        
        conn.close()
        
        # If form submission (not JSON), redirect
        if not request.is_json:
            flash(f"Disposition decided: {disposition}", "success")
            return redirect(url_for("rma.admin_disposition_queue"))
        
        return jsonify({
            "success": True,
            "message": "Disposition decided",
            "disposition": disposition
        }), 200
        
    except ValueError as e:
        if not request.is_json:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for("rma.admin_disposition_page", rma_id=rma_id))
        return jsonify({"error": "ValidationError", "details": str(e)}), 400
    except Exception as e:
        if not request.is_json:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for("rma.admin_disposition_page", rma_id=rma_id))
        return jsonify({"error": "ServerError", "details": str(e)}), 500


# =============================
# Admin: Disposition Queue & Decision (Step 5)
# =============================

@bp.route("/admin/disposition-queue", methods=["GET"])
def admin_disposition_queue():
    """List RMAs in INSPECTED status awaiting disposition decision."""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT id, rma_number, sale_id, user_id, status, 
                   inspection_result, inspected_at, inspected_by, disposition
            FROM rma_requests
            WHERE status IN ('INSPECTED', 'DISPOSITION')
            ORDER BY inspected_at DESC
        """).fetchall()
        conn.close()
        return render_template("rma/disposition_queue.html", rmas=rows)
    except Exception as e:
        flash(f"Error loading disposition queue: {str(e)}", "error")
        return redirect(url_for("rma.admin_warehouse_queue"))


@bp.route("/admin/disposition/<int:rma_id>", methods=["GET"])
def admin_disposition_page(rma_id: int):
    """Disposition decision page for warranty team."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        data = manager.get_rma(rma_id=rma_id)
        conn.close()
        if not data:
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_disposition_queue"))
        return render_template("rma/disposition.html", rma=data["rma"], items=data["items"], activity=data.get("activities", []))
    except Exception as e:
        flash(f"Error loading disposition page: {str(e)}", "error")
        return redirect(url_for("rma.admin_disposition_queue"))


# =============================
# STEP 6: Process Refund
# =============================

@bp.route("/admin/<int:rma_id>/refund", methods=["POST"])
def admin_process_refund(rma_id: int):
    """
    Process refund (Step 6: Issue refund).
    
    POST /rma/admin/123/refund
    Body: {
        "amount_cents": 9999,
        "method": "ORIGINAL_PAYMENT"
    }
    """
    data = request.get_json() or {}
    
    amount_cents = data.get("amount_cents")
    method = data.get("method", "ORIGINAL_PAYMENT")
    
    if amount_cents is None:
        return jsonify({"error": "BadRequest", "details": "amount_cents is required"}), 400
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        refund_id = manager.process_refund(rma_id, amount_cents=amount_cents, method=method)
        
        # Simulate payment processing (in real system, call payment gateway)
        # For demo, auto-complete the refund
        manager.complete_refund(refund_id, reference=f"REF-{refund_id}-DEMO", success=True)
        
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "Refund processed",
            "refund_id": refund_id,
            "amount": f"${amount_cents/100:.2f}"
        }), 200
        
    except ValueError as e:
        return jsonify({"error": "ValidationError", "details": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "ServerError", "details": str(e)}), 500


# =============================
# STEP 7: Reporting & Metrics
# =============================

@bp.route("/admin/metrics", methods=["GET"])
def admin_get_metrics():
    """
    Get RMA metrics for reporting (Step 7: Closure & Reporting).
    
    GET /rma/admin/metrics?start_date=2025-11-01&end_date=2025-11-30
    """
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        metrics = manager.get_metrics(start_date=start_date, end_date=end_date)
        
        conn.close()
        
        return jsonify({
            "success": True,
            "metrics": metrics
        }), 200
        
    except Exception as e:
        return jsonify({"error": "ServerError", "details": str(e)}), 500


# =============================
# Admin: Inspection Queue (list view)
# =============================

@bp.route("/admin/queue", methods=["GET"])
def admin_inspection_queue():
    """List RMAs pending or in inspection for QA/technicians."""
    status = request.args.get("status")  # optional: RECEIVED or INSPECTING
    try:
        conn = get_conn()
        cursor = conn.cursor()
        base_query = (
            "SELECT id, rma_number, sale_id, user_id, status, created_at, received_at, inspected_by "
            "FROM rma_requests "
        )
        params = []
        if status in ("RECEIVED", "INSPECTING"):
            base_query += "WHERE status = ? "
            params.append(status)
        else:
            base_query += "WHERE status IN ('RECEIVED','INSPECTING') "
        base_query += "ORDER BY COALESCE(received_at, created_at) DESC"
        rows = cursor.execute(base_query, params).fetchall()
        conn.close()
        return render_template("rma/admin_queue.html", rmas=rows, filter_status=status)
    except Exception as e:
        flash(f"Error loading inspection queue: {str(e)}", "error")
        return redirect(url_for("rma.my_returns"))


# =============================
# Admin: Main Dashboard
# =============================

@bp.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():
    """Main admin dashboard showing all queues and quick access to all admin functions."""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # Get queue counts
        queues = {
            'warehouse': cursor.execute("SELECT COUNT(*) as count FROM rma_requests WHERE status = 'SHIPPING'").fetchone()['count'],
            'inspection': cursor.execute("SELECT COUNT(*) as count FROM rma_requests WHERE status IN ('RECEIVED', 'INSPECTING')").fetchone()['count'],
            'disposition': cursor.execute("SELECT COUNT(*) as count FROM rma_requests WHERE status = 'INSPECTED'").fetchone()['count'],
            'processing': cursor.execute("SELECT COUNT(*) as count FROM rma_requests WHERE status IN ('DISPOSITION', 'PROCESSING')").fetchone()['count']
        }
        
        conn.close()
        return render_template("rma/admin_dashboard.html", queues=queues)
    except Exception as e:
        flash(f"Error loading admin dashboard: {str(e)}", "error")
        return redirect(url_for("index"))


# =============================
# Admin: Warehouse Receiving Queue
# =============================

@bp.route("/admin/warehouse", methods=["GET"])
def admin_warehouse_queue():
    """List RMAs in SHIPPING status for warehouse to mark as received."""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT id, rma_number, sale_id, user_id, status, 
                   shipping_carrier, tracking_number, shipped_at
            FROM rma_requests
            WHERE status = 'SHIPPING'
            ORDER BY shipped_at DESC
        """).fetchall()
        conn.close()
        return render_template("rma/warehouse_queue.html", rmas=rows)
    except Exception as e:
        flash(f"Error loading warehouse queue: {str(e)}", "error")
        return redirect(url_for("rma.my_returns"))


@bp.route("/admin/warehouse/receive/<int:rma_id>", methods=["POST"])
def admin_warehouse_receive_form(rma_id: int):
    """Mark RMA as received (form POST handler for warehouse queue)."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        manager.mark_received(rma_id, actor="warehouse")
        conn.commit()
        conn.close()
        flash("RMA marked as received", "success")
        return redirect(url_for("rma.admin_warehouse_queue"))
    except ValueError as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("rma.admin_warehouse_queue"))
    except Exception as e:
        flash(f"Error marking as received: {str(e)}", "error")
        return redirect(url_for("rma.admin_warehouse_queue"))


@bp.route("/admin/view/<int:rma_id>", methods=["GET"])
def admin_view_rma(rma_id: int):
    """Admin-specific RMA detail view with warehouse/inspection actions."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma_data = manager.get_rma(rma_id=rma_id)
        conn.close()
        
        if not rma_data:
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_warehouse_queue"))
        
        return render_template(
            "rma/admin_view.html",
            rma=rma_data["rma"],
            items=rma_data["items"],
            refund=rma_data.get("refund"),
            activity=rma_data.get("activities", [])
        )
    except Exception as e:
        flash(f"Error loading RMA details: {str(e)}", "error")
        return redirect(url_for("rma.admin_warehouse_queue"))


@bp.route("/admin/view-disposition/<int:rma_id>", methods=["GET"])
def admin_view_disposition_rma(rma_id: int):
    """Admin disposition-specific RMA detail view."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma_data = manager.get_rma(rma_id=rma_id)
        conn.close()
        
        if not rma_data:
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_disposition_queue"))
        
        # Ensure items is a list
        items = rma_data.get("items", [])
        if not isinstance(items, list):
            items = []
        
        return render_template(
            "rma/admin_view_disposition.html",
            rma=rma_data["rma"],
            items=items,
            refund=rma_data.get("refund"),
            activity=rma_data.get("activities", [])
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error loading RMA details: {str(e)}", "error")
        return redirect(url_for("rma.admin_disposition_queue"))


# =============================
# Admin: Refund Processing Queue (Step 6)
# =============================

@bp.route("/admin/processing-queue", methods=["GET"])
def admin_processing_queue():
    """List RMAs with disposition decisions awaiting refund/replacement processing."""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        # Get RMAs in DISPOSITION or PROCESSING status
        rows = cursor.execute("""
            SELECT id, rma_number, sale_id, user_id, status, disposition, 
                   refund_amount_cents, disposition_at
            FROM rma_requests
            WHERE status IN ('DISPOSITION', 'PROCESSING')
              AND disposition IS NOT NULL
            ORDER BY disposition_at DESC
        """).fetchall()
        conn.close()
        return render_template("rma/processing_queue.html", rmas=rows)
    except Exception as e:
        flash(f"Error loading processing queue: {str(e)}", "error")
        return redirect(url_for("rma.my_returns"))


@bp.route("/admin/view-processing/<int:rma_id>", methods=["GET"])
def admin_view_processing_rma(rma_id: int):
    """Admin processing-specific RMA detail view."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma_data = manager.get_rma(rma_id=rma_id)
        conn.close()
        
        if not rma_data:
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        # Ensure items is a list
        items = rma_data.get("items", [])
        if not isinstance(items, list):
            items = []
        
        return render_template(
            "rma/admin_view_processing.html",
            rma=rma_data["rma"],
            items=items,
            refund=rma_data.get("refund"),
            activity=rma_data.get("activities", [])
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error loading RMA details: {str(e)}", "error")
        return redirect(url_for("rma.admin_processing_queue"))


@bp.route("/admin/process-refund/<int:rma_id>", methods=["GET"])
def admin_refund_form(rma_id: int):
    """Display refund processing form."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma_data = manager.get_rma(rma_id=rma_id)
        
        if not rma_data:
            conn.close()
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        rma = rma_data["rma"]
        items = rma_data["items"]
        
        # Check if refund already exists
        existing_refund = conn.execute(
            "SELECT id, status FROM refunds WHERE rma_id = ?", (rma_id,)
        ).fetchone()
        
        conn.close()
        
        if existing_refund:
            flash(f"Refund already exists for this RMA (Status: {existing_refund['status']}). Cannot process again.", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))
        
        # Check if RMA is in correct status
        if rma["status"] != "PROCESSING":
            flash(f"RMA must be in PROCESSING status to issue refund. Current status: {rma['status']}", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))
        
        # Calculate requested refund amount
        requested_amount = sum(item["quantity"] * item.get("price_at_purchase", 0) for item in items)
        
        return render_template(
            "rma/process_refund.html",
            rma=rma,
            items=items,
            requested_amount=requested_amount
        )
    except Exception as e:
        flash(f"Error loading refund form: {str(e)}", "error")
        return redirect(url_for("rma.admin_processing_queue"))


@bp.route("/admin/<int:rma_id>/process-refund", methods=["POST"])
def admin_process_refund_form(rma_id: int):
    """Process a refund (Step 6) via form submission."""
    try:
        # Get form data
        if request.is_json:
            data = request.get_json()
            method = data.get("method", "ORIGINAL_PAYMENT")
            amount_dollars = float(data.get("amount_dollars", 0))
            notes = data.get("notes", "")
        else:
            method = request.form.get("method", "ORIGINAL_PAYMENT")
            amount_dollars = float(request.form.get("amount_dollars", 0))
            notes = request.form.get("notes", "")
        
        amount_cents = int(amount_dollars * 100)
        
        if amount_cents <= 0:
            flash("Refund amount must be greater than 0", "error")
            return redirect(url_for("rma.admin_refund_form", rma_id=rma_id))
        
        # Process refund
        conn = get_conn()
        manager = RMAManager(conn)
        refund_id = manager.process_refund(
            rma_id=rma_id,
            amount_cents=amount_cents,
            method=method,
            actor=session.get("user_id", "admin")
        )
        
        # Auto-complete refund (in production, this would integrate with payment gateway)
        manager.complete_refund(
            refund_id=refund_id,
            reference=f"REF-{refund_id}",
            success=True
        )
        
        conn.commit()
        conn.close()
        
        flash(f"Refund processed successfully: ${amount_dollars:.2f} via {method}", "success")
        
        if request.is_json:
            return jsonify({"message": "Refund processed", "refund_id": refund_id})
        return redirect(url_for("rma.admin_processing_queue"))
        
    except ValueError as e:
        flash(f"Error: {str(e)}", "error")
        if request.is_json:
            return jsonify({"error": str(e)}), 400
        return redirect(url_for("rma.admin_refund_form", rma_id=rma_id))
    except Exception as e:
        flash(f"Error processing refund: {str(e)}", "error")
        if request.is_json:
            return jsonify({"error": str(e)}), 500
        return redirect(url_for("rma.admin_refund_form", rma_id=rma_id))


# =============================
# Admin: Replacement Processing
# =============================

@bp.route("/admin/process-replacement/<int:rma_id>", methods=["GET"])
def admin_replacement_form(rma_id: int):
    """Display replacement processing form."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma_data = manager.get_rma(rma_id=rma_id)
        
        if not rma_data:
            conn.close()
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        rma = rma_data["rma"]
        items = rma_data["items"]
        
        # Check if RMA has correct disposition
        if rma["disposition"] != "REPLACEMENT":
            conn.close()
            flash(f"RMA disposition must be REPLACEMENT. Current: {rma['disposition']}", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))
        
        # Check if RMA is in correct status
        # Only allow initiating repair once (from DISPOSITION)
        if rma["status"] != "DISPOSITION":
            conn.close()
            if rma["status"] == "PROCESSING":
                flash("Repair already initiated for this RMA.", "error")
            else:
                flash(f"RMA must be in DISPOSITION status. Current status: {rma['status']}", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))
        
        # Check if replacement already processed
        if rma["status"] == "COMPLETED":
            conn.close()
            flash("Replacement already processed for this RMA.", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))
        
        conn.close()
        
        return render_template(
            "rma/process_replacement.html",
            rma=rma,
            items=items
        )
    except Exception as e:
        flash(f"Error loading replacement form: {str(e)}", "error")
        return redirect(url_for("rma.admin_processing_queue"))


@bp.route("/admin/<int:rma_id>/process-replacement", methods=["POST"])
def admin_process_replacement_form(rma_id: int):
    """Process a replacement (Step 6) via form submission."""
    try:
        # Get form data
        shipping_carrier = request.form.get("shipping_carrier", "")
        tracking_number = request.form.get("tracking_number", "")
        notes = request.form.get("notes", "")
        
        conn = get_conn()
        manager = RMAManager(conn)
        
        # Process replacement - creates new sale and decreases inventory
        replacement_sale_id = manager.process_replacement(rma_id, actor="admin")
        
        # Log shipping info if provided (sale is already marked COMPLETED)
        if shipping_carrier or tracking_number:
            manager._log_activity(rma_id, "REPLACEMENT_SHIPPED", "COMPLETED", "COMPLETED", "admin",
                                f"Replacement shipped via {shipping_carrier}. Tracking: {tracking_number}. {notes}")
        
        conn.commit()
        conn.close()
        
        flash(f"Replacement processed successfully! New order #{replacement_sale_id} created.", "success")
        return redirect(url_for("rma.admin_processing_queue"))
        
    except ValueError as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("rma.admin_replacement_form", rma_id=rma_id))
    except Exception as e:
        flash(f"Error processing replacement: {str(e)}", "error")
        return redirect(url_for("rma.admin_replacement_form", rma_id=rma_id))


# ==========================
# Admin: Repair Processing
# ==========================

@bp.route("/admin/process-repair/<int:rma_id>", methods=["GET"])
def admin_repair_form(rma_id: int):
    """Display repair processing form."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma_data = manager.get_rma(rma_id=rma_id)

        if not rma_data:
            conn.close()
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_processing_queue"))

        rma = rma_data["rma"]
        items = rma_data["items"]

        # Validate disposition and status
        if rma["disposition"] != "REPAIR":
            conn.close()
            flash(f"RMA disposition must be REPAIR. Current: {rma['disposition']}", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))

        if rma["status"] not in ("PROCESSING", "DISPOSITION"):
            conn.close()
            flash(f"RMA must be in PROCESSING status. Current status: {rma['status']}", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))

        conn.close()

        return render_template(
            "rma/process_repair.html",
            rma=rma,
            items=items
        )
    except Exception as e:
        flash(f"Error loading repair form: {str(e)}", "error")
        return redirect(url_for("rma.admin_processing_queue"))


@bp.route("/admin/<int:rma_id>/process-repair", methods=["POST"])
def admin_process_repair_form(rma_id: int):
    """Initiate a repair (Step 6) via form submission."""
    try:
        # Get form data
        repair_center = request.form.get("repair_center", "").strip()
        repair_rma = request.form.get("repair_rma", "").strip()
        return_tracking = request.form.get("return_tracking", "").strip()
        notes = request.form.get("notes", "").strip()

        conn = get_conn()
        manager = RMAManager(conn)

        # Ensure we haven't already initiated repair
        rma_data = manager.get_rma(rma_id=rma_id)
        rma = rma_data["rma"] if rma_data else None
        if not rma:
            conn.close()
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        if rma["status"] != "DISPOSITION":
            conn.close()
            flash("Repair already initiated or invalid status for initiation.", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))

        # Initiate repair (moves to PROCESSING and logs activity)
        manager.process_repair(rma_id, actor="admin", notes=notes or f"Repair RMA: {repair_rma} at {repair_center}. Return tracking: {return_tracking}")

        # Log extra metadata if provided
        extra = []
        if repair_center:
            extra.append(f"Center: {repair_center}")
        if repair_rma:
            extra.append(f"Repair RMA: {repair_rma}")
        if return_tracking:
            extra.append(f"Return Tracking: {return_tracking}")
        if extra:
            manager._log_activity(rma_id, "REPAIR_METADATA", "PROCESSING", "PROCESSING", "admin", ", ".join(extra))

        conn.commit()
        conn.close()

        flash("Repair initiated successfully.", "success")
        return redirect(url_for("rma.admin_processing_queue"))
    except ValueError as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("rma.admin_repair_form", rma_id=rma_id))
    except Exception as e:
        flash(f"Error processing repair: {str(e)}", "error")
        return redirect(url_for("rma.admin_repair_form", rma_id=rma_id))


@bp.route("/admin/complete-repair/<int:rma_id>", methods=["GET"])
def admin_complete_repair_form(rma_id: int):
    """Display form to complete repair and log return shipping."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma_data = manager.get_rma(rma_id=rma_id)

        if not rma_data:
            conn.close()
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_processing_queue"))

        rma = rma_data["rma"]
        items = rma_data["items"]

        # Validate disposition and status
        if rma["disposition"] != "REPAIR":
            conn.close()
            flash(f"RMA disposition must be REPAIR. Current: {rma['disposition']}", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))

        if rma["status"] != "PROCESSING":
            conn.close()
            if rma["status"] == "COMPLETED":
                flash("Repair already completed for this RMA.", "error")
            else:
                flash(f"RMA must be in PROCESSING status. Current status: {rma['status']}", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))

        conn.close()

        return render_template(
            "rma/complete_repair.html",
            rma=rma,
            items=items
        )
    except Exception as e:
        flash(f"Error loading complete repair form: {str(e)}", "error")
        return redirect(url_for("rma.admin_processing_queue"))


@bp.route("/admin/<int:rma_id>/complete-repair", methods=["POST"])
def admin_complete_repair_submit(rma_id: int):
    """Complete a repair (Step 6 final) via form submission."""
    try:
        # Get form data
        return_carrier = request.form.get("return_carrier", "").strip()
        return_tracking = request.form.get("return_tracking", "").strip()
        notes = request.form.get("notes", "").strip()

        conn = get_conn()
        manager = RMAManager(conn)

        # Validate status before completing
        rma_data = manager.get_rma(rma_id=rma_id)
        rma = rma_data["rma"] if rma_data else None
        if not rma:
            conn.close()
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        if rma["status"] != "PROCESSING":
            conn.close()
            flash("Repair already completed or invalid status for completion.", "error")
            return redirect(url_for("rma.admin_view_processing_rma", rma_id=rma_id))

        # Complete repair (marks RMA as COMPLETED)
        completion_notes = notes or f"Returned to customer via {return_carrier}. Tracking: {return_tracking}"
        manager.complete_repair(rma_id, actor="admin", notes=completion_notes)

        # Log shipping metadata if provided
        if return_carrier or return_tracking:
            manager._log_activity(rma_id, "REPAIR_RETURN_SHIPPED", "COMPLETED", "COMPLETED", "admin",
                                f"Repaired item shipped back. Carrier: {return_carrier}, Tracking: {return_tracking}")

        conn.commit()
        conn.close()

        flash("Repair completed successfully. Item returned to customer.", "success")
        return redirect(url_for("rma.admin_completed_queue"))
    except ValueError as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("rma.admin_complete_repair_form", rma_id=rma_id))
    except Exception as e:
        flash(f"Error completing repair: {str(e)}", "error")
        return redirect(url_for("rma.admin_complete_repair_form", rma_id=rma_id))


# =============================
# Admin: Process Store Credit (Step 6)
# =============================

@bp.route("/admin/process-credit/<int:rma_id>", methods=["GET"])
def admin_process_credit_form(rma_id: int):
    """Display store credit issuance form."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        rma = manager._get_rma(rma_id)
        
        # Validation: Can only process store credit in DISPOSITION or PROCESSING status
        if rma["status"] not in ("DISPOSITION", "PROCESSING"):
            flash(f"Cannot process store credit - RMA status is {rma['status']}", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        if rma["disposition"] != "STORE_CREDIT":
            flash(f"This RMA is not marked for store credit (disposition: {rma['disposition']})", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        # Get items
        items = conn.execute("""
            SELECT si.*, p.name as product_name, p.price_cents
            FROM sale_item si
            JOIN product p ON si.product_id = p.id
            WHERE si.sale_id = ?
        """, (rma["sale_id"],)).fetchall()
        
        conn.close()
        return render_template("rma/process_store_credit.html", rma=rma, items=items)
        
    except Exception as e:
        flash(f"Error loading store credit form: {str(e)}", "error")
        return redirect(url_for("rma.admin_processing_queue"))


@bp.route("/admin/<int:rma_id>/process-credit", methods=["POST"])
def admin_process_credit_submit(rma_id: int):
    """Process store credit issuance."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        rma = manager._get_rma(rma_id)
        
        # Validation: Can only process once
        if rma["status"] not in ("DISPOSITION", "PROCESSING"):
            flash(f"Cannot process store credit - already processed or invalid status", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        if rma["disposition"] != "STORE_CREDIT":
            flash(f"This RMA is not marked for store credit", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        # Get form data
        credit_amount = request.form.get("credit_amount", type=float, default=0)
        notes = request.form.get("notes", "")
        
        if credit_amount <= 0:
            flash("Store credit amount must be greater than 0", "error")
            return redirect(url_for("rma.admin_process_credit_form", rma_id=rma_id))
        
        # Convert to cents
        amount_cents = int(credit_amount * 100)
        
        # Process store credit
        actor = session.get("username", "admin")
        manager.process_store_credit(rma_id, amount_cents, actor)
        
        # Log additional notes if provided
        if notes:
            manager._log_activity(
                rma_id,
                "STORE_CREDIT_NOTES",
                rma["status"],
                "COMPLETED",
                actor,
                f"Additional notes: {notes}"
            )
        
        flash(f"Store credit of ${credit_amount:.2f} has been issued successfully!", "success")
        conn.close()
        return redirect(url_for("rma.admin_completed_queue"))
        
    except Exception as e:
        flash(f"Error processing store credit: {str(e)}", "error")
        return redirect(url_for("rma.admin_processing_queue"))


@bp.route("/admin/process-rejection/<int:rma_id>", methods=["GET"])
def admin_process_rejection_form(rma_id: int):
    """Show form to process rejection."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma = manager._get_rma(rma_id)
        
        if not rma:
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        if rma["disposition"] != "REJECT":
            flash("This RMA is not marked for rejection", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        # Get RMA items
        items = conn.execute("""
            SELECT ri.*, p.name as product_name
            FROM rma_items ri
            LEFT JOIN product p ON ri.product_id = p.id
            WHERE ri.rma_id = ?
        """, (rma_id,)).fetchall()
        
        conn.close()
        return render_template("rma/process_rejection.html", rma=rma, items=items)
        
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("rma.admin_processing_queue"))


@bp.route("/admin/<int:rma_id>/process-rejection", methods=["POST"])
def admin_process_rejection_submit(rma_id: int):
    """Process rejection completion."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        rma = manager._get_rma(rma_id)
        
        # Validation
        if rma["status"] not in ("DISPOSITION", "PROCESSING"):
            flash(f"Cannot process rejection - already processed or invalid status", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        if rma["disposition"] != "REJECT":
            flash(f"This RMA is not marked for rejection", "error")
            return redirect(url_for("rma.admin_processing_queue"))
        
        # Get form data
        notes = request.form.get("notes", "Return request rejected after review")
        
        # Process rejection
        actor = session.get("username", "admin")
        manager.process_rejection(rma_id, actor, notes)
        
        flash(f"Rejection has been processed successfully!", "success")
        conn.close()
        return redirect(url_for("rma.admin_completed_queue"))
        
    except Exception as e:
        flash(f"Error processing rejection: {str(e)}", "error")
        return redirect(url_for("rma.admin_processing_queue"))


# =============================
# Admin: Completed RMAs & Audit Log (Step 7)
# =============================

@bp.route("/admin/completed", methods=["GET"])
def admin_completed_queue():
    """List completed and closed RMAs with metrics for audit and reporting."""
    try:
        # Get filter parameters
        disposition = request.args.get("disposition", "")
        days = int(request.args.get("days", 30))
        
        conn = get_conn()
        cursor = conn.cursor()
        
        # Build query with filters
        query = """
            SELECT 
                id, rma_number, sale_id, user_id, status, disposition, 
                refund_amount_cents, closed_at, created_at,
                CAST((julianday(closed_at) - julianday(created_at)) AS INTEGER) as resolution_days
            FROM rma_requests
            WHERE status IN ('COMPLETED', 'CANCELLED')
        """
        params = []
        
        if disposition:
            query += " AND disposition = ?"
            params.append(disposition)
        
        if days > 0:
            query += " AND closed_at >= datetime('now', ? || ' days')"
            params.append(f"-{days}")
        
        query += " ORDER BY closed_at DESC LIMIT 100"
        
        rmas = cursor.execute(query, params).fetchall()
        
        # Calculate metrics
        total_completed = cursor.execute("""
            SELECT COUNT(*) as count FROM rma_requests WHERE status = 'COMPLETED'
        """).fetchone()["count"]
        
        total_refunded = cursor.execute("""
            SELECT COALESCE(SUM(refund_amount_cents), 0) as total 
            FROM rma_requests 
            WHERE status = 'COMPLETED' AND disposition = 'REFUND'
        """).fetchone()["total"]
        
        avg_resolution = cursor.execute("""
            SELECT AVG(julianday(closed_at) - julianday(created_at)) as avg_days
            FROM rma_requests
            WHERE status = 'COMPLETED' AND closed_at IS NOT NULL
        """).fetchone()["avg_days"] or 0
        
        success_rate = cursor.execute("""
            SELECT 
                CAST(COUNT(CASE WHEN disposition IN ('REFUND', 'REPLACEMENT', 'REPAIR', 'STORE_CREDIT') THEN 1 END) AS FLOAT) / 
                NULLIF(COUNT(*), 0) * 100 as rate
            FROM rma_requests
            WHERE status = 'COMPLETED'
        """).fetchone()["rate"] or 0
        
        conn.close()
        
        return render_template(
            "rma/completed_queue.html",
            rmas=rmas,
            total_completed=total_completed,
            total_refunded=total_refunded,
            avg_resolution_days=avg_resolution,
            success_rate=success_rate,
            filter_disposition=disposition,
            filter_days=days
        )
    except Exception as e:
        flash(f"Error loading completed RMAs: {str(e)}", "error")
        return redirect(url_for("rma.my_returns"))


@bp.route("/admin/view-completed/<int:rma_id>", methods=["GET"])
def admin_view_completed_rma(rma_id: int):
    """View details of a completed RMA."""
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma_data = manager.get_rma(rma_id=rma_id)
        conn.close()
        
        if not rma_data:
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_completed_queue"))
        
        # Ensure items is a list
        items = rma_data.get("items", [])
        if not isinstance(items, list):
            items = []
        
        return render_template(
            "rma/admin_view_completed.html",  # Use dedicated completed view
            rma=rma_data["rma"],
            items=items,
            refund=rma_data.get("refund"),
            activities=rma_data.get("activities", [])
        )
    except Exception as e:
        flash(f"Error loading RMA details: {str(e)}", "error")
        return redirect(url_for("rma.admin_completed_queue"))


@bp.route("/admin/audit-log/<int:rma_id>", methods=["GET"])
def admin_audit_log(rma_id: int):
    """View full audit log for an RMA."""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # Get RMA details
        rma = cursor.execute("SELECT * FROM rma_requests WHERE id = ?", (rma_id,)).fetchone()
        
        if not rma:
            flash("RMA not found", "error")
            return redirect(url_for("rma.admin_completed_queue"))
        
        # Get all activity log entries
        activities = cursor.execute("""
            SELECT * FROM rma_activity_log
            WHERE rma_id = ?
            ORDER BY created_at ASC
        """, (rma_id,)).fetchall()
        
        conn.close()
        
        return render_template(
            "rma/audit_log.html",
            rma=rma,
            activities=activities
        )
    except Exception as e:
        flash(f"Error loading audit log: {str(e)}", "error")
        return redirect(url_for("rma.admin_completed_queue"))


# =============================
# Metrics Dashboard
# =============================

@bp.route("/admin/metrics-dashboard", methods=["GET"])
def admin_metrics_dashboard():
    """Comprehensive RMA metrics dashboard"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        from datetime import datetime, timedelta
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate date ranges
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        sixty_days_ago = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        current_month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        # 1. RMA Rate (Total RMAs / Total Orders)
        total_orders = cursor.execute("SELECT COUNT(*) as count FROM sale").fetchone()['count']
        total_rmas = cursor.execute("SELECT COUNT(*) as count FROM rma_requests").fetchone()['count']
        rma_rate = (total_rmas / total_orders * 100) if total_orders > 0 else 0
        
        # 2. Total Refund Amount (Current Month)
        total_refund_result = cursor.execute("""
            SELECT COALESCE(SUM(amount_cents), 0) as total
            FROM refunds
            WHERE created_at >= ?
        """, (current_month_start,)).fetchone()
        total_refund_amount = total_refund_result['total'] / 100.0
        
        # 3. Refund Rate (% of revenue)
        total_revenue_result = cursor.execute("""
            SELECT COALESCE(SUM(total_cents), 0) as total
            FROM sale
        """).fetchone()
        total_revenue = total_revenue_result['total'] / 100.0
        refund_rate = (total_refund_amount / total_revenue * 100) if total_revenue > 0 else 0
        
        # 4. Refunds per Day (Last 30 days)
        refunds_30d_result = cursor.execute("""
            SELECT COUNT(*) as count
            FROM refunds
            WHERE created_at >= ?
        """, (thirty_days_ago,)).fetchone()
        refunds_per_day = refunds_30d_result['count'] / 30.0
        
        # 5. Approval Rate
        approved_count = cursor.execute("""
            SELECT COUNT(*) as count
            FROM rma_requests
            WHERE status IN ('APPROVED', 'SHIPPING', 'RECEIVED', 'INSPECTING', 'INSPECTED', 
                           'DISPOSITION', 'PROCESSING', 'COMPLETED')
        """).fetchone()['count']
        approval_rate = (approved_count / total_rmas * 100) if total_rmas > 0 else 0
        
        # 6. Disposition Breakdown
        disposition_breakdown_rows = cursor.execute("""
            SELECT 
                disposition,
                COUNT(*) as count
            FROM rma_requests
            WHERE disposition IS NOT NULL
            GROUP BY disposition
        """).fetchall()
        
        # Convert to dicts so we can modify them
        disposition_breakdown = []
        total_with_disposition = sum(d['count'] for d in disposition_breakdown_rows)
        for disp in disposition_breakdown_rows:
            percentage = (disp['count'] / total_with_disposition * 100) if total_with_disposition > 0 else 0
            disposition_breakdown.append({
                'disposition': disp['disposition'],
                'count': disp['count'],
                'percentage': percentage
            })
        
        # Add pending if needed
        if not disposition_breakdown:
            disposition_breakdown = [{'disposition': None, 'count': 0, 'percentage': 0}]
        
        # 7. Queue Backlogs
        queue_backlog = {
            'warehouse': cursor.execute("SELECT COUNT(*) as count FROM rma_requests WHERE status = 'SHIPPING'").fetchone()['count'],
            'inspection': cursor.execute("SELECT COUNT(*) as count FROM rma_requests WHERE status IN ('RECEIVED', 'INSPECTING')").fetchone()['count'],
            'disposition': cursor.execute("SELECT COUNT(*) as count FROM rma_requests WHERE status = 'INSPECTED'").fetchone()['count'],
            'processing': cursor.execute("SELECT COUNT(*) as count FROM rma_requests WHERE status IN ('DISPOSITION', 'PROCESSING')").fetchone()['count']
        }
        
        # 8. Average Cycle Time (Overall)
        avg_cycle_time_result = cursor.execute("""
            SELECT AVG(julianday(closed_at) - julianday(created_at)) as avg_days
            FROM rma_requests
            WHERE status IN ('COMPLETED', 'CANCELLED') AND closed_at IS NOT NULL
        """).fetchone()
        avg_cycle_time = avg_cycle_time_result['avg_days'] or 0
        
        # 9. Cycle Time by Stage
        cycle_time_by_stage = []
        
        # Time to approval
        approval_time = cursor.execute("""
            SELECT AVG(julianday(validated_at) - julianday(created_at)) as avg_days
            FROM rma_requests
            WHERE validated_at IS NOT NULL
        """).fetchone()['avg_days'] or 0
        cycle_time_by_stage.append({'stage': 'Submission → Approval', 'avg_days': approval_time})
        
        # Time to receive
        receive_time = cursor.execute("""
            SELECT AVG(julianday(received_at) - julianday(validated_at)) as avg_days
            FROM rma_requests
            WHERE received_at IS NOT NULL AND validated_at IS NOT NULL
        """).fetchone()['avg_days'] or 0
        cycle_time_by_stage.append({'stage': 'Approval → Received', 'avg_days': receive_time})
        
        # Time to inspect
        inspect_time = cursor.execute("""
            SELECT AVG(julianday(inspected_at) - julianday(received_at)) as avg_days
            FROM rma_requests
            WHERE inspected_at IS NOT NULL AND received_at IS NOT NULL
        """).fetchone()['avg_days'] or 0
        cycle_time_by_stage.append({'stage': 'Received → Inspected', 'avg_days': inspect_time})
        
        # Time to disposition
        disposition_time = cursor.execute("""
            SELECT AVG(julianday(disposition_at) - julianday(inspected_at)) as avg_days
            FROM rma_requests
            WHERE disposition_at IS NOT NULL AND inspected_at IS NOT NULL
        """).fetchone()['avg_days'] or 0
        cycle_time_by_stage.append({'stage': 'Inspected → Disposition', 'avg_days': disposition_time})
        
        # Time to complete
        complete_time = cursor.execute("""
            SELECT AVG(julianday(closed_at) - julianday(disposition_at)) as avg_days
            FROM rma_requests
            WHERE closed_at IS NOT NULL AND disposition_at IS NOT NULL
        """).fetchone()['avg_days'] or 0
        cycle_time_by_stage.append({'stage': 'Disposition → Completed', 'avg_days': complete_time})
        
        max_stage_time = max([s['avg_days'] for s in cycle_time_by_stage]) if cycle_time_by_stage else 1
        
        # 10. SLA Compliance (7 days target)
        sla_compliant = cursor.execute("""
            SELECT COUNT(*) as count
            FROM rma_requests
            WHERE status IN ('COMPLETED', 'CANCELLED') 
                AND closed_at IS NOT NULL
                AND julianday(closed_at) - julianday(created_at) <= 7
        """).fetchone()['count']
        total_completed = cursor.execute("""
            SELECT COUNT(*) as count
            FROM rma_requests
            WHERE status IN ('COMPLETED', 'CANCELLED') AND closed_at IS NOT NULL
        """).fetchone()['count']
        sla_compliance = (sla_compliant / total_completed * 100) if total_completed > 0 else 100
        
        # 11. RMA Volume Trend (Last 30 days)
        trend_rma_volume_30d = cursor.execute("""
            SELECT COUNT(*) as count
            FROM rma_requests
            WHERE created_at >= ?
        """, (thirty_days_ago,)).fetchone()['count']
        
        # Previous 30 days for comparison
        trend_rma_volume_60d = cursor.execute("""
            SELECT COUNT(*) as count
            FROM rma_requests
            WHERE created_at >= ? AND created_at < ?
        """, (sixty_days_ago, thirty_days_ago)).fetchone()['count']
        
        trend_rma_volume_change = ((trend_rma_volume_30d - trend_rma_volume_60d) / trend_rma_volume_60d * 100) if trend_rma_volume_60d > 0 else 0
        
        # 12. Cycle Time Trend
        trend_cycle_time_30d = cursor.execute("""
            SELECT AVG(julianday(closed_at) - julianday(created_at)) as avg_days
            FROM rma_requests
            WHERE status IN ('COMPLETED', 'CANCELLED') 
                AND closed_at IS NOT NULL
                AND created_at >= ?
        """, (thirty_days_ago,)).fetchone()['avg_days'] or 0
        
        trend_cycle_time_60d = cursor.execute("""
            SELECT AVG(julianday(closed_at) - julianday(created_at)) as avg_days
            FROM rma_requests
            WHERE status IN ('COMPLETED', 'CANCELLED') 
                AND closed_at IS NOT NULL
                AND created_at >= ? AND created_at < ?
        """, (sixty_days_ago, thirty_days_ago)).fetchone()['avg_days'] or 0
        
        trend_cycle_time_change = ((trend_cycle_time_30d - trend_cycle_time_60d) / trend_cycle_time_60d * 100) if trend_cycle_time_60d > 0 else 0
        
        # 13. Top Products by Return Rate
        top_returned_products = cursor.execute("""
            SELECT 
                ri.product_id,
                p.name as product_name,
                COUNT(*) as return_count,
                (COUNT(*) * 100.0 / (
                    SELECT COUNT(*) 
                    FROM sale_item 
                    WHERE product_id = ri.product_id
                )) as return_rate
            FROM rma_items ri
            JOIN product p ON ri.product_id = p.id
            GROUP BY ri.product_id
            ORDER BY return_count DESC
            LIMIT 10
        """).fetchall()
        
        conn.close()
        
        metrics = {
            'current_time': current_time,
            'rma_rate': rma_rate,
            'total_rmas': total_rmas,
            'total_orders': total_orders,
            'total_refund_amount': total_refund_amount,
            'refund_rate': refund_rate,
            'refunds_per_day': refunds_per_day,
            'approval_rate': approval_rate,
            'approved_count': approved_count,
            'disposition_breakdown': disposition_breakdown,
            'queue_backlog': queue_backlog,
            'avg_cycle_time': avg_cycle_time,
            'cycle_time_by_stage': cycle_time_by_stage,
            'max_stage_time': max_stage_time,
            'sla_compliance': sla_compliance,
            'trend_rma_volume_30d': trend_rma_volume_30d,
            'trend_rma_volume_change': trend_rma_volume_change,
            'trend_cycle_time_30d': trend_cycle_time_30d,
            'trend_cycle_time_change': trend_cycle_time_change,
            'top_returned_products': top_returned_products
        }
        
        return render_template("rma/metrics_dashboard.html", metrics=metrics)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"ERROR in metrics dashboard: {str(e)}")
        print(error_detail)
        flash(f"Error loading metrics: {str(e)}", "error")
        return redirect(url_for("rma.admin_completed_queue"))


# =============================
# Cancel RMA
# =============================

@bp.route("/<int:rma_id>/cancel", methods=["POST"])
@login_required
def cancel_rma(rma_id: int):
    """
    Cancel RMA request.
    
    POST /rma/123/cancel
    Body: {"reason": "Changed my mind"}
    """
    user_id = session.get("user_id")
    data = request.get_json() or {}
    reason = data.get("reason", "")
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        # Verify user owns this RMA
        rma_data = manager.get_rma(rma_id=rma_id)
        if not rma_data or rma_data["rma"]["user_id"] != user_id:
            return jsonify({"error": "Forbidden", "details": "Access denied"}), 403
        
        manager.cancel_rma(rma_id, actor=f"user_{user_id}", reason=reason)
        
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "RMA cancelled"
        }), 200
        
    except ValueError as e:
        return jsonify({"error": "ValidationError", "details": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "ServerError", "details": str(e)}), 500


# =============================
# WEB UI ROUTES (Customer-Facing)
# =============================

@bp.route("/request", methods=["GET"])
@login_required
def request_form():
    """Display RMA request form for a specific order."""
    sale_id = request.args.get("sale_id", type=int)
    if not sale_id:
        flash("Order ID is required", "error")
        return redirect(url_for("products"))
    
    user_id = session.get("user_id")
    
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # Get sale details
        cursor.execute("""
            SELECT s.*, u.username, u.name
            FROM sale s
            JOIN user u ON s.user_id = u.id
            WHERE s.id = ? AND s.user_id = ?
        """, (sale_id, user_id))
        
        sale = cursor.fetchone()
        if not sale:
            flash("Order not found", "error")
            conn.close()
            return redirect(url_for("products"))
        
        # Only allow returns for COMPLETED orders
        if sale["status"] != "COMPLETED":
            flash("Only completed orders can be returned", "error")
            conn.close()
            return redirect(url_for("products"))
        
        # Get sale items
        cursor.execute("""
            SELECT si.*, p.name as product_name
            FROM sale_item si
            JOIN product p ON si.product_id = p.id
            WHERE si.sale_id = ?
        """, (sale_id,))
        
        items = cursor.fetchall()
        conn.close()
        
        return render_template("rma/request.html", sale=sale, items=items)
        
    except Exception as e:
        flash(f"Error loading order: {str(e)}", "error")
        return redirect(url_for("products"))


@bp.route("/submit-form", methods=["POST"])
@login_required
def submit_form():
    """Process RMA request form submission."""
    import os
    from werkzeug.utils import secure_filename
    
    user_id = session.get("user_id")
    
    sale_id = request.form.get("sale_id", type=int)
    reason = request.form.get("reason", "")
    description = request.form.get("description", "")
    items_json = request.form.get("items", "[]")
    
    # Handle file upload
    photo_url = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename:
            # Validate file
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            
            if file_ext in allowed_extensions:
                # Create uploads directory if it doesn't exist
                upload_dir = os.path.join('/app', 'data', 'uploads', 'rma')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Generate unique filename
                import uuid
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                file_path = os.path.join(upload_dir, unique_filename)
                
                # Save file
                file.save(file_path)
                photo_url = f"/uploads/rma/{unique_filename}"
            else:
                flash("Invalid file type. Please upload JPG, PNG, or GIF only.", "error")
                return redirect(request.referrer or url_for("products"))
    
    if not sale_id or not reason:
        flash("Missing required fields", "error")
        return redirect(request.referrer or url_for("products"))
    
    try:
        import json
        items = json.loads(items_json)
        
        if not items:
            flash("Please select at least one item to return", "error")
            return redirect(request.referrer or url_for("products"))
        
        conn = get_conn()
        manager = RMAManager(conn)
        
        # Convert photo_url to list format expected by manager
        photo_urls = [photo_url] if photo_url else None
        
        rma_id, rma_number = manager.submit_rma_request(
            user_id=user_id,
            sale_id=sale_id,
            reason=reason,
            description=description or None,
            photo_urls=photo_urls,
            items=items
        )
        
        # Auto-validate synchronously (system rules)
        approved = manager.validate_rma_request(
            rma_id=rma_id,
            validated_by="system",
            approve=True
        )
        
        # Re-fetch to get number/status
        rma_data = manager.get_rma(rma_id=rma_id)
        rma_number = rma_data["rma"].get("rma_number")
        status = rma_data["rma"]["status"]
        
        conn.commit()
        conn.close()
        
        if approved and rma_number:
            flash("Return request validated and approved. RMA number issued.", "success")
            return redirect(url_for("rma.view_rma", rma_number=rma_number))
        else:
            flash("Return submitted but failed validation. Please contact support.", "error")
            return redirect(url_for("rma.view_rma_by_id", rma_id=rma_id))
        
    except ValueError as e:
        flash(f"Invalid request: {str(e)}", "error")
        return redirect(request.referrer or url_for("products"))
    except Exception as e:
        flash(f"Error submitting return: {str(e)}", "error")
        return redirect(request.referrer or url_for("products"))


@bp.route("/my-returns", methods=["GET"])
@login_required
def my_returns():
    """List all RMA requests for the current user."""
    user_id = session.get("user_id")
    
    try:
        conn = get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        rows = cursor.execute(
            """
            SELECT id, rma_number, sale_id, reason, status, created_at, disposition
            FROM rma_requests
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

        # Compute display_status: show meaningful status based on RMA state
        rmas = []
        for row in rows:
            r = dict(row)
            display_status = r["status"]
            
            # Active (in-progress) RMAs
            if r["status"] not in ("COMPLETED", "REJECTED", "CANCELLED"):
                if r.get("disposition") == "REPAIR":
                    display_status = "REPAIRING"
                elif r.get("disposition") == "REPLACEMENT":
                    display_status = "REPLACING"
                elif r.get("disposition") == "REFUND":
                    display_status = "REFUNDING"
                elif r.get("disposition") == "STORE_CREDIT":
                    display_status = "STORE_CREDIT"
                elif r.get("disposition") == "REJECT":
                    display_status = "REJECTED"
            # Rejected RMAs
            elif r["status"] == "REJECTED":
                display_status = "REJECTED"
            # Completed RMAs - show final outcome
            elif r["status"] == "COMPLETED":
                if r.get("disposition") == "REPAIR":
                    display_status = "REPAIRED"
                elif r.get("disposition") == "REPLACEMENT":
                    display_status = "REPLACED"
                elif r.get("disposition") == "REFUND":
                    display_status = "REFUNDED"
                elif r.get("disposition") == "STORE_CREDIT":
                    display_status = "CREDITED"
                elif r.get("disposition") == "REJECT":
                    display_status = "REJECTED"
            
            r["display_status"] = display_status
            rmas.append(r)

        conn.close()

        return render_template("rma/my_returns.html", rmas=rmas)
        
    except Exception as e:
        flash(f"Error loading returns: {str(e)}", "error")
        return redirect(url_for("products"))


@bp.route("/view/<rma_number>", methods=["GET"])
@login_required
def view_rma(rma_number: str):
    """View detailed information about an RMA request."""
    user_id = session.get("user_id")
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        # Get RMA data
        rma_data = manager.get_rma(rma_number=rma_number)
        
        if not rma_data:
            flash("Return request not found", "error")
            conn.close()
            return redirect(url_for("rma.my_returns"))
        
        # Verify user owns this RMA
        if rma_data["rma"]["user_id"] != user_id:
            flash("Access denied", "error")
            conn.close()
            return redirect(url_for("rma.my_returns"))
        
        # Compute display_status for better UX
        rma = rma_data["rma"]
        display_status = rma["status"]
        
        if rma["status"] not in ("COMPLETED", "REJECTED", "CANCELLED"):
            if rma.get("disposition") == "REPAIR":
                display_status = "REPAIRING"
            elif rma.get("disposition") == "REPLACEMENT":
                display_status = "REPLACING"
            elif rma.get("disposition") == "REFUND":
                display_status = "REFUNDING"
            elif rma.get("disposition") == "STORE_CREDIT":
                display_status = "STORE_CREDIT"
            elif rma.get("disposition") == "REJECT":
                display_status = "REJECTED"
        elif rma["status"] == "REJECTED":
            display_status = "REJECTED"
        elif rma["status"] == "COMPLETED":
            if rma.get("disposition") == "REPAIR":
                display_status = "REPAIRED"
            elif rma.get("disposition") == "REPLACEMENT":
                display_status = "REPLACED"
            elif rma.get("disposition") == "REFUND":
                display_status = "REFUNDED"
            elif rma.get("disposition") == "STORE_CREDIT":
                display_status = "CREDITED"
            elif rma.get("disposition") == "REJECT":
                display_status = "REJECTED"
        
        conn.close()
        
        return render_template(
            "rma/view.html",
            rma=rma_data["rma"],
            items=rma_data["items"],
            refund=rma_data.get("refund"),
            activity=rma_data.get("activities", []),
            display_status=display_status
        )
        
    except Exception as e:
        flash(f"Error loading return details: {str(e)}", "error")
        return redirect(url_for("rma.my_returns"))


@bp.route("/view-id/<int:rma_id>", methods=["GET"])
@login_required
def view_rma_by_id(rma_id: int):
    """View RMA details by internal ID, useful before number is issued."""
    user_id = session.get("user_id")
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        rma_data = manager.get_rma(rma_id=rma_id)
        if not rma_data:
            flash("Return request not found", "error")
            conn.close()
            return redirect(url_for("rma.my_returns"))
        if rma_data["rma"]["user_id"] != user_id:
            flash("Access denied", "error")
            conn.close()
            return redirect(url_for("rma.my_returns"))
        
        # Compute display_status for better UX
        rma = rma_data["rma"]
        display_status = rma["status"]
        
        if rma["status"] not in ("COMPLETED", "REJECTED", "CANCELLED"):
            if rma.get("disposition") == "REPAIR":
                display_status = "REPAIRING"
            elif rma.get("disposition") == "REPLACEMENT":
                display_status = "REPLACING"
            elif rma.get("disposition") == "REFUND":
                display_status = "REFUNDING"
            elif rma.get("disposition") == "STORE_CREDIT":
                display_status = "STORE_CREDIT"
            elif rma.get("disposition") == "REJECT":
                display_status = "REJECTED"
        elif rma["status"] == "REJECTED":
            display_status = "REJECTED"
        elif rma["status"] == "COMPLETED":
            if rma.get("disposition") == "REPAIR":
                display_status = "REPAIRED"
            elif rma.get("disposition") == "REPLACEMENT":
                display_status = "REPLACED"
            elif rma.get("disposition") == "REFUND":
                display_status = "REFUNDED"
            elif rma.get("disposition") == "STORE_CREDIT":
                display_status = "CREDITED"
            elif rma.get("disposition") == "REJECT":
                display_status = "REJECTED"
        
        conn.close()
        return render_template(
            "rma/view.html",
            rma=rma_data["rma"],
            items=rma_data["items"],
            refund=rma_data.get("refund"),
            activity=rma_data.get("activities", []),
            display_status=display_status
        )
    except Exception as e:
        flash(f"Error loading return details: {str(e)}", "error")
        return redirect(url_for("rma.my_returns"))


@bp.route("/update-shipping-form/<int:rma_id>", methods=["POST"])
@login_required
def update_shipping_form(rma_id: int):
    """Process shipping information form submission."""
    user_id = session.get("user_id")
    
    carrier = request.form.get("carrier", "")
    tracking_number = request.form.get("tracking_number", "")
    
    if not carrier or not tracking_number:
        flash("Carrier and tracking number are required", "error")
        return redirect(request.referrer or url_for("rma.my_returns"))
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        # Verify user owns this RMA
        rma_data = manager.get_rma(rma_id=rma_id)
        if not rma_data or rma_data["rma"]["user_id"] != user_id:
            flash("Access denied", "error")
            conn.close()
            return redirect(url_for("rma.my_returns"))
        
        rma_number = rma_data["rma"]["rma_number"]
        
        manager.update_shipping_info(
            rma_id=rma_id,
            carrier=carrier,
            tracking_number=tracking_number,
            actor=f"user_{user_id}"
        )
        
        conn.commit()
        conn.close()
        
        flash("Shipping information updated successfully!", "success")
        return redirect(url_for("rma.view_rma", rma_number=rma_number))
        
    except ValueError as e:
        flash(f"Invalid request: {str(e)}", "error")
        return redirect(request.referrer or url_for("rma.my_returns"))
    except Exception as e:
        flash(f"Error updating shipping info: {str(e)}", "error")
        return redirect(request.referrer or url_for("rma.my_returns"))


@bp.route("/cancel-form/<int:rma_id>", methods=["GET", "POST"])
@login_required
def cancel_form(rma_id: int):
    """Cancel RMA request via web form."""
    user_id = session.get("user_id")
    
    try:
        conn = get_conn()
        manager = RMAManager(conn)
        
        # Verify user owns this RMA
        rma_data = manager.get_rma(rma_id=rma_id)
        if not rma_data or rma_data["rma"]["user_id"] != user_id:
            flash("Access denied", "error")
            conn.close()
            return redirect(url_for("rma.my_returns"))
        
        rma_number = rma_data["rma"]["rma_number"]
        
        if request.method == "POST":
            reason = request.form.get("reason", "Customer requested cancellation")
            
            manager.cancel_rma(rma_id, actor=f"user_{user_id}", reason=reason)
            conn.commit()
            conn.close()
            
            flash("Return request cancelled", "success")
            return redirect(url_for("rma.my_returns"))
        
        # GET: Show confirmation page
        conn.close()
        return render_template("rma/cancel_confirm.html", rma=rma_data["rma"])
        
    except ValueError as e:
        flash(f"Cannot cancel: {str(e)}", "error")
        return redirect(url_for("rma.my_returns"))
    except Exception as e:
        flash(f"Error cancelling return: {str(e)}", "error")
        return redirect(url_for("rma.my_returns"))
