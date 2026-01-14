#!/bin/bash
set -e

# Function to substitute environment variables in a template file
substitute_env_vars() {
    local template_file="$1"
    local output_file="$2"
    
    echo "Substituting environment variables in $template_file -> $output_file"
    
    # Use envsubst to replace environment variables
    if [ -f "$template_file" ]; then
        envsubst < "$template_file" > "$output_file"
        echo "Configuration file created: $output_file"
    else
        echo "Warning: Template file $template_file not found"
    fi
}

# Ensure config directory exists
mkdir -p "$CONFIG_DIR"

# Check if settings.json already exists
if [ ! -f "$CONFIG_DIR/settings.json" ]; then
    echo "Creating initial jellyfin_debrid configuration..."
    
    # Set default values if environment variables are not provided
    export JELLYSEERR_BASE_URL="${JELLYSEERR_BASE_URL:-http://192.168.1.169:5055}"
    export JELLYSEERR_USERS="${JELLYSEERR_USERS:-all}"
    
    # Verify required environment variables
    if [ -z "$JELLYSEERR_API_KEY" ]; then
        echo "ERROR: JELLYSEERR_API_KEY environment variable is required"
        echo "Please get your API key from your Jellyseerr settings"
        exit 1
    fi
    
    if [ -z "$REALDEBRID_API_KEY" ] || [ "$REALDEBRID_API_KEY" = "YOUR_REALDEBRID_API_KEY_HERE" ]; then
        echo "ERROR: REALDEBRID_API_KEY environment variable is required"
        echo "Please get your API key from your Real-Debrid account"
        exit 1
    fi
    
    # Generate settings.json from template
    substitute_env_vars "/app/settings.json.template" "$CONFIG_DIR/settings.json"
    echo "jellyfin_debrid pre-configured successfully!"
    
    # Show generated config for debugging (first 20 lines)
    echo "Generated configuration preview:"
    head -20 "$CONFIG_DIR/settings.json"
else
    echo "Existing configuration found at $CONFIG_DIR/settings.json"
fi

# Execute the original command
exec "$@"