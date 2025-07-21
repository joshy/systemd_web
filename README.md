# systemd_web
 
A super simple web control for start/stop/status of systemd services

This is a company app for other flask web apps as there are no special dependencies needed beside which are typically already installed likea
 * flask
 * python-dotenv
 * gunicorn


To run the app simple create a systemd service file with the following executable
`gunicorn "systemd_web:create_app(username='foo',password='foo',services=['dummy-service'])"`


### Service Format

- **Local services**: Just the service name (e.g., `'nginx'`, `'mysql'`)
- **Remote services**: `user@host:service_name` (e.g., `'user@192.168.1.100:nginx'`)

### Example ExecStart

```bash
ExecStart=/var/www/abc/.venv/bin/gunicorn -b 0.0.0.0:8011 -w 2 -t 86400 "systemd_web:create_app(username='abc',password='abc',services=['abc','foo@remote-host:remote-service'])"
```

## Polkit Configuration

If you want to run the systemd service as a non-root user (recommended), you'll need to configure polkit to allow that user to manage systemd services without sudo.

Create a polkit rule file `/etc/polkit-1/rules.d/50-systemd-web.rules`:

```javascript
polkit.addRule(function(action, subject) {
    // Define allowed services
    var allowedServices = [
        "example.service",
        "nginx.service",
        "mysql.service"
    ];
    
    // Define allowed actions
    var allowedActions = ["start", "stop", "restart", "status"];
    
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        subject.user == "your-username" &&
        action.lookup("unit") &&
        allowedServices.indexOf(action.lookup("unit")) >= 0 &&
        allowedActions.indexOf(action.lookup("verb")) >= 0) {
        
        return polkit.Result.YES;
    }
    
    return polkit.Result.NOT_HANDLED;
});
```

Replace `"your-username"` with the actual username running the systemd service, and update the `allowedServices` array with the services you want to manage.


## Publish to pypi
* uv build
* uv publish