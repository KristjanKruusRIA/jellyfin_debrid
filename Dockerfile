FROM python:3

# Install gettext for envsubst and aria2 for fast multi-connection downloads
RUN apt-get update && apt-get install -y gettext-base aria2 && rm -rf /var/lib/apt/lists/*

# Copy the application code
COPY . /app
WORKDIR /app

# Install Python dependencies
RUN pip install -r requirements.txt

# Set environment variables
ENV TERM=xterm
ENV CONFIG_DIR=/config

# Create a startup script that will handle configuration
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create config directory
RUN mkdir -p /config

# Copy default settings template
COPY settings.json.template /app/

# Set the entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "./main.py", "--config-dir", "/config"]
