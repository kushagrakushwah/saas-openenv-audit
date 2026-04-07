# ── Base image ───────────────────────────────────────────────────────────────
FROM python:3.11-slim

# HuggingFace Spaces runs containers as a non-root user (uid 1000).
# Create that user so file permissions work correctly on HF Spaces.
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install dependencies first (layer-cached separately from app code)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Give ownership to the non-root user
RUN chown -R appuser:appuser /app

USER appuser

# HuggingFace Spaces requires port 7860
EXPOSE 7860

# Start the FastAPI server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]