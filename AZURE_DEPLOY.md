# Azure App Service Deployment

This project is ready for Azure App Service (Linux).

## Files added

- `startup.sh`
- updated `requirements.txt` with `gunicorn`

## Azure setup

1. Push this project to GitHub.
2. In Azure Portal, create:
   - `App Service`
   - Runtime: `Python 3.11` or newer
   - OS: `Linux`
3. In `Deployment Center`, connect your GitHub repository.
4. In `Configuration` -> `General settings` -> `Startup Command`, set:

```bash
bash startup.sh
```

5. Save and restart the App Service.

## What Azure will run

`startup.sh` starts the app with:

```bash
gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 600 app:app
```

## After deployment

Azure will give you a public URL like:

```text
https://your-app-name.azurewebsites.net
```

You can share that URL with your friend, and it will keep working even when your computer is off.
