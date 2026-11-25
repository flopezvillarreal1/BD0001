from flask import Flask
from tienda import tienda_bp

app = Flask(__name__, template_folder='plantillas')

app.register_blueprint(tienda_bp)

if __name__ == "__main__":
    import os
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)