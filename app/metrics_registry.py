from prometheus_client import Counter, Histogram, Gauge

# --- Custom domain metrics ---
ocr_requests_total = Counter("ocr_requests_total", "Total number of OCR requests received")
upload_requests_total = Counter("upload_requests_total", "Total number of document uploads")
webhook_calls_total = Counter("webhook_calls_total", "Total number of webhooks processed")
db_query_latency_seconds = Histogram("db_query_latency_seconds", "Time taken for MongoDB operations")
active_users_gauge = Gauge("active_users", "Number of currently active authenticated users")
errors_total = Counter("app_errors_total", "Total application errors encountered")
