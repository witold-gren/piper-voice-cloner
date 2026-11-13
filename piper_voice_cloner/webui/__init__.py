"""Web UI (Gradio) on top of the same steps as the `pvc` command line."""

import os

# private tool: no usage telemetry to gradio.app / huggingface.co; runs before gradio is imported
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
