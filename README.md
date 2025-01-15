# systemd_web
 
A super simple web control for start/stop/status of systemd services

This is a company app for other flask web apps as there are no special dependencies needed beside which are typically already installed like
 * flask
 * python-dotenv
 * gunicorn


To run the app simple create a systemd service file with the following executable
`gunicorn "systemd_web:create_app(username='foo',password='foo',services=['dummy-service'])"`