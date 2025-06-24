FROM public.ecr.aws/lambda/python:3.10

WORKDIR /var/task

COPY api/ .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -t .
    