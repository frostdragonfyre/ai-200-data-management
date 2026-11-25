"""One local embedding model for everything: stored items and questions.

all-MiniLM-L6-v2 produces 384 numbers per text. It runs on the CPU in Cloud
Shell, so no model endpoint or quota is involved. setup.sh downloads it once
(prewarm) so the first call doesn't wait on a download.
"""
import time

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_TAG = "all-MiniLM-L6-v2"
DIMENSIONS = 384
_model = None


def model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(MODEL_NAME)
    return _model


def embed(text):
    """Return one embedding as a list of 384 floats."""
    return [float(x) for x in next(iter(model().embed([text])))]


def timed_embed(text):
    start = time.perf_counter()
    vector = embed(text)
    return vector, (time.perf_counter() - start) * 1000


if __name__ == "__main__":
    v, ms = timed_embed("warm up")
    print(f"Model ready: {len(v)} dimensions, {ms:.0f} ms")
