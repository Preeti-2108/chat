FROM public.ecr.aws/lambda/python:3.12

WORKDIR /var/task

# Upgrade pip and install build tools
RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .

# Install dependencies (optimized without cache to reduce image size)
RUN pip install --no-cache-dir -r requirements.txt -t .

COPY . .