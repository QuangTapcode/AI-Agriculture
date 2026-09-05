FROM python:3.11-slim

WORKDIR /app

# Thu vien he thong cho OpenCV (libGL + glib).
# Goi libgl1-mesa-glx da bi go khoi Debian bookworm — nen cua python:3.11-slim
# — nen phai dung libgl1. Da bo libpq-dev vi do la driver PostgreSQL,
# du an nay dung SQL Server.
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ultralytics keo ve ban torch CUDA: rieng cac wheel NVIDIA (cudnn, cublas,
# cufft, nccl...) da ~6 GB. docker-compose.yml KHONG cap GPU cho container
# nay, nen toan bo CUDA do khong bao gio duoc dung. Cai truoc ban CPU-only
# (~200 MB) de pip coi nhu torch da thoa man khi doc requirements.txt.
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create upload directory
RUN mkdir -p uploads/quality_check

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
