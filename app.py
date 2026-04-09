"""
Invoice Platform — Flask application entry point.
Run:  python app.py
Then: open http://localhost:5000
"""
import io
import logging
import os

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for

import config
from services import data_loader, pdf_generator, drive_uploader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

# ---------------------------------------------------------------------------
# Startup: load all CSV data into memory
# ---------------------------------------------------------------------------
with app.app_context():
    logger.info("Loading CSV data from: %s", os.path.abspath(config.DATA_DIR))
    data_loader.load_all(config.DATA_DIR)


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    drive_connected = request.args.get("drive_connected") == "true"
    return render_template("index.html", drive_connected_flash=drive_connected)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
@app.route("/api/health")
def health():
    return jsonify(data_loader.get_health())


@app.route("/api/config/drive-status")
def drive_status():
    status = drive_uploader.get_status(
        config.GOOGLE_OAUTH_TOKEN_FILE,
        config.GOOGLE_SERVICE_ACCOUNT_FILE,
        config.GOOGLE_DRIVE_FOLDER_ID,
    )
    # Also report whether OAuth credentials are configured in .env
    status["oauth_configured"] = bool(config.GOOGLE_OAUTH_CLIENT_ID and config.GOOGLE_OAUTH_CLIENT_SECRET)
    return jsonify(status)


# ---------------------------------------------------------------------------
# Google Drive — OAuth 2.0
# ---------------------------------------------------------------------------
_REDIRECT_URI = "http://localhost:5000/api/drive/callback"


@app.route("/api/drive/connect")
def drive_connect():
    if not config.GOOGLE_OAUTH_CLIENT_ID or not config.GOOGLE_OAUTH_CLIENT_SECRET:
        return jsonify({
            "error": "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set in .env first."
        }), 400

    flow = drive_uploader.build_oauth_flow(
        config.GOOGLE_OAUTH_CLIENT_ID,
        config.GOOGLE_OAUTH_CLIENT_SECRET,
        _REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/api/drive/callback")
def drive_callback():
    state = session.get("oauth_state", "")
    flow = drive_uploader.build_oauth_flow(
        config.GOOGLE_OAUTH_CLIENT_ID,
        config.GOOGLE_OAUTH_CLIENT_SECRET,
        _REDIRECT_URI,
    )
    flow.state = state

    # Allow http for localhost during development
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    flow.fetch_token(authorization_response=request.url)

    drive_uploader.save_oauth_token(flow.credentials, config.GOOGLE_OAUTH_TOKEN_FILE)
    return redirect("/?drive_connected=true")


@app.route("/api/drive/disconnect", methods=["POST"])
def drive_disconnect():
    drive_uploader.disconnect_oauth(config.GOOGLE_OAUTH_TOKEN_FILE)
    return jsonify({"disconnected": True})


# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------
@app.route("/api/categories")
def categories():
    return jsonify(data_loader.get_categories())


@app.route("/api/brands")
def brands():
    category = request.args.get("category", "").strip()
    return jsonify(data_loader.get_brands(category or None))


@app.route("/api/dates")
def dates():
    return jsonify(data_loader.get_dates())


@app.route("/api/currencies")
def currencies():
    return jsonify(data_loader.get_currencies())


# ---------------------------------------------------------------------------
# Dynamic search
# ---------------------------------------------------------------------------
@app.route("/api/customers/search")
def customers_search():
    query = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify(data_loader.search_customers(query, limit))


@app.route("/api/customers/<customer_id>")
def customer_detail(customer_id):
    customer = data_loader.get_customer(customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404
    return jsonify(customer)


@app.route("/api/products")
def products():
    category = request.args.get("category", "").strip() or None
    brand = request.args.get("brand", "").strip() or None
    query = request.args.get("q", "").strip() or None
    limit = min(int(request.args.get("limit", 100)), 500)
    return jsonify(data_loader.get_products(category, brand, query, limit))


@app.route("/api/products/<product_id>")
def product_detail(product_id):
    product = data_loader.get_product(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(product)


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------
def _extract_invoice_data(req) -> dict:
    data = req.get_json(force=True, silent=True) or {}
    return {
        "dt": data.get("dt", ""),
        "order_ts": data.get("order_ts", ""),
        "customer_id": data.get("customer_id", ""),
        "customer_info": data.get("customer_info", {}),
        "order_id": data.get("order_id", ""),
        "item_seq": data.get("item_seq", 1),
        "product_id": data.get("product_id", ""),
        "product_info": data.get("product_info", {}),
        "quantity": data.get("quantity", 1),
        "unit_price_currency": data.get("unit_price_currency", "USD"),
        "unit_price": data.get("unit_price", 0),
        "discount_pct": data.get("discount_pct", 0),
        "tax_amount": data.get("tax_amount", 0),
        "channel": data.get("channel", "web"),
        "coupon_code": data.get("coupon_code", ""),
    }


@app.route("/api/invoice/preview", methods=["POST"])
def invoice_preview():
    invoice_data = _extract_invoice_data(request)
    html = pdf_generator.render_invoice_html(
        invoice_data, config.COMPANY_NAME, config.COMPANY_ADDRESS
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/invoice/generate", methods=["POST"])
def invoice_generate():
    invoice_data = _extract_invoice_data(request)
    order_id = invoice_data.get("order_id", "unknown")
    item_seq = invoice_data.get("item_seq", 1)
    filename = f"Invoice-{order_id}-{item_seq}.pdf"

    pdf_bytes = pdf_generator.generate_pdf(
        invoice_data, config.COMPANY_NAME, config.COMPANY_ADDRESS
    )

    os.makedirs(config.PDF_OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(config.PDF_OUTPUT_DIR, filename), "wb") as f:
        f.write(pdf_bytes)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/invoice/upload", methods=["POST"])
def invoice_upload():
    if not drive_uploader.is_configured(
        config.GOOGLE_OAUTH_TOKEN_FILE,
        config.GOOGLE_SERVICE_ACCOUNT_FILE,
        config.GOOGLE_DRIVE_FOLDER_ID,
    ):
        return jsonify({"error": "Google Drive is not connected. Click 'Connect Google Drive' first."}), 503

    invoice_data = _extract_invoice_data(request)
    order_id = invoice_data.get("order_id", "unknown")
    item_seq = invoice_data.get("item_seq", 1)
    filename = f"Invoice-{order_id}-{item_seq}.pdf"

    pdf_bytes = pdf_generator.generate_pdf(
        invoice_data, config.COMPANY_NAME, config.COMPANY_ADDRESS
    )
    result = drive_uploader.upload_pdf(
        pdf_bytes, filename,
        config.GOOGLE_OAUTH_TOKEN_FILE,
        config.GOOGLE_SERVICE_ACCOUNT_FILE,
        config.GOOGLE_DRIVE_FOLDER_ID,
    )
    result["filename"] = filename
    return jsonify(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(port=config.FLASK_PORT, debug=True)
