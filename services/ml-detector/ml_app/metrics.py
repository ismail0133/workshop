from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.score = Gauge(
            "ml_decision_score",
            "Dernier decision_function (bas = atypique)",
            registry=self.registry,
        )
        self.threshold = Gauge(
            "ml_threshold", "Seuil de décision du modèle chargé", registry=self.registry
        )
        self.inference = Histogram(
            "ml_inference_duration_seconds",
            "Durée d'inférence",
            registry=self.registry,
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1),
        )
        self.windows = Counter(
            "ml_windows_total", "Fenêtres traitées", ["status"], registry=self.registry
        )
        for status in ("valid", "invalid"):
            self.windows.labels(status).inc(0)
        self.model_info = Gauge(
            "ml_model_info", "Modèle chargé", ["version"], registry=self.registry
        )
        self.anomalies = Counter("ml_anomalies_total", "Anomalies émises", registry=self.registry)
        self.deliveries = Counter(
            "ml_event_deliveries_total", "Livraisons Incident", ["outcome"], registry=self.registry
        )
        self.outbox = Gauge(
            "ml_outbox_pending", "Événements en attente d'envoi", registry=self.registry
        )
