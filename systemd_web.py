import os
import argparse
import subprocess
from flask import Flask, request, jsonify, render_template_string, Response
from dotenv import load_dotenv
from functools import wraps
import logging

def create_app(username, password, services):
    app = Flask(__name__)

    def run_systemctl_command(service, command):
        """Run a systemctl command for a specific service."""
        try:
            result = subprocess.run(
                ["systemctl", command, service],
                text=True,
                capture_output=True,
                check=True
            )
            logging.debug(result)
            return {"success": True, "output": result.stdout.strip()}
        except subprocess.CalledProcessError as e:
            logging.error(e)
            if e.returncode == 3:
                return {"sucess": False, "error": "Service is not running"}
            return {"success": False, "error": str(e)}

    def authenticate(auth_username, auth_password):
        """Check if username/password combination is valid."""
        return username == auth_username and password == auth_password

    def requires_auth(f):
        """Decorator to enforce basic authentication."""
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not authenticate(auth.username, auth.password):
                return Response(
                    "Could not verify your access level for that URL.\n"
                    "You have to login with proper credentials.", 401,
                    {"WWW-Authenticate": "Basic realm=\"Login Required\""}
                )
            return f(*args, **kwargs)
        return decorated

    @app.route("/")
    @requires_auth
    def index():
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Systemd Web Control</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px;width:60%;margin:auto;}
                button { margin: 5px; padding: 10px 15px; }
                pre { background-color: #f4f4f4; padding: 10px; border: 1px solid #ddd; }
            </style>
        </head>
        <body>
            <h1>Systemd Web Control</h1>
            {% for service in services %}
            <div>
                <h2>{{ service }}</h2>
                <button onclick="manageService('{{ service }}', 'start')">Start</button>
                <button onclick="manageService('{{ service }}', 'stop')">Stop</button>
                <button onclick="manageService('{{ service }}', 'restart')">Restart</button>
                <button onclick="manageService('{{ service }}', 'status')">Status</button>
                <pre id="{{ service }}-output">No action yet.</pre>
            </div>
            <hr>
            {% endfor %}
            <script>
                function manageService(service, action) {
                    fetch(`/service/${service}/${action}`, { method: "POST" })
                        .then(response => response.json())
                        .then(data => {
                            const output = document.getElementById(`${service}-output`);
                            if (data.success) {
                                output.textContent = data.output || "Command executed successfully.";
                            } else {
                                output.textContent = data.error || "An error occurred.";
                            }
                        });
                }
            </script>
        </body>
        </html>
        """, services=services)

    @app.route("/service/<service>/<action>", methods=["POST"])
    @requires_auth
    def manage_service(service, action):
        if service not in services:
            return jsonify({"success": False, "error": f"Service '{service}' is not configured"}), 400

        if action in ["start", "stop", "restart", "status"]:
            result = run_systemctl_command(service, action)
            return jsonify(result)

        return jsonify({"success": False, "error": "Invalid action"}), 400

    return app

if __name__ == "__main__":
    # Parse the command-line arguments
    parser = argparse.ArgumentParser(description="Systemd Service Manager")
    parser.add_argument(
        "--services", type=str, help="Comma-separated list of systemd services", default=os.getenv("SERVICES", "")
    )
    parser.add_argument("--host", type=str, help="Host to run the app on", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, help="Port to run the app on", default=int(os.getenv("PORT", 5000)))
    parser.add_argument("--env-file", type=str, help="Path to a .env file", default=None)
    parser.add_argument("--username", type=str, help="Username for authentication", default=os.getenv("USERNAME", "admin"))
    parser.add_argument("--password", type=str, help="Password for authentication", default=os.getenv("PASSWORD", "password"))

    args = parser.parse_args()

    # Load .env file if provided
    if args.env_file:
        load_dotenv(args.env_file)

    # Get the services list
    SERVICES = args.services.split(",") if args.services else []

    if not SERVICES:
        print("No services provided via CLI or .env. Use --services or set SERVICES in .env.")
        exit(1)

    # Create the app
    app = create_app(username=args.username, password=args.password, services=SERVICES)

    # Run the app
    app.run(host=args.host, port=args.port)
