from __future__ import annotations
from .product_repo import AProductRepo

from werkzeug.security import generate_password_hash, check_password_hash

import os
from pathlib import Path
from typing import Dict

from flask import Flask, redirect, render_template, request, session, url_for, flash, g, jsonify 
import sqlite3
import time
import uuid

from .dao import SalesRepo, ProductRepo, get_connection
from .payment import process as payment_process
from .main import init_db
from .adapters.registry import get_adapter
from .partners.partner_ingest_service import validate_products, upsert_products

# Import observability components
try:
    # Use absolute imports to ensure a single module instance across the app
    from src.observability.structured_logger import app_logger, log_request
    from src.observability.metrics_collector import metrics_collector, track_request_duration
    OBSERVABILITY_ENABLED = True
except ImportError:
    OBSERVABILITY_ENABLED = False
    print("Warning: Observability modules not found. Running without observability.")


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.secret_key = os.environ.get("APP_SECRET_KEY", "dev-insecure-secret")
    # Low stock threshold (configurable via environment variable)
    app.config['LOW_STOCK_THRESHOLD'] = int(os.environ.get('LOW_STOCK_THRESHOLD', '5'))

    from .flash_sales.routes import flash_bp
    app.register_blueprint(flash_bp)
    
    # Register partners blueprint (ingest, diagnostics, integrability)
    try:
        from .partners.routes import bp as partners_bp
        app.register_blueprint(partners_bp, url_prefix='/partners')
    except Exception as e:
        app.logger.exception("Failed to import/register partners blueprint; admin routes unavailable")
    
    # Register RMA (Returns & Refunds) blueprint
    try:
        from .rma.routes import bp as rma_bp
        app.register_blueprint(rma_bp)
    except Exception as e:
        app.logger.exception("Failed to import/register RMA blueprint; returns/refunds unavailable")

    # Register monitoring blueprint for observability
    if OBSERVABILITY_ENABLED:
        try:
            from .monitoring_routes import monitoring_bp
            app.register_blueprint(monitoring_bp)
            app.logger.info("Monitoring dashboard registered at /monitoring/dashboard")
        except Exception as e:
            app.logger.exception("Failed to register monitoring blueprint")

    root = Path(__file__).resolve().parents[1]
    db_path = os.environ.get("APP_DB_PATH", str(root / "app.sqlite"))
    init_db(db_path)

    def get_conn():
        return get_connection(db_path)

    def get_repo(conn: sqlite3.Connection) -> SalesRepo:
        return SalesRepo(conn, AProductRepo(conn))

    # Start background ingest worker if partners blueprint is available
    try:
        from .partners.ingest_queue import start_worker
        root = Path(__file__).resolve().parents[1]
        db_path = os.environ.get("APP_DB_PATH", str(root / "app.sqlite"))
        start_worker(db_path)
    except Exception:
        pass

    # ============================================
    # OBSERVABILITY MIDDLEWARE
    # ============================================
    
    @app.before_request
    def before_request_observability():
        """Initialize request tracking for observability"""
        # Generate unique request ID
        g.request_id = request.headers.get('X-Request-Id') or str(uuid.uuid4())
        g.start_time = time.time()
        
        if OBSERVABILITY_ENABLED:
            app_logger.info(
                f"Request started: {request.method} {request.path}",
                method=request.method,
                path=request.path,
                remote_addr=request.remote_addr
            )
    
    @app.after_request
    def after_request_observability(response):
        """Record metrics after each request"""
        if OBSERVABILITY_ENABLED and hasattr(g, 'start_time'):
            try:
                duration = time.time() - g.start_time
                
                # Record response time
                metrics_collector.observe(
                    'http_request_duration_seconds',
                    duration,
                    labels={
                        'endpoint': request.endpoint or 'unknown',
                        'method': request.method,
                        'status': response.status_code
                    }
                )
                
                # Log completion
                app_logger.info(
                    f"Request completed: {request.method} {request.path}",
                    status_code=response.status_code,
                    duration_ms=round(duration * 1000, 2)
                )
                
                # Track HTTP errors
                if response.status_code >= 400:
                    # Increment overall error counter for dashboard totals/rates
                    metrics_collector.increment_counter('errors_total')
                    metrics_collector.record_event('errors_total')
                    if 400 <= response.status_code < 500:
                        metrics_collector.increment_counter('http_errors', labels={'type': '4xx'})
                    elif 500 <= response.status_code < 600:
                        metrics_collector.increment_counter('http_errors', labels={'type': '5xx'})
                        
            except Exception as e:
                app.logger.error(f"Error in observability middleware: {e}")
        
        return response
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors with observability"""
        if OBSERVABILITY_ENABLED:
            # Count both category and total for dashboard visibility
            metrics_collector.increment_counter('errors_total')
            metrics_collector.record_event('errors_total')
            metrics_collector.increment_counter('http_errors', labels={'type': '4xx'})
            app_logger.warning(f"404 Not Found: {request.path}")
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors with observability"""
        if OBSERVABILITY_ENABLED:
            # Count both category and total for dashboard visibility
            metrics_collector.increment_counter('errors_total')
            metrics_collector.record_event('errors_total')
            metrics_collector.increment_counter('http_errors', labels={'type': '5xx'})
            app_logger.error(f"500 Internal Server Error", error=str(error))
        return render_template('500.html'), 500
    
    @app.errorhandler(429)
    def rate_limit_error(error):
        """Handle rate limit errors"""
        if OBSERVABILITY_ENABLED:
            metrics_collector.increment_counter('errors_total', labels={'type': 'rate_limit'})
            metrics_collector.record_event('errors_total')
            app_logger.warning("Rate limit exceeded", ip=request.remote_addr)
        return {'error': 'Rate limit exceeded. Please try again later.'}, 429

    # ============================================
    # ROUTES
    # ============================================

    @app.route("/")
    def index():
        """Home page - redirect to login if not logged in, otherwise to products"""
        if "user_id" in session:
            return redirect(url_for("products"))
        return redirect(url_for("login"))

    @app.route("/health")
    def health_check():
        """Health check endpoint for Docker/monitoring"""
        return {
            'status': 'healthy',
            'timestamp': time.time(),
            'version': '1.0.0'
        }, 200

    @app.route("/admin")
    def admin_home():
        """General Admin Homepage linking RMA and Partner admin tools."""
        # Priority: admin_username (partner or database admin when preserving user session)
        # Fallback: username (database admin or regular user)
        username = session.get("admin_username") or session.get("username", "Admin")
        
        # If we have an admin_user_id (database admin preserving user session), fetch that user
        admin_user_id = session.get("admin_user_id")
        if admin_user_id:
            conn = get_conn()
            try:
                admin_user = conn.execute(
                    "SELECT username, name FROM user WHERE id = ?",
                    (admin_user_id,)
                ).fetchone()
                if admin_user:
                    username = admin_user["username"]
            finally:
                conn.close()
        # Otherwise if username is from a database user (regular login), fetch current info
        elif not session.get("admin_username"):
            user_id = session.get("user_id")
            if user_id:
                conn = get_conn()
                try:
                    user = conn.execute(
                        "SELECT username, name FROM user WHERE id = ?",
                        (user_id,)
                    ).fetchone()
                    if user:
                        username = user["username"]
                finally:
                    conn.close()
        
        # Low stock alerts (allow optional override via query param for quick inspection)
        override = request.args.get('low_stock_threshold')
        threshold = app.config.get('LOW_STOCK_THRESHOLD', 5)
        if override:
            try:
                o_val = int(override)
                if 0 <= o_val <= 100000:  # basic sanity
                    threshold = o_val
            except ValueError:
                pass
        conn = get_conn()
        low_stock_products = []
        try:
            repo = AProductRepo(conn)
            low_stock_products = repo.get_low_stock_products(threshold)
        except Exception:
            low_stock_products = []
        finally:
            conn.close()

        return render_template(
            "admin_home.html",
            username=username,
            low_stock=low_stock_products,
            low_stock_threshold=threshold
        )

    @app.route('/api/low-stock')
    def api_low_stock():
        """Return JSON list of low-stock products (admin only)."""
        if not (session.get('is_admin') or session.get('admin_user_id') or session.get('admin_username')):
            return jsonify({'error': 'Unauthorized'}), 403
        conn = get_conn()
        try:
            repo = AProductRepo(conn)
            threshold = app.config.get('LOW_STOCK_THRESHOLD', 5)
            products = repo.get_low_stock_products(threshold)
            return jsonify({'threshold': threshold, 'products': products})
        finally:
            conn.close()

    @app.route("/products")
    def products():
        if "user_id" not in session:
            flash("Please login to access products", "error")
            return redirect(url_for("login"))
        q = request.args.get("q", "").strip()
        conn = get_conn()
        try:
            try:
                repo = AProductRepo(conn)
                if q:
                    rows = repo.search_products(q)
                else:
                    rows = repo.get_all_products()
            except Exception:
                rows = []
                flash(
                    "Product table not available. Partner A needs to add user/product schema and seed.",
                    "error",
                )
            return render_template("products.html", products=rows, q=q)
        finally:
            conn.close()

    @app.post("/cart/add")
    def cart_add():
        pid = int(request.form.get("product_id", 0))
        qty = int(request.form.get("qty", 1))
        
        if qty <= 0:
            flash("Quantity must be > 0", "error")
            return redirect(url_for("products"))
        
        conn = get_conn()
        try:
            repo = AProductRepo(conn)
            product = repo.get_product(pid)
            
            if not product:
                flash(f"Product ID {pid} not found", "error")
                return redirect(url_for("products"))
            
            if not repo.check_stock(pid, qty):
                flash(f"Only {product['stock']} in stock for {product['name']}", "error")
                return redirect(url_for("products"))
            
            cart = session.get("cart", {})
            cart[str(pid)] = cart.get(str(pid), 0) + qty
            session["cart"] = cart
            
            if OBSERVABILITY_ENABLED:
                app_logger.info(
                    "Item added to cart",
                    product_id=pid,
                    product_name=product['name'],
                    quantity=qty,
                    user_id=session.get('user_id')
                )
            
            flash(f"Added {qty} x {product['name']} to cart", "info")
            return redirect(url_for("cart_view"))
            
        except ValueError:
            flash("Invalid product ID", "error")
            return redirect(url_for("products"))
        finally:
            conn.close()

    @app.get("/cart")
    def cart_view():
        cart: Dict[str, int] = session.get("cart", {})
        conn = get_conn()
        items = []
        total = 0
        try:
            repo = AProductRepo(conn)
            for pid_str, qty in cart.items():
                pid = int(pid_str)
                prod = repo.get_product(pid)
                
                if not prod:
                    continue
                
                unit = int(prod["price_cents"])
                items.append({
                    "id": pid,
                    "name": prod["name"],
                    "qty": qty,
                    "unit": unit,
                    "line": unit * qty,
                    "is_flash_sale": prod.get("is_flash_sale", False),
                    "original_price": prod.get("original_price", unit)
                })
                total += unit * qty
        finally:
            conn.close()
        return render_template("cart.html", items=items, total=total)

    @app.post("/cart/clear")
    def cart_clear():
        session.pop("cart", None)
        flash("Cart cleared", "info")
        return redirect(url_for("products"))

    @app.post("/cart/remove")
    def cart_remove():
        pid = request.form.get("product_id")
        cart = session.get("cart", {})
        
        if pid in cart:
            del cart[pid]
            session["cart"] = cart
            flash("Item removed from cart", "info")
        
        return redirect(url_for("cart_view"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            selected_role = request.form.get("role", "customer")  # Get the selected role
            
            conn = get_conn()
            try:
                user = conn.execute(
                    "SELECT id, username, password, name FROM user WHERE username = ?", 
                    (username,)
                ).fetchone()
                
                if user:
                    try:
                        ok = check_password_hash(user["password"], password)
                    except ValueError as e:
                        flash("Your account uses an unsupported password hash. Please reset your password or contact support.", "error")
                        ok = False
                    if ok:
                        # Check if this is an admin user (name starts with "Admin: ")
                        is_admin_user = user["name"] and user["name"].startswith("Admin: ")
                        
                        # Validate that the selected role matches the user's actual role
                        if selected_role == "admin" and not is_admin_user:
                            flash("Invalid credentials for admin role", "error")
                            if OBSERVABILITY_ENABLED:
                                app_logger.warning("Failed admin login attempt - user is not admin", username=username)
                            return render_template("login.html")
                        
                        if selected_role == "customer" and is_admin_user:
                            flash("Admin accounts cannot login as customers. Please select Admin role.", "error")
                            if OBSERVABILITY_ENABLED:
                                app_logger.warning("Failed customer login attempt - user is admin", username=username)
                            return render_template("login.html")
                        
                        # Set session data
                        # Check if there's already a regular user logged in
                        existing_user_id = session.get("user_id")
                        
                        if is_admin_user:
                            # Admin user login - store separately to preserve regular user session
                            if existing_user_id and existing_user_id != user["id"]:
                                # Regular user already logged in, add admin without replacing
                                session["is_admin"] = True
                                session["admin_username"] = user["username"]
                                session["admin_user_id"] = user["id"]
                                # Don't flash message - it will show to the regular user
                                return redirect(url_for("admin_home"))
                            else:
                                # No existing user or same user, normal admin login
                                session["user_id"] = user["id"]
                                session["username"] = user["username"]
                                session["is_admin"] = True
                                flash("Admin login successful!", "success")
                                return redirect(url_for("admin_home"))
                        else:
                            # Regular user login - only allow if no admin is logged in
                            if session.get("is_admin"):
                                flash("An admin is already logged in. Please logout first or use a different browser.", "error")
                                return render_template("login.html")
                            
                            session["user_id"] = user["id"]
                            session["username"] = user["username"]
                        
                        if OBSERVABILITY_ENABLED:
                            app_logger.info(
                                "User logged in",
                                user_id=user["id"],
                                username=username
                            )
                        
                        flash("Login successful!", "success")
                        return redirect(url_for("dashboard"))
                
                if OBSERVABILITY_ENABLED:
                    app_logger.warning("Failed login attempt", username=username)
                
                flash("Invalid username or password", "error")
            finally:
                conn.close()
        
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        user_id = session.get('user_id')
        
        if OBSERVABILITY_ENABLED and user_id:
            app_logger.info("User logged out", user_id=user_id)
        
        session.clear()
        flash("You have been logged out", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    def dashboard():
        """User dashboard showing order history and stats with filtering support."""
        if "user_id" not in session:
            flash("Please login to access your dashboard", "error")
            return redirect(url_for("login"))
        
        user_id = session["user_id"]
        
        # Get filter parameters from query string
        status_filter = request.args.get('status', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        search_query = request.args.get('search', '').strip()
        
        conn = get_conn()
        try:
            # Fetch current username from database - always use database, never session
            # This ensures admin login doesn't affect what username is displayed
            user = conn.execute(
                "SELECT username, name FROM user WHERE id = ?",
                (user_id,)
            ).fetchone()
            
            if user:
                username = user["username"]
                # Debug logging to diagnose session issue
                if OBSERVABILITY_ENABLED:
                    app_logger.info(
                        "Dashboard loaded",
                        user_id=user_id,
                        fetched_username=username,
                        session_username=session.get("username"),
                        admin_username=session.get("admin_username"),
                        is_admin=session.get("is_admin")
                    )
            else:
                username = "User"
            
            # Build dynamic SQL query with filters
            query = """
                SELECT s.id, s.sale_time as created_at, s.status, 
                       s.total_cents / 100.0 as total,
                       GROUP_CONCAT(p.name || ' (' || si.quantity || 'x)', ', ') as items_summary
                FROM sale s
                LEFT JOIN sale_item si ON s.id = si.sale_id
                LEFT JOIN product p ON si.product_id = p.id
                WHERE s.user_id = ?
            """
            params = [user_id]
            
            # Apply status filter (including RMA-related statuses)
            if status_filter:
                if status_filter in ['COMPLETED', 'PENDING', 'PROCESSING', 'CANCELLED', 'REFUNDED']:
                    query += " AND s.status = ?"
                    params.append(status_filter)
                elif status_filter == 'RETURNED':
                    # For RETURNED status, find orders with completed RMAs
                    query += """ AND s.id IN (
                        SELECT sale_id FROM rma_requests 
                        WHERE status = 'COMPLETED' AND disposition IN ('REFUND', 'REPLACEMENT', 'REPAIR', 'STORE_CREDIT')
                    )"""
            
            # Apply date range filter
            if start_date:
                query += " AND DATE(s.sale_time) >= ?"
                params.append(start_date)
            if end_date:
                query += " AND DATE(s.sale_time) <= ?"
                params.append(end_date)
            
            # Apply search filter (by order ID or product name)
            if search_query:
                query += """ AND (
                    CAST(s.id AS TEXT) LIKE ? OR
                    s.id IN (
                        SELECT DISTINCT si2.sale_id 
                        FROM sale_item si2
                        JOIN product p2 ON si2.product_id = p2.id
                        WHERE p2.name LIKE ?
                    )
                )"""
                search_pattern = f"%{search_query}%"
                params.extend([search_pattern, search_pattern])
            
            query += " GROUP BY s.id ORDER BY s.sale_time DESC"
            
            # Get all user orders with items (filtered)
            orders = conn.execute(query, params).fetchall()
            
            # Get items for each order
            orders_with_items = []
            for order in orders:
                items_rows = conn.execute("""
                    SELECT si.*, p.name as product_name
                    FROM sale_item si
                    JOIN product p ON si.product_id = p.id
                    WHERE si.sale_id = ?
                """, (order["id"],)).fetchall()
                
                # Convert Row objects to dicts for template
                items_list = [dict(item) for item in items_rows]
                
                # Check if this is a replacement order (created by an RMA)
                is_replacement = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM rma_activity_log
                    WHERE notes LIKE ?
                """, (f"%Replacement order created: #{order['id']}%",)).fetchone()
                
                # Check if this order already has an RMA request
                has_rma = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM rma_requests
                    WHERE sale_id = ?
                """, (order["id"],)).fetchone()

                # Compute display status based on RMA disposition
                # Check for active (in-progress) RMAs first
                active_rma = conn.execute("""
                    SELECT disposition, status
                    FROM rma_requests
                    WHERE sale_id = ? AND status NOT IN ('COMPLETED','REJECTED','CANCELLED')
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (order["id"],)).fetchone()
                
                # Check for completed RMAs to show final outcome
                completed_rma = conn.execute("""
                    SELECT disposition, status
                    FROM rma_requests
                    WHERE sale_id = ? AND status = 'COMPLETED'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (order["id"],)).fetchone()
                
                # Check for rejected RMAs
                rejected_rma = conn.execute("""
                    SELECT disposition, status
                    FROM rma_requests
                    WHERE sale_id = ? AND status = 'REJECTED'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (order["id"],)).fetchone()
                
                display_status = order["status"]
                
                # Active RMA takes precedence (show in-progress status)
                if active_rma:
                    if active_rma["disposition"] == "REPAIR":
                        display_status = "REPAIRING"
                    elif active_rma["disposition"] == "REPLACEMENT":
                        display_status = "REPLACING"
                    elif active_rma["disposition"] == "REFUND":
                        display_status = "REFUNDING"
                    elif active_rma["disposition"] == "STORE_CREDIT":
                        display_status = "STORE_CREDIT"
                    elif active_rma["disposition"] == "REJECT":
                        display_status = "RETURN_REJECTED"
                # Rejected RMA shows rejection
                elif rejected_rma:
                    display_status = "RETURN_REJECTED"
                # Completed RMA shows final outcome
                elif completed_rma and order["status"] == "COMPLETED":
                    if completed_rma["disposition"] == "REPAIR":
                        display_status = "REPAIRED"
                    elif completed_rma["disposition"] == "REPLACEMENT":
                        display_status = "REPLACED"
                    elif completed_rma["disposition"] == "STORE_CREDIT":
                        display_status = "CREDITED"
                    elif completed_rma["disposition"] == "REFUND":
                        display_status = "REFUNDED"
                    elif completed_rma["disposition"] == "REJECT":
                        display_status = "RETURN_REJECTED"
                # If order status is already REFUNDED, keep it
                elif order["status"] == "REFUNDED":
                    display_status = "REFUNDED"
                
                orders_with_items.append({
                    "id": order["id"],
                    "created_at": order["created_at"],
                    "status": order["status"],
                    "display_status": display_status,
                    "total": order["total"],
                    "items": items_list,
                    "is_replacement": is_replacement["count"] > 0,
                    "has_rma": has_rma["count"] > 0
                })
            
            # Calculate stats (based on ALL orders, not just filtered)
            all_orders = conn.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(total_cents), 0) as total
                FROM sale WHERE user_id = ?
            """, (user_id,)).fetchone()
            
            stats = {
                "total_orders": all_orders["count"],
                "total_spent": all_orders["total"] / 100.0,
                "active_returns": 0,
                "store_credit": 0.0
            }
            
            # Count active returns and calculate store credit
            try:
                active_returns = conn.execute("""
                    SELECT COUNT(*) as count 
                    FROM rma_requests 
                    WHERE user_id = ? AND status NOT IN ('COMPLETED', 'REJECTED', 'CANCELLED')
                """, (user_id,)).fetchone()
                stats["active_returns"] = active_returns["count"] if active_returns else 0
                
                # Calculate total store credit from completed STORE_CREDIT RMAs
                store_credit_result = conn.execute("""
                    SELECT COALESCE(SUM(refund_amount_cents), 0) as total_credit
                    FROM rma_requests 
                    WHERE user_id = ? AND status = 'COMPLETED' AND disposition = 'STORE_CREDIT'
                """, (user_id,)).fetchone()
                stats["store_credit"] = (store_credit_result["total_credit"] or 0) / 100.0
            except:
                pass  # RMA table might not exist yet
        finally:
            conn.close()
            
            return render_template("dashboard.html", 
                                 username=username, 
                                 orders=orders_with_items,
                                 stats=stats,
                                 filters={
                                     'status': status_filter,
                                     'start_date': start_date,
                                     'end_date': end_date,
                                     'search': search_query
                                 })

    @app.route("/notifications")
    def notifications():
        """View user notifications"""
        if "user_id" not in session:
            flash("Please login to view notifications", "error")
            return redirect(url_for("login"))
        
        user_id = session["user_id"]
        
        from src.notifications import NotificationService
        conn = get_conn()
        try:
            # Get all notifications
            all_notifications = NotificationService.get_user_notifications(conn, user_id, unread_only=False, limit=100)
            unread_count = NotificationService.get_unread_count(conn, user_id)
            
            return render_template("notifications.html",
                                 notifications=all_notifications,
                                 unread_count=unread_count)
        finally:
            conn.close()
    
    @app.route("/notifications/mark-read/<int:notification_id>", methods=["POST"])
    def mark_notification_read(notification_id: int):
        """Mark a notification as read"""
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        user_id = session["user_id"]
        
        from src.notifications import NotificationService
        conn = get_conn()
        try:
            success = NotificationService.mark_as_read(conn, notification_id, user_id)
            unread_count = NotificationService.get_unread_count(conn, user_id)
            return jsonify({"success": success, "unread_count": unread_count})
        finally:
            conn.close()
    
    @app.route("/notifications/mark-all-read", methods=["POST"])
    def mark_all_notifications_read():
        """Mark all notifications as read"""
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        user_id = session["user_id"]
        
        from src.notifications import NotificationService
        conn = get_conn()
        try:
            count = NotificationService.mark_all_as_read(conn, user_id)
            return jsonify({"success": True, "count": count, "unread_count": 0})
        finally:
            conn.close()
    
    @app.route("/api/notifications/count")
    def get_notification_count():
        """API endpoint to get unread notification count (for badge)"""
        if "user_id" not in session:
            return jsonify({"count": 0})
        
        user_id = session["user_id"]
        
        from src.notifications import NotificationService
        conn = get_conn()
        try:
            count = NotificationService.get_unread_count(conn, user_id)
            return jsonify({"count": count})
        finally:
            conn.close()

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form["name"]
            username = request.form["username"]
            password = request.form["password"]
            
            conn = get_conn()
            try:
                existing = conn.execute("SELECT id FROM user WHERE username = ?", (username,)).fetchone()
                if existing:
                    flash("Username already exists", "error")
                else:
                    hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
                    conn.execute(
                        "INSERT INTO user (name, username, password) VALUES (?, ?, ?)",
                        (name, username, hashed_password)
                    )
                    conn.commit()
                    
                    if OBSERVABILITY_ENABLED:
                        app_logger.info("New user registered", username=username)
                    
                    flash("Registration successful! Please login.", "success")
                    return redirect(url_for("login"))
            finally:
                conn.close()
        
        return render_template("register.html")

    @app.route("/register-admin", methods=["POST"])
    def register_admin():
        """Handle admin registration - validates super admin key then creates new admin account."""
        super_admin_key = request.form.get("super_admin_key", "").strip()
        admin_username = request.form.get("admin_username", "").strip()
        admin_password = request.form.get("admin_password", "").strip()
        
        expected_super_key = os.environ.get("ADMIN_API_KEY", "admin-demo-key")
        
        # First verify super admin key
        if super_admin_key != expected_super_key:
            flash("Invalid super admin key. You need the super admin key to create admin accounts.", "error")
            return redirect(url_for("register"))
        
        # Validate inputs
        if not admin_username or not admin_password:
            flash("Username and password are required for admin account.", "error")
            return redirect(url_for("register"))
        
        # Create admin account in database
        conn = get_conn()
        try:
            # Check if admin username already exists
            existing = conn.execute("SELECT id FROM user WHERE username = ?", (admin_username,)).fetchone()
            if existing:
                flash("Admin username already exists. Choose a different username.", "error")
                return redirect(url_for("register"))
            
            # Create admin user with a flag to identify them as admin
            hashed_password = generate_password_hash(admin_password, method="pbkdf2:sha256")
            conn.execute(
                "INSERT INTO user (name, username, password) VALUES (?, ?, ?)",
                (f"Admin: {admin_username}", admin_username, hashed_password)
            )
            conn.commit()
            
            # Don't auto-login, redirect to login page
            flash(f"Admin account '{admin_username}' created successfully! Please login with your new credentials.", "success")
            return redirect(url_for("login"))
            
        except Exception as e:
            flash(f"Error creating admin account: {str(e)}", "error")
            return redirect(url_for("register"))
        finally:
            conn.close()

    @app.route("/uploads/rma/<filename>")
    def serve_rma_upload(filename):
        """Serve uploaded RMA photos."""
        from flask import send_from_directory
        import os
        upload_dir = os.path.join('/app', 'data', 'uploads', 'rma')
        return send_from_directory(upload_dir, filename)

    # Add login requirement to protected routes
    def login_required(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login to access this page", "error")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated_function

    @app.post("/checkout")
    def checkout():
        """Checkout with observability tracking"""
        pay_method = request.form.get("payment_method", "CARD")
        user_id = session.get("user_id")
        cart: Dict[str, int] = session.get("cart", {})
        cart_list = [(int(pid), qty) for pid, qty in cart.items()]
        
        if not user_id:
            flash("Please login to checkout", "error")
            return redirect(url_for("login"))
        
        if not cart_list:
            flash("Cart is empty", "error")
            return redirect(url_for("cart_view"))

        conn = get_conn()
        repo = get_repo(conn)
        
        try:
            # Calculate total for metrics
            total_cents = 0
            for pid, qty in cart_list:
                prod = conn.execute("SELECT price_cents FROM product WHERE id = ?", (pid,)).fetchone()
                if prod:
                    total_cents += prod[0] * qty
            
            if OBSERVABILITY_ENABLED:
                app_logger.info(
                    "Checkout started",
                    user_id=user_id,
                    cart_items=len(cart_list),
                    total_cents=total_cents,
                    payment_method=pay_method
                )
                metrics_collector.record_event('orders_total')
            
            # Use resilient payment with circuit breaker
            try:
                from .flash_sales.payment_resilience import process_payment_resilient
                payment_cb = process_payment_resilient
            except Exception:
                payment_cb = payment_process

            sale_id = repo.checkout_transaction(
                user_id=user_id,
                cart=cart_list,
                pay_method=pay_method,
                payment_cb=payment_cb,
            )
            
            # Success metrics
            if OBSERVABILITY_ENABLED:
                metrics_collector.increment_counter('orders_total')
                metrics_collector.increment_counter('orders_total', labels={'status': 'success'})
                app_logger.info(
                    "Checkout completed successfully",
                    sale_id=sale_id,
                    user_id=user_id,
                    total_cents=total_cents
                )
            
            session.pop("cart", None)
            flash(f"Checkout success. Sale #{sale_id}", "success")
            return redirect(url_for("receipt", sale_id=sale_id))
            
        except Exception as e:
            # Error metrics
            if OBSERVABILITY_ENABLED:
                metrics_collector.increment_counter('orders_total')
                metrics_collector.increment_counter('orders_total', labels={'status': 'failed'})
                metrics_collector.increment_counter('errors_total', labels={'type': 'checkout'})
                metrics_collector.record_event('errors_total')
                app_logger.error(
                    "Checkout failed",
                    user_id=user_id,
                    error=str(e),
                    exception_type=type(e).__name__
                )
            
            flash(str(e), "error")
            return redirect(url_for("cart_view"))
        finally:
            conn.close()

    @app.post('/partner/ingest')
    def partner_ingest_main():
        api_key = request.headers.get('X-API-Key') or request.form.get('api_key')
        if not api_key:
            return ("Missing API key", 401)

        conn_check = get_conn()
        try:
            cur = conn_check.execute('SELECT partner_id FROM partner_api_keys WHERE api_key = ?', (api_key,))
            row = cur.fetchone()
            if not row:
                return ("Invalid API key", 401)
        finally:
            conn_check.close()

        content_type = request.content_type or ''
        payload = request.get_data()
        adapter = get_adapter(content_type)
        if not adapter:
            if content_type.startswith('application/json'):
                adapter = get_adapter('application/json')
            elif content_type.startswith('text/csv') or content_type == 'text/plain':
                adapter = get_adapter('text/csv')
        if not adapter:
            return ('No adapter for content type', 415)

        try:
            products = adapter(payload, content_type)
        except Exception as e:
            return (f'Adapter parse error: {e}', 400)

        valid_items, validation_errors = validate_products(products)
        ingested = 0
        errors = validation_errors[:]
        if valid_items:
            conn = get_conn()
            try:
                upserted, upsert_errors = upsert_products(conn, valid_items)
                ingested = upserted
                errors.extend(upsert_errors)
            finally:
                conn.close()

        return ({'ingested': ingested, 'errors': errors}, 200)

    @app.get("/receipt/<int:sale_id>")
    def receipt(sale_id: int):
        conn = get_conn()
        try:
            sale = conn.execute(
                "SELECT id, user_id, sale_time, total_cents, status FROM sale WHERE id = ?",
                (sale_id,),
            ).fetchone()
            # Compute display status based on RMA disposition
            display_status = sale["status"] if sale else ""
            try:
                # Check for active (in-progress) RMAs first
                active_rma = conn.execute(
                    """
                    SELECT disposition, status
                    FROM rma_requests
                    WHERE sale_id = ? AND status NOT IN ('COMPLETED','REJECTED','CANCELLED')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (sale_id,),
                ).fetchone()
                
                # Check for completed RMAs to show final outcome
                completed_rma = conn.execute(
                    """
                    SELECT disposition, status
                    FROM rma_requests
                    WHERE sale_id = ? AND status = 'COMPLETED'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (sale_id,),
                ).fetchone()
                
                # Check for rejected RMAs
                rejected_rma = conn.execute(
                    """
                    SELECT disposition, status
                    FROM rma_requests
                    WHERE sale_id = ? AND status = 'REJECTED'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (sale_id,),
                ).fetchone()
                
                # Active RMA takes precedence (show in-progress status)
                if active_rma:
                    if active_rma["disposition"] == "REPAIR":
                        display_status = "REPAIRING"
                    elif active_rma["disposition"] == "REPLACEMENT":
                        display_status = "REPLACING"
                    elif active_rma["disposition"] == "REFUND":
                        display_status = "REFUNDING"
                    elif active_rma["disposition"] == "STORE_CREDIT":
                        display_status = "STORE_CREDIT"
                    elif active_rma["disposition"] == "REJECT":
                        display_status = "RETURN_REJECTED"
                # Rejected RMA shows rejection
                elif rejected_rma:
                    display_status = "RETURN_REJECTED"
                # Completed RMA shows final outcome
                elif completed_rma and sale["status"] == "COMPLETED":
                    if completed_rma["disposition"] == "REPAIR":
                        display_status = "REPAIRED"
                    elif completed_rma["disposition"] == "REPLACEMENT":
                        display_status = "REPLACED"
                    elif completed_rma["disposition"] == "STORE_CREDIT":
                        display_status = "CREDITED"
            except Exception:
                # rma tables may not exist in some setups
                pass
            items = conn.execute(
                "SELECT si.product_id, p.name as product_name, si.quantity, si.price_cents "
                "FROM sale_item si JOIN product p ON si.product_id = p.id "
                "WHERE si.sale_id = ?",
                (sale_id,),
            ).fetchall()
            payment = conn.execute(
                "SELECT method, amount_cents, status, ref FROM payment WHERE sale_id = ?",
                (sale_id,),
            ).fetchone()
        finally:
            conn.close()
        return render_template("receipt.html", sale=sale, items=items, payment=payment, display_status=display_status)

    @app.get("/admin/flash-sale")
    def admin_flash_sale():
        """Admin page to manage flash sales"""
        conn = get_conn()
        try:
            cursor = conn.execute("""
                SELECT id, name, price_cents, flash_sale_active, flash_sale_price_cents
                FROM product 
                WHERE active = 1
                ORDER BY name
            """)
            products = cursor.fetchall()
            return render_template("admin_flash_sale.html", products=products)
        finally:
            conn.close()

    @app.post("/admin/flash-sale/set")
    def admin_flash_sale_set():
        """Set a product as flash sale"""
        product_id = int(request.form.get("product_id"))
        flash_price = float(request.form.get("flash_price"))
        flash_price_cents = int(flash_price * 100)
        
        conn = get_conn()
        try:
            conn.execute("""
                UPDATE product 
                SET flash_sale_active = 1, flash_sale_price_cents = ?
                WHERE id = ?
            """, (flash_price_cents, product_id))
            conn.commit()
            
            if OBSERVABILITY_ENABLED:
                app_logger.info(
                    "Flash sale activated",
                    product_id=product_id,
                    flash_price_cents=flash_price_cents
                )
            
            flash("Flash sale activated!", "success")
        finally:
            conn.close()
        
        return redirect(url_for("admin_flash_sale"))

    @app.post("/admin/flash-sale/remove")
    def admin_flash_sale_remove():
        """Remove flash sale from product"""
        product_id = int(request.form.get("product_id"))
        
        conn = get_conn()
        try:
            conn.execute("""
                UPDATE product 
                SET flash_sale_active = 0, flash_sale_price_cents = NULL
                WHERE id = ?
            """, (product_id,))
            conn.commit()
            
            if OBSERVABILITY_ENABLED:
                app_logger.info("Flash sale removed", product_id=product_id)
            
            flash("Flash sale removed", "info")
        finally:
            conn.close()
        
        return redirect(url_for("admin_flash_sale"))

    return app


# Create app instance at module level for Flask CLI and WSGI servers
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))