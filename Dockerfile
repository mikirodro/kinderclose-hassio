FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY kinderclose.py .
COPY custom_components ./custom_components
USER 65534:65534
CMD ["python", "-u", "kinderclose.py", "--watch"]
