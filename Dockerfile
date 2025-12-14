FROM python:3.9-slim

WORKDIR /app

# Setup virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY . .

# Install dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command if no args are provided
CMD ["backup", "--help"]
