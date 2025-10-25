# docker run -p local_port:container_port image_name
FROM python:3.10-slim
# This makes /app the default folder inside the container where all commands and files run.
# So when you copy or run anything next, it happens inside /app.
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
# Tells Docker that this container will listen on port 8001 (your node’s API).
EXPOSE 8001
CMD ["uvicorn", "cache_logic.server:app", "--host", "0.0.0.0", "--port", "8001"]