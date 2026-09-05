# SettleSense backend — Hugging Face Spaces (Docker SDK).
# Follows HF's documented permissions pattern: Spaces containers run as
# UID 1000, so a non-root user is created and owns everything under $HOME
# before any pip install or COPY, to avoid permission errors at build/run
# time. See: https://huggingface.co/docs/hub/spaces-sdks-docker
FROM python:3.13-slim

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

# HF Spaces' default app_port is 7860 (set to match in this repo's
# README.md YAML frontmatter). Spaces does NOT inject a $PORT env var the
# way Railway/Render do, so it's declared here directly — main.py's
# `os.environ.get("PORT", 8000)` fallback still works unchanged locally.
ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
