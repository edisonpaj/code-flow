# syntax=docker/dockerfile:1

FROM maven:3.9-eclipse-temurin-17 AS spoon-builder

WORKDIR /build

COPY spoon-analyzer/pom.xml spoon-analyzer/pom.xml
RUN mvn -B -f spoon-analyzer/pom.xml dependency:go-offline

COPY spoon-analyzer/src spoon-analyzer/src
RUN mvn -B -f spoon-analyzer/pom.xml clean package -DskipTests


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EXPERT_CODE_FLOW_SPOON=selectable \
    PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend backend
COPY frontend frontend
COPY spoon-analyzer/pom.xml spoon-analyzer/pom.xml
COPY --from=spoon-builder /build/spoon-analyzer/target/expert-code-flow-spoon.jar spoon-analyzer/target/expert-code-flow-spoon.jar

RUN mkdir -p /app/.uploads/projects /app/.cache/maturity /app/.cache/spoon \
    && useradd --create-home --uid 10001 codeflow \
    && chown -R codeflow:codeflow /app

USER codeflow

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '8000') + '/api/health', timeout=3)" || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
