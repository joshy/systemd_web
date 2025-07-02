import argparse
import logging
import os
import subprocess
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template_string, request


def create_app(username, password, services):
    app = Flask(__name__)

    def parse_service_definition(service_def):
        """Parse service definition to extract service name and host info."""
        if '@' in service_def and ':' in service_def:
            # Format: user@host:service_name (remote service)
            user_host, service_name = service_def.split(':', 1)
            if '@' in user_host:
                user, host = user_host.split('@', 1)
                return service_name.strip(), user.strip(), host.strip(), service_name.strip()
            else:
                # Format: host:service_name (remote service without user)
                return service_name.strip(), None, user_host.strip(), service_name.strip()
        else:
            # Local service (no @ or : in the definition)
            return service_def.strip(), None, None, service_def.strip()

    def run_systemctl_command(service, command, host=None, remote_service=None, user=None):
        """Run a systemctl command for a specific service on local or remote host."""
        try:
            if host:
                # Remote execution via SSH - always use remote_service name
                target_service = remote_service or service
                if user:
                    ssh_cmd = ["ssh", f"{user}@{host}", f"systemctl {command} {target_service}"]
                else:
                    ssh_cmd = ["ssh", host, f"systemctl {command} {target_service}"]
                result = subprocess.run(
                    ssh_cmd,
                    text=True,
                    capture_output=True,
                    check=True
                )
            else:
                # Local execution
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
                return {"success": False, "error": "Service is not running"}
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
        # Parse services to get display names and host info
        service_info = []
        for service_def in services:
            service_name, user, host, remote_service = parse_service_definition(service_def)
            if host:
                if user:
                    display_name = f"{user}@{host}:{service_name}"
                else:
                    display_name = f"{host}:{service_name}"
            else:
                display_name = service_name
            service_info.append({
                'definition': service_def,
                'display_name': display_name,
                'service_name': service_name,
                'user': user,
                'host': host,
                'remote_service': remote_service
            })
        
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Systemd Web Control</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px;width:60%;margin:auto;}
                button { margin: 5px; padding: 10px 15px; }
                pre { background-color: #f4f4f4; padding: 10px; border: 1px solid #ddd; white-space: pre; overflow-x:auto }
                .service-info { color: #666; font-size: 0.9em; margin-bottom: 10px; }
            </style>
        </head>
        <body>
            <h1>Systemd Web Control</h1>
            {% for service in service_info %}
            <div>
                <h2>{{ service.display_name }}</h2>
                {% if service.host %}
                <div class="service-info">
                    Remote host: {{ service.host }}
                    {% if service.user %}
                    (User: {{ service.user }})
                    {% endif %}
                </div>
                {% else %}
                <div class="service-info">Local service</div>
                {% endif %}
                <button onclick="manageService('{{ service.definition }}', 'start')">Start</button>
                <button onclick="manageService('{{ service.definition }}', 'stop')">Stop</button>
                <button onclick="manageService('{{ service.definition }}', 'restart')">Restart</button>
                <button onclick="manageService('{{ service.definition }}', 'status')">Status</button>
                <pre id="{{ service.definition }}-output">No action yet.</pre>
            </div>
            <hr>
            {% endfor %}
            <script>
                function manageService(service, action) {
                    fetch(`/service/${encodeURIComponent(service)}/${action}`, { method: "POST" })
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
        """, service_info=service_info)

    @app.route("/service/<service>/<action>", methods=["POST"])
    @requires_auth
    def manage_service(service, action):
        # Decode the service name from URL
        service = request.view_args['service']
        
        if service not in services:
            return jsonify({"success": False, "error": f"Service '{service}' is not configured"}), 400

        if action in ["start", "stop", "restart", "status"]:
            service_name, user, host, remote_service = parse_service_definition(service)
            result = run_systemctl_command(service_name, action, host, remote_service, user)
            return jsonify(result)

        return jsonify({"success": False, "error": "Invalid action"}), 400

    return app

if __name__ == "__main__":
    # Parse the command-line arguments
    parser = argparse.ArgumentParser(description="Systemd Service Manager")
    parser.add_argument(
        "--services", type=str, help="Comma-separated list of systemd services (format: user@host:service_name for remote or service_name for local)", default=os.getenv("SERVICES", "")
    )
    parser.add_argument("--host", type=str, help="Host to run the app on", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, help="Port to run the app on", default=int(os.getenv("PORT", 5000)))
    parser.add_argument("--env-file", type=str, help="Path to a .env file", default=None)
    parser.add_argument("--username", type=str, help="Username for authentication", default=os.getenv("USERNAME", "admin"))
    parser.add_argument("--password", type=str, help="Password for authentication", default=os.getenv("PASSWORD", "password"))
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with auto-reload")

    args = parser.parse_args()

    # Load .env file if provided
    if args.env_file:
        load_dotenv(args.env_file)

    # Get the services list
    SERVICES = args.services.split(",") if args.services else []

    if not SERVICES:
        print("No services provided via CLI or .env. Use --services or set SERVICES in .env.")
        print("Service format: 'user@host:service_name' for remote, 'service_name' for local")
        print("Example: 'ubuntu@192.168.1.100:nginx,server2:apache2,mysql'")
        exit(1)

    # Create the app
    app = create_app(username=args.username, password=args.password, services=SERVICES)

    # Run the app
    debug_mode = args.debug or os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=args.host, port=args.port, debug=debug_mode)
