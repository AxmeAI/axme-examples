FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir "axme>=0.1.1"
COPY agent.py ./agent.py
ENV PORT=8080
CMD ["python", "agent.py"]
