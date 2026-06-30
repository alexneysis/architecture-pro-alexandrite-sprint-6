import os
import random
import time

from flask import Flask, jsonify, request

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from opentelemetry.instrumentation.flask import FlaskInstrumentor


SERVICE_NAME = "service-b-price-calculation"
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


@app.route("/calculate", methods=["GET"])
def calculate_price():
    order_id = request.args.get("order_id", "unknown")

    with tracer.start_as_current_span("calculate_price") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.status.before", "SUBMITTED")
        span.set_attribute("order.status.after", "PRICE_CALCULATED")
        span.set_attribute("calculation.type", "3d_model_price")

        processing_time = random.uniform(0.2, 1.5)
        time.sleep(processing_time)

        price = random.randint(10_000, 100_000)

        span.set_attribute("calculation.duration_ms", int(processing_time * 1000))
        span.set_attribute("calculation.price", price)

        return jsonify(
            {
                "service": SERVICE_NAME,
                "order_id": order_id,
                "status": "PRICE_CALCULATED",
                "price": price,
                "currency": "RUB",
                "processing_time_seconds": round(processing_time, 2),
            }
        )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)