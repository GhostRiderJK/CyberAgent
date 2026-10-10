import uvicorn
from cyberagent.api.main import app
from cyberagent.config import config

if __name__ == "__main__":
    host = config.get("api.host", "0.0.0.0")
    port = config.get("api.port", 8000)
    uvicorn.run(app, host=host, port=port)