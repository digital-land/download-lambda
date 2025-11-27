# Multi-stage Dockerfile for AWS Lambda with Web Adapter
# This allows FastAPI to run inside Lambda with response streaming support

# Use AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.12

# Copy Lambda Web Adapter from its official image
# The adapter translates Lambda events to HTTP requests for FastAPI
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.3 /lambda-adapter /opt/extensions/lambda-adapter

# Set environment variables for the Lambda Web Adapter
ENV PORT=8000
ENV AWS_LWA_INVOKE_MODE=response_stream
ENV AWS_LWA_READINESS_CHECK_PORT=8000
ENV AWS_LWA_READINESS_CHECK_PATH=/health

# Ensure Python can find packages installed in LAMBDA_TASK_ROOT
# ENV PYTHONPATH="${LAMBDA_TASK_ROOT}:${PYTHONPATH}"

# Create a startup script for uvicorn
# Use python -m to run uvicorn as a module instead of calling it directly
RUN printf '#!/bin/sh\nexec python -m uvicorn application.main:app --host 0.0.0.0 --port 8000 --log-level info\n' > /lambda-entrypoint.sh && \
    chmod +x /lambda-entrypoint.sh

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
# Use --target to install into the Lambda task root
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy application code
COPY application/ ${LAMBDA_TASK_ROOT}/application/

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# The Lambda Web Adapter will execute the startup script
# Use the startup script as the handler
CMD ["/lambda-entrypoint.sh"]
