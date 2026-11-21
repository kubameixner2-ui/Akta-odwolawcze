FROM python:3.13-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY run.py fields.py names.py scan_fields.py extractor.py check_api.py index.html LICENSE ./
COPY config/ config/
COPY tessdata/ tessdata/
CMD ["python", "run.py"]
