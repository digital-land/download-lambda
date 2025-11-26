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

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
# Use --target to install into the Lambda task root
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy application code
COPY application/ ${LAMBDA_TASK_ROOT}/application/

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# The Lambda Web Adapter will start uvicorn automatically
# CMD specifies the command to run the FastAPI application
CMD ["uvicorn", "application.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
