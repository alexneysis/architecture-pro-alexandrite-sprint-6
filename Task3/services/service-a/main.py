import os
import uuid
import requests

from flask import Flask, jsonify

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


SERVICE_NAME = "service-a-order-api"
SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://service-b:8080/calculate")
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://simplest-collector:4317",
)

resource = Resource.create(
    {
        "service.name": SERVICE_NAME,
        "deployment.environment": os.getenv("ENVIRONMENT", "dev"),
    }
)

trace_provider = TracerProvider(resource=resource)
trace_provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
    )
)

trace.set_tracer_provider(trace_provider)

tracer = trace.get_tracer(SERVICE_NAME)

app = Flask(__name__)

FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()


@app.route("/", methods=["GET"])
def create_order():
    order_id = str(uuid.uuid4())

    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.source", "online_shop")
        span.set_attribute("order.status", "SUBMITTED")

        response = requests.get(
            SERVICE_B_URL,
            params={"order_id": order_id},
            timeout=10,
        )

        span.set_attribute("price_calculation.http_status", response.status_code)

        if response.status_code >= 400:
            span.set_attribute("order.result", "price_calculation_failed")
            return jsonify(
                {
                    "service": SERVICE_NAME,
                    "order_id": order_id,
                    "status": "ERROR",
                    "message": "Price calculation failed",
                }
            ), 500

        price_data = response.json()

        span.set_attribute("order.result", "price_calculated")
        span.set_attribute("order.calculated_price", price_data.get("price"))

        return jsonify(
            {
                "service": SERVICE_NAME,
                "order_id": order_id,
                "status": "PRICE_CALCULATED",
                "price_result": price_data,
            }
        )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)