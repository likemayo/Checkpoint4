from __future__ import annotations
from .product_repo import AProductRepo

from werkzeug.security import generate_password_hash, check_password_hash

import os
from pathlib import Path
from typing import Dict

from flask import Flask, redirect, render_template, request, session, url_for, flash, g 
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
    from .observability.structured_logger import app_logger, log_request
    from .observability.metrics_collector import metrics_collector, track_request_duration
    OBSERVABILITY_ENABLED = True
except ImportError:
    OBSERVABILITY_ENABLED = False
    print("Warning: Observability modules not found. Running without observability.")


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.secret_key = os.environ.get("APP_SECRET_KEY", "dev-insecure-secret")

    from .flash_sales.routes import flash_bp
    app.register_blueprint(flash_bp)
    
    # Register partners blueprint (ingest, diagnostics, integrability)
    try:
        from .partners.routes import bp as partners_bp
        app.register_blueprint(partners_bp)
    except Exception as e:
        app.logger.exception("Failed to import/register partners blueprint; admin routes unavailable")

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
            metrics_collector.increment_counter('http_errors', labels={'type': '4xx'})
            app_logger.warning(f"404 Not Found: {request.path}")
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors with observability"""
        if OBSERVABILITY_ENABLED:
            metrics_collector.increment_counter('http_errors', labels={'type': '5xx'})
            app_logger.error(f"500 Internal Server Error", error=str(error))
        return render_template('500.html'), 500
    
    @app.errorhandler(429)
    def rate_limit_error(error):
        """Handle rate limit errors"""
        if OBSERVABILITY_ENABLED:
            metrics_collector.increment_counter('errors_total', labels={'type': 'rate_limit'})
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
            
            conn = get_conn()
            try:
                user = conn.execute(
                    "SELECT id, username, password FROM user WHERE username = ?", 
                    (username,)
                ).fetchone()
                
                if user:
                    try:
                        ok = check_password_hash(user["password"], password)
                    except ValueError as e:
                        flash("Your account uses an unsupported password hash. Please reset your password or contact support.", "error")
                        ok = False
                    if ok:
                        session["user_id"] = user["id"]
                        session["username"] = user["username"]
                        
                        if OBSERVABILITY_ENABLED:
                            app_logger.info(
                                "User logged in",
                                user_id=user["id"],
                                username=username
                            )
                        
                        flash("Login successful!", "success")
                        return redirect(url_for("products"))
                
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
        return render_template("receipt.html", sale=sale, items=items, payment=payment)

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
    

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))