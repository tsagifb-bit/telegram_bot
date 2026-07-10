# Gunakan image resmi Python yang ringan (slim)
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Tentukan working directory di dalam container
WORKDIR /app

# Salin file requirements terlebih dahulu untuk mengoptimalkan caching layer Docker
COPY requirements.txt .

# Install dependency
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode program dan file CSV/database ke dalam container
COPY . .

# Jalankan aplikasi botSite.py
CMD ["python", "botSite.py"]
